import logging
from datetime import datetime
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.db import DatabaseError
from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from .forms import ClaimReviewForm, CompanyBrandingForm, EmployeeRegistrationForm, ExpenseClaimForm
from .models import Company, EmployeeProfile, ExpenseClaim, ExpenseReceipt


logger = logging.getLogger(__name__)


class EmployeeLoginView(LoginView):
    template_name = 'claims/login.html'


class EmployeeLogoutView(LogoutView):
    next_page = 'home'


def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    company_count = 0
    claim_count = 0
    try:
        company_count = Company.objects.filter(is_active=True).count()
        claim_count = ExpenseClaim.objects.count()
    except DatabaseError:
        pass

    context = {
        'company_count': company_count,
        'claim_count': claim_count,
    }
    return render(request, 'claims/home.html', context)


def manifest(request):
    body = {
        'name': 'Rimborso spese',
        'short_name': 'Rimborso',
        'description': 'Rimborsi spese per dipendenti, installabile da mobile.',
        'start_url': '/',
        'scope': '/',
        'display': 'standalone',
        'background_color': '#071c31',
        'theme_color': '#0b3654',
        'icons': [
            {
                'src': '/static/claims/branding/app-logo-192.png',
                'sizes': '192x192',
                'type': 'image/png',
                'purpose': 'any maskable',
            },
            {
                'src': '/static/claims/branding/app-logo-512.png',
                'sizes': '512x512',
                'type': 'image/png',
                'purpose': 'any maskable',
            },
        ],
    }
    import json
    return HttpResponse(json.dumps(body), content_type='application/manifest+json')


def service_worker(request):
        script = """
const CACHE_NAME = 'rimborso-spese-v6';
const APP_SHELL = ['/', '/accedi/', '/registrati/', '/static/claims/app.css?v=20260713d'];
const PUBLIC_ROUTES = new Set(['/', '/accedi/', '/registrati/']);

self.addEventListener('install', (event) => {
    event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;

    const url = new URL(event.request.url);
    const isStaticAsset = url.origin === self.location.origin && url.pathname.startsWith('/static/');
    const isPublicRoute = url.origin === self.location.origin && PUBLIC_ROUTES.has(url.pathname);

    if (!isStaticAsset && !isPublicRoute) {
        event.respondWith(fetch(event.request));
        return;
    }

    event.respondWith(
        caches.match(event.request).then((cached) => {
            if (cached) return cached;
            return fetch(event.request)
                .then((response) => {
                    if (!response || response.status !== 200 || response.type === 'opaque') return response;
                    const copy = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
                    return response;
                })
                .catch(() => caches.match('/'));
        })
    );
});
""".strip()
        return HttpResponse(script, content_type='application/javascript')


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = EmployeeRegistrationForm(request.POST, request.FILES)
        try:
            if form.is_valid():
                try:
                    user, profile = form.save()
                except ValidationError as exc:
                    form.add_error(None, exc)
                except Exception:
                    logger.exception('Registration failed during save flow.')
                    form.add_error(None, 'Non siamo riusciti a completare la registrazione. Riprova tra poco.')
                else:
                    return redirect(f"/accedi/?registered=1")
        except Exception:
            logger.exception('Registration failed during form validation.')
            form.add_error(None, 'Non siamo riusciti a completare la registrazione. Riprova tra poco.')
    else:
        form = EmployeeRegistrationForm()

    return render(request, 'claims/register.html', {'form': form})


def _get_profile(user):
    return EmployeeProfile.objects.select_related('company', 'user').get(user=user)


def _user_can_manage_company(profile):
    return profile.is_company_admin or profile.user.is_staff or profile.user.is_superuser


@login_required
def dashboard(request):
    profile = _get_profile(request.user)
    claims = profile.claims.all()
    summary = claims.aggregate(
        total_amount=Coalesce(
            Sum('amount'),
            Value(0, output_field=DecimalField(max_digits=10, decimal_places=2)),
        ),
        total_submitted=Count('id'),
    )
    status_counts = {
        'submitted': claims.filter(status=ExpenseClaim.STATUS_SUBMITTED).count(),
        'approved': claims.filter(status=ExpenseClaim.STATUS_APPROVED).count(),
        'rejected': claims.filter(status=ExpenseClaim.STATUS_REJECTED).count(),
        'reimbursed': claims.filter(status=ExpenseClaim.STATUS_REIMBURSED).count(),
    }
    context = {
        'profile': profile,
        'claims': claims[:20],
        'report_month': timezone.localdate().strftime('%Y-%m'),
        'summary': summary,
        'status_counts': status_counts,
    }
    return render(request, 'claims/dashboard.html', context)


@login_required
def profile(request):
    profile = _get_profile(request.user)
    if request.method == 'POST':
        branding_form = CompanyBrandingForm(request.POST, request.FILES, instance=profile.company)
        if branding_form.is_valid():
            branding_form.save()
            messages.success(request, 'Logo aziendale aggiornato.')
            return redirect('profile')
    else:
        branding_form = CompanyBrandingForm(instance=profile.company)

    context = {
        'profile': profile,
        'is_company_admin': _user_can_manage_company(profile),
        'branding_form': branding_form,
    }
    return render(request, 'claims/profile.html', context)


@login_required
def create_claim(request):
    profile = _get_profile(request.user)
    if request.method == 'POST':
        form = ExpenseClaimForm(request.POST, request.FILES)
        if form.is_valid():
            claim = form.save(commit=False)
            claim.employee = profile
            claim.company = profile.company
            claim.save()
            uploaded_receipts = form.cleaned_data.get('receipts', [])
            for index, receipt_file in enumerate(uploaded_receipts, start=1):
                ExpenseReceipt.objects.create(
                    claim=claim,
                    file=receipt_file,
                    label=f'Scontrino {index}',
                )
            messages.success(request, 'Richiesta inviata correttamente.')
            return redirect('claim_detail', claim_id=claim.pk)
    else:
        form = ExpenseClaimForm()

    return render(request, 'claims/claim_form.html', {'form': form, 'profile': profile})


@login_required
def claim_detail(request, claim_id):
    profile = _get_profile(request.user)
    claim = get_object_or_404(
        ExpenseClaim.objects.select_related('company', 'employee__user').prefetch_related('receipts'),
        pk=claim_id,
        employee=profile,
    )
    return render(request, 'claims/claim_detail.html', {'claim': claim, 'profile': profile})


def _claim_report_label(month_value):
    if not month_value:
        return 'storico completo'

    month_start = datetime.strptime(month_value, '%Y-%m').date()
    return month_start.strftime('%m/%Y')


def _draw_pdf_row(pdf, y_pos, left_text, right_text, width):
    pdf.setFont('Helvetica', 11)
    pdf.setFillColor(colors.whitesmoke)
    pdf.drawString(18 * mm, y_pos, left_text)
    right_width = stringWidth(right_text, 'Helvetica-Bold', 11)
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(width - 18 * mm - right_width, y_pos, right_text)


@login_required
def claim_pdf_report(request):
    profile = _get_profile(request.user)
    month_value = (request.GET.get('month') or '').strip()
    claims = profile.claims.all()

    if month_value:
        try:
            month_start = datetime.strptime(month_value, '%Y-%m').date()
        except ValueError:
            messages.error(request, 'Formato mese non valido.')
            return redirect('dashboard')
        claims = claims.filter(expense_date__year=month_start.year, expense_date__month=month_start.month)

    claims = claims.order_by('-expense_date', '-submitted_at')
    total_amount = claims.aggregate(
        total=Coalesce(
            Sum('amount'),
            Value(0, output_field=DecimalField(max_digits=10, decimal_places=2)),
        )
    )['total']

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y_pos = height - 22 * mm

    pdf.setTitle('Rimborso spese')
    pdf.setFillColor(colors.HexColor('#0b3654'))
    pdf.rect(0, height - 34 * mm, width, 34 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont('Helvetica-Bold', 18)
    pdf.drawString(18 * mm, height - 20 * mm, 'Report rimborsi spese')
    pdf.setFont('Helvetica', 10)
    pdf.drawString(18 * mm, height - 27 * mm, f'Dipendente: {profile.user.get_full_name().strip() or profile.user.username}')
    pdf.drawString(108 * mm, height - 27 * mm, f'Azienda: {profile.company.name}')

    y_pos -= 26 * mm
    pdf.setFillColor(colors.HexColor('#dfeff2'))
    pdf.setFont('Helvetica-Bold', 12)
    pdf.drawString(18 * mm, y_pos, f'Periodo: {_claim_report_label(month_value)}')
    pdf.drawRightString(width - 18 * mm, y_pos, f'Totale: {total_amount:.2f} EUR')
    y_pos -= 10 * mm

    if not claims:
        pdf.setFont('Helvetica', 11)
        pdf.drawString(18 * mm, y_pos, 'Nessuna spesa trovata per il periodo richiesto.')
    else:
        for index, claim in enumerate(claims, start=1):
            if y_pos < 34 * mm:
                pdf.showPage()
                y_pos = height - 24 * mm
                pdf.setFillColor(colors.whitesmoke)

            pdf.setStrokeColor(colors.HexColor('#72f0e2'))
            pdf.setFillColor(colors.HexColor('#dfeff2'))
            pdf.roundRect(16 * mm, y_pos - 16 * mm, width - 32 * mm, 20 * mm, 4 * mm, stroke=1, fill=0)
            pdf.setFont('Helvetica-Bold', 12)
            pdf.drawString(20 * mm, y_pos - 5 * mm, f'{index}. {claim.title}')
            amount_label = f'{claim.amount:.2f} {claim.currency}'
            amount_width = stringWidth(amount_label, 'Helvetica-Bold', 12)
            pdf.drawString(width - 20 * mm - amount_width, y_pos - 5 * mm, amount_label)

            row_left = f'{claim.category} · {claim.expense_date:%d/%m/%Y} · Stato: {claim.get_status_display()}'
            attachment_count = claim.receipts.count() + (1 if claim.receipt else 0)
            row_right = f'{attachment_count} allegati' if attachment_count else 'Nessuna ricevuta'
            _draw_pdf_row(pdf, y_pos - 11 * mm, row_left, row_right, width)

            if claim.description:
                pdf.setFont('Helvetica', 10)
                pdf.setFillColor(colors.HexColor('#bcd5db'))
                pdf.drawString(20 * mm, y_pos - 15 * mm, claim.description[:105])

            y_pos -= 24 * mm

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    filename_suffix = month_value or 'completo'
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="rimborsi-{filename_suffix}.pdf"'
    return response


@login_required
def company_dashboard(request):
    profile = _get_profile(request.user)
    if not _user_can_manage_company(profile):
        messages.error(request, 'Non hai accesso alla gestione aziendale.')
        return redirect('dashboard')

    claims = ExpenseClaim.objects.filter(company=profile.company).select_related('employee__user')
    reviewable_claims = claims.exclude(status=ExpenseClaim.STATUS_REIMBURSED)
    context = {
        'profile': profile,
        'claims': claims[:50],
        'reviewable_count': reviewable_claims.count(),
        'submitted_count': claims.filter(status=ExpenseClaim.STATUS_SUBMITTED).count(),
        'approved_count': claims.filter(status=ExpenseClaim.STATUS_APPROVED).count(),
    }
    return render(request, 'claims/company_dashboard.html', context)


@login_required
def review_claim(request, claim_id):
    profile = _get_profile(request.user)
    if not _user_can_manage_company(profile):
        messages.error(request, 'Non hai accesso alla gestione aziendale.')
        return redirect('dashboard')

    claim = get_object_or_404(
        ExpenseClaim.objects.select_related('employee__user', 'company'),
        pk=claim_id,
        company=profile.company,
    )

    if request.method == 'POST':
        form = ClaimReviewForm(request.POST, instance=claim)
        if form.is_valid():
            reviewed_claim = form.save(commit=False)
            reviewed_claim.reviewed_at = timezone.now()
            reviewed_claim.save()
            messages.success(request, 'Richiesta aggiornata.')
            return redirect('company_dashboard')
    else:
        form = ClaimReviewForm(instance=claim)

    return render(request, 'claims/review_claim.html', {'form': form, 'claim': claim, 'profile': profile})

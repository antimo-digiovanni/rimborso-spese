from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponse
from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.utils import timezone

from .forms import ClaimReviewForm, EmployeeRegistrationForm, ExpenseClaimForm
from .models import Company, EmployeeProfile, ExpenseClaim


class EmployeeLoginView(LoginView):
    template_name = 'claims/login.html'


class EmployeeLogoutView(LogoutView):
    next_page = 'home'


def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    context = {
        'company_count': Company.objects.filter(is_active=True).count(),
        'claim_count': ExpenseClaim.objects.count(),
    }
    return render(request, 'claims/home.html', context)


def manifest(request):
        body = {
                'name': 'Expense Hub',
                'short_name': 'Expense Hub',
                'description': 'Rimborsi spese per dipendenti, installabile da mobile.',
                'start_url': '/',
                'scope': '/',
                'display': 'standalone',
                'background_color': '#f6f1e8',
                'theme_color': '#0b6e4f',
                'icons': [
                        {
                                'src': static('claims/icons/icon-192.svg'),
                                'sizes': '192x192',
                                'type': 'image/svg+xml',
                            'background_color': '#f5f8ff',
                            'theme_color': '#1d4ed8',
                        {
                                'src': static('claims/icons/icon-512.svg'),
                                'sizes': '512x512',
                                'type': 'image/svg+xml',
                                'purpose': 'any maskable',
                        },
                ],
        }
        import json
        return HttpResponse(json.dumps(body), content_type='application/manifest+json')


def service_worker(request):
        script = """
const CACHE_NAME = 'expense-hub-v1';
const APP_SHELL = ['/', '/accedi/', '/registrati/', '/static/claims/app.css'];

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
        form = EmployeeRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            profile = _get_profile(user)
            if profile.is_company_admin:
                messages.success(request, 'Account creato. Abbiamo aperto il tuo spazio aziendale di prova: ora puoi iniziare subito.')
            else:
                messages.success(request, 'Account creato. Ora puoi inserire la tua prima richiesta di rimborso.')
            return redirect('dashboard')
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
        'summary': summary,
        'status_counts': status_counts,
    }
    return render(request, 'claims/dashboard.html', context)


@login_required
def profile(request):
    profile = _get_profile(request.user)
    context = {
        'profile': profile,
        'is_company_admin': _user_can_manage_company(profile),
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
            messages.success(request, 'Richiesta inviata correttamente.')
            return redirect('dashboard')
    else:
        form = ExpenseClaimForm()

    return render(request, 'claims/claim_form.html', {'form': form, 'profile': profile})


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

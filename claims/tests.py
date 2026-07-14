from io import BytesIO
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from .models import Company, EmployeeProfile, ExpenseClaim, ExpenseReceipt


def make_test_image(name='test.png', color='navy'):
    buffer = BytesIO()
    image = Image.new('RGB', (8, 8), color=color)
    image.save(buffer, format='PNG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/png')


class RegistrationFlowTests(TestCase):
    def test_employee_can_register_and_create_company(self):
        response = self.client.post(reverse('register'), {
            'company_name': 'Acme Logistics',
            'first_name': 'Luca',
            'last_name': 'Bianchi',
            'email': 'luca@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })

        self.assertRedirects(response, f"{reverse('login')}?registered=1")
        user = User.objects.get(username='luca@example.com')
        profile = EmployeeProfile.objects.get(user=user)
        self.assertEqual(profile.company.name, 'Acme Logistics')
        self.assertTrue(profile.is_company_admin)

    def test_employee_can_join_existing_company_by_name(self):
        company = Company.objects.create(name='Acme Logistics', slug='acme-logistics', invite_code='ACME2026')
        response = self.client.post(reverse('register'), {
            'company_name': 'Acme Logistics',
            'first_name': 'Sara',
            'last_name': 'Neri',
            'email': 'sara@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })

        self.assertRedirects(response, f"{reverse('login')}?registered=1")
        profile = EmployeeProfile.objects.get(user__username='sara@example.com')
        self.assertEqual(profile.company, company)
        self.assertFalse(profile.is_company_admin)

    def test_register_shows_form_error_when_save_fails(self):
        with patch('claims.views.EmployeeRegistrationForm.save', side_effect=ValidationError('Registrazione temporaneamente non disponibile.')):
            response = self.client.post(reverse('register'), {
                'company_name': 'Acme Logistics',
                'first_name': 'Luca',
                'last_name': 'Bianchi',
                'email': 'luca2@example.com',
                'password1': 'SecurePass123!',
                'password2': 'SecurePass123!',
            })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registrazione temporaneamente non disponibile.')

    def test_register_shows_generic_error_when_unexpected_exception_occurs(self):
        with patch('claims.views.EmployeeRegistrationForm.save', side_effect=RuntimeError('boom')):
            response = self.client.post(reverse('register'), {
                'company_name': 'Acme Logistics',
                'first_name': 'Luca',
                'last_name': 'Bianchi',
                'email': 'luca3@example.com',
                'password1': 'SecurePass123!',
                'password2': 'SecurePass123!',
            })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Non siamo riusciti a completare la registrazione. Riprova tra poco.')

    def test_register_shows_generic_error_when_validation_crashes(self):
        with patch('claims.views.EmployeeRegistrationForm.is_valid', side_effect=RuntimeError('boom')):
            response = self.client.post(reverse('register'), {
                'company_name': 'Acme Logistics',
                'first_name': 'Luca',
                'last_name': 'Bianchi',
                'email': 'luca4@example.com',
                'password1': 'SecurePass123!',
                'password2': 'SecurePass123!',
            })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Non siamo riusciti a completare la registrazione. Riprova tra poco.')

    def test_email_check_is_case_insensitive(self):
        User.objects.create_user(username='Luca@Example.com', password='SecurePass123!', email='Luca@Example.com')

        response = self.client.post(reverse('register'), {
            'company_name': 'Acme Logistics',
            'first_name': 'Luca',
            'last_name': 'Bianchi',
            'email': 'luca@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Esiste gia un account con questa email.')

    def test_registration_can_store_company_logo(self):
        response = self.client.post(reverse('register'), {
            'company_name': 'Logo Logistics',
            'first_name': 'Marta',
            'last_name': 'Riva',
            'email': 'marta@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'company_logo': make_test_image('logo.png', color='teal'),
        })

        self.assertRedirects(response, f"{reverse('login')}?registered=1")
        company = Company.objects.get(name='Logo Logistics')
        self.assertTrue(bool(company.logo))


class ClaimFlowTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Beta Services', slug='beta-services', invite_code='BETA2026')
        self.user = User.objects.create_user(username='anna@example.com', password='StrongPass123!', email='anna@example.com')
        self.profile = EmployeeProfile.objects.create(user=self.user, company=self.company)

    def test_employee_can_create_claim(self):
        self.client.login(username='anna@example.com', password='StrongPass123!')
        response = self.client.post(reverse('create_claim'), {
            'title': 'Taxi aeroporto',
            'category': 'Trasferta',
            'description': 'Taxi per raggiungere il cliente.',
            'amount': '48.50',
            'currency': 'EUR',
            'expense_date': '2026-07-01',
        })

        claim = ExpenseClaim.objects.get()
        self.assertRedirects(response, reverse('claim_detail', args=[claim.id]))
        claim = ExpenseClaim.objects.get()
        self.assertEqual(claim.company, self.company)
        self.assertEqual(claim.employee, self.profile)
        self.assertEqual(claim.amount, Decimal('48.50'))

    def test_employee_can_open_claim_detail_and_receipt(self):
        claim = ExpenseClaim.objects.create(
            company=self.company,
            employee=self.profile,
            title='Parcheggio',
            category='Trasferta',
            amount=Decimal('12.00'),
            expense_date='2026-07-04',
            receipt=SimpleUploadedFile('scontrino.jpg', b'filecontent', content_type='image/jpeg'),
        )

        self.client.login(username='anna@example.com', password='StrongPass123!')
        response = self.client.get(reverse('claim_detail', args=[claim.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Scontrino principale')
        self.assertContains(response, 'Parcheggio')

    def test_employee_can_create_claim_with_multiple_receipts(self):
        self.client.login(username='anna@example.com', password='StrongPass123!')
        response = self.client.post(reverse('create_claim'), {
            'title': 'Pranzo e parcheggio',
            'category': 'Cliente',
            'description': 'Due spese nella stessa giornata.',
            'amount': '32.50',
            'currency': 'EUR',
            'expense_date': '2026-07-06',
            'receipts': [
                make_test_image('scontrino-1.png', color='red'),
                make_test_image('scontrino-2.png', color='green'),
            ],
        })

        claim = ExpenseClaim.objects.get(title='Pranzo e parcheggio')
        self.assertRedirects(response, reverse('claim_detail', args=[claim.id]))
        self.assertEqual(ExpenseReceipt.objects.filter(claim=claim).count(), 2)

    def test_employee_can_download_claim_pdf_report(self):
        ExpenseClaim.objects.create(
            company=self.company,
            employee=self.profile,
            title='Hotel',
            category='Trasferta',
            amount=Decimal('145.00'),
            expense_date='2026-07-05',
        )

        self.client.login(username='anna@example.com', password='StrongPass123!')
        response = self.client.get(reverse('claim_pdf_report'), {'month': '2026-07'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename="rimborsi-2026-07.pdf"', response['Content-Disposition'])

    def test_claim_pdf_report_draws_uploaded_receipt_images(self):
        claim = ExpenseClaim.objects.create(
            company=self.company,
            employee=self.profile,
            title='Cena cliente',
            category='Cliente',
            amount=Decimal('38.00'),
            expense_date='2026-07-07',
        )
        ExpenseReceipt.objects.create(claim=claim, file=make_test_image('receipt-image.png', color='orange'), label='Ricevuta cena')

        self.client.login(username='anna@example.com', password='StrongPass123!')
        with patch('claims.views.canvas.Canvas.drawImage') as draw_image_mock:
            response = self.client.get(reverse('claim_pdf_report'), {'month': '2026-07'})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(draw_image_mock.called)

    def test_claim_pdf_report_draws_company_logo_in_header(self):
        self.company.logo = make_test_image('company-logo.png', color='blue')
        self.company.save(update_fields=['logo'])
        ExpenseClaim.objects.create(
            company=self.company,
            employee=self.profile,
            title='Treno',
            category='Trasferta',
            amount=Decimal('18.00'),
            expense_date='2026-07-09',
        )

        self.client.login(username='anna@example.com', password='StrongPass123!')
        with patch('claims.views._draw_company_logo') as draw_logo_mock:
            response = self.client.get(reverse('claim_pdf_report'), {'month': '2026-07'})

        self.assertEqual(response.status_code, 200)
        draw_logo_mock.assert_called()

    def test_employee_can_delete_own_claim(self):
        claim = ExpenseClaim.objects.create(
            company=self.company,
            employee=self.profile,
            title='Parcheggio da cancellare',
            category='Trasferta',
            amount=Decimal('8.50'),
            expense_date='2026-07-08',
        )
        ExpenseReceipt.objects.create(claim=claim, file=make_test_image('delete-me.png', color='yellow'), label='Scontrino')

        self.client.login(username='anna@example.com', password='StrongPass123!')
        response = self.client.post(reverse('delete_claim', args=[claim.id]))

        self.assertRedirects(response, reverse('dashboard'))
        self.assertFalse(ExpenseClaim.objects.filter(pk=claim.pk).exists())
        self.assertEqual(ExpenseReceipt.objects.count(), 0)

    def test_dashboard_shows_pdf_export_and_not_quick_mobile_panel(self):
        self.client.login(username='anna@example.com', password='StrongPass123!')
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Scarica PDF del mese')
        self.assertNotContains(response, 'Uso rapido da cellulare')

    def test_employee_can_update_company_logo_from_profile(self):
        self.client.login(username='anna@example.com', password='StrongPass123!')
        response = self.client.post(reverse('profile'), {
            'logo': make_test_image('updated-logo.png', color='purple'),
        })

        self.assertRedirects(response, reverse('profile'))
        self.company.refresh_from_db()
        self.assertTrue(bool(self.company.logo))

    def test_company_admin_can_review_claim_for_own_company(self):
        manager = User.objects.create_user(username='manager@example.com', password='StrongPass123!', email='manager@example.com')
        manager_profile = EmployeeProfile.objects.create(user=manager, company=self.company, is_company_admin=True)
        claim = ExpenseClaim.objects.create(
            company=self.company,
            employee=self.profile,
            title='Hotel',
            category='Trasferta',
            amount=Decimal('120.00'),
            expense_date='2026-07-02',
        )

        self.client.login(username='manager@example.com', password='StrongPass123!')
        response = self.client.post(reverse('review_claim', args=[claim.id]), {
            'status': ExpenseClaim.STATUS_APPROVED,
            'admin_notes': 'Ok per rimborso',
        })

        self.assertRedirects(response, reverse('company_dashboard'))
        claim.refresh_from_db()
        self.assertEqual(claim.status, ExpenseClaim.STATUS_APPROVED)
        self.assertEqual(claim.admin_notes, 'Ok per rimborso')
        self.assertIsNotNone(claim.reviewed_at)

    def test_company_admin_cannot_review_other_company_claim(self):
        other_company = Company.objects.create(name='Other Co', slug='other-co', invite_code='OTHER2026')
        manager = User.objects.create_user(username='othermanager@example.com', password='StrongPass123!', email='othermanager@example.com')
        EmployeeProfile.objects.create(user=manager, company=other_company, is_company_admin=True)
        claim = ExpenseClaim.objects.create(
            company=self.company,
            employee=self.profile,
            title='Pranzo',
            category='Cliente',
            amount=Decimal('30.00'),
            expense_date='2026-07-03',
        )

        self.client.login(username='othermanager@example.com', password='StrongPass123!')
        response = self.client.get(reverse('review_claim', args=[claim.id]))

        self.assertEqual(response.status_code, 404)

    def test_employee_profile_page_is_available(self):
        self.client.login(username='anna@example.com', password='StrongPass123!')
        response = self.client.get(reverse('profile'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Profilo')

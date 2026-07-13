from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Company, EmployeeProfile, ExpenseClaim


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

        self.assertRedirects(response, reverse('dashboard'))
        claim = ExpenseClaim.objects.get()
        self.assertEqual(claim.company, self.company)
        self.assertEqual(claim.employee, self.profile)
        self.assertEqual(claim.amount, Decimal('48.50'))

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

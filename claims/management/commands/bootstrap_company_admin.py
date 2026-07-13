from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from claims.models import Company, EmployeeProfile


class Command(BaseCommand):
    help = 'Crea o aggiorna una azienda e il relativo admin aziendale.'

    def add_arguments(self, parser):
        parser.add_argument('--company-name', required=True, help='Nome dell\'azienda da creare o aggiornare.')
        parser.add_argument('--invite-code', help='Codice invito da assegnare all\'azienda.')
        parser.add_argument('--admin-email', required=True, help='Email dell\'utente admin aziendale.')
        parser.add_argument('--password', required=True, help='Password iniziale dell\'admin aziendale.')
        parser.add_argument('--first-name', default='Admin', help='Nome dell\'admin aziendale.')
        parser.add_argument('--last-name', default='Azienda', help='Cognome dell\'admin aziendale.')

    def handle(self, *args, **options):
        company_name = options['company_name'].strip()
        invite_code = (options.get('invite_code') or '').strip().upper()
        admin_email = options['admin_email'].strip().lower()

        if not company_name:
            raise CommandError('company-name non puO essere vuoto.')
        if not admin_email:
            raise CommandError('admin-email non puO essere vuoto.')

        company_defaults = {}
        if invite_code:
            company_defaults['invite_code'] = invite_code

        company, company_created = Company.objects.get_or_create(
            name=company_name,
            defaults=company_defaults,
        )

        if invite_code and company.invite_code != invite_code:
            company.invite_code = invite_code
            company.save(update_fields=['invite_code'])

        user, user_created = User.objects.get_or_create(
            username=admin_email,
            defaults={
                'email': admin_email,
                'first_name': options['first_name'].strip(),
                'last_name': options['last_name'].strip(),
            },
        )

        if user_created:
            user.set_password(options['password'])
            user.save()
        else:
            updated = False
            if user.email != admin_email:
                user.email = admin_email
                updated = True
            if options['first_name'].strip() and user.first_name != options['first_name'].strip():
                user.first_name = options['first_name'].strip()
                updated = True
            if options['last_name'].strip() and user.last_name != options['last_name'].strip():
                user.last_name = options['last_name'].strip()
                updated = True
            if updated:
                user.save(update_fields=['email', 'first_name', 'last_name'])

        profile, profile_created = EmployeeProfile.objects.get_or_create(
            user=user,
            defaults={
                'company': company,
                'is_company_admin': True,
            },
        )

        profile.company = company
        profile.is_company_admin = True
        profile.save(update_fields=['company', 'is_company_admin'])

        self.stdout.write(self.style.SUCCESS(
            f"Azienda {'creata' if company_created else 'aggiornata'}: {company.name} | "
            f"utente {'creato' if user_created else 'aggiornato'}: {user.username} | "
            f"profilo {'creato' if profile_created else 'aggiornato'}"
        ))
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.text import slugify

from .models import Company, EmployeeProfile, ExpenseClaim


class EmployeeRegistrationForm(forms.Form):
    company_name = forms.CharField(
        label='Nome azienda',
        max_length=160,
        help_text='Se l\'azienda non esiste ancora la creiamo subito per la prova del dipendente.',
    )
    first_name = forms.CharField(label='Nome', max_length=150)
    last_name = forms.CharField(label='Cognome', max_length=150)
    email = forms.EmailField(label='Email di lavoro')
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Conferma password', widget=forms.PasswordInput)

    def clean_company_name(self):
        company_name = ' '.join(self.cleaned_data['company_name'].split()).strip()
        if not company_name:
            raise forms.ValidationError('Inserisci il nome della tua azienda.')

        company = Company.objects.filter(slug=slugify(company_name), is_active=True).first()
        if company and not company.allow_self_registration:
            raise forms.ValidationError('Questa azienda non accetta nuove registrazioni autonome.')

        self.company_name = company_name
        self.company = company
        return company_name

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError('Esiste gia un account con questa email.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Le password non coincidono.')
        if password1:
            validate_password(password1)
        return cleaned_data

    @transaction.atomic
    def save(self):
        email = self.cleaned_data['email']
        company = self.company
        company_was_created = False

        if company is None:
            try:
                company = Company.objects.create(name=self.company_name)
                company_was_created = True
            except IntegrityError:
                company = Company.objects.filter(slug=slugify(self.company_name), is_active=True).first()
                if company is None:
                    raise ValidationError('Non siamo riusciti a creare lo spazio aziendale. Riprova.')

        try:
            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=self.cleaned_data['first_name'].strip(),
                last_name=self.cleaned_data['last_name'].strip(),
                password=self.cleaned_data['password1'],
            )
        except IntegrityError:
            raise ValidationError('Esiste gia un account con questa email.')

        profile, _ = EmployeeProfile.objects.get_or_create(
            user=user,
            defaults={
                'company': company,
                'is_company_admin': company_was_created,
            },
        )
        return user, profile


class ExpenseClaimForm(forms.ModelForm):
    class Meta:
        model = ExpenseClaim
        fields = ['title', 'category', 'description', 'amount', 'currency', 'expense_date', 'receipt']
        labels = {
            'title': 'Titolo',
            'category': 'Categoria',
            'description': 'Descrizione',
            'amount': 'Importo',
            'currency': 'Valuta',
            'expense_date': 'Data spesa',
            'receipt': 'Ricevuta',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'expense_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-input')


class ClaimReviewForm(forms.ModelForm):
    class Meta:
        model = ExpenseClaim
        fields = ['status', 'admin_notes']
        labels = {
            'status': 'Stato',
            'admin_notes': 'Note interne',
        }
        widgets = {
            'admin_notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].choices = [
            (ExpenseClaim.STATUS_APPROVED, 'Approvata'),
            (ExpenseClaim.STATUS_REJECTED, 'Respinta'),
            (ExpenseClaim.STATUS_REIMBURSED, 'Rimborsata'),
        ]
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-input')
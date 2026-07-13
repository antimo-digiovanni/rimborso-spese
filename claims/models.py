import secrets
import string

from django.conf import settings
from django.db import models
from django.template.defaultfilters import slugify
from django.urls import reverse


def generate_invite_code(length=8):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class Company(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    invite_code = models.CharField(max_length=20, unique=True, default=generate_invite_code)
    is_active = models.BooleanField(default=True)
    allow_self_registration = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'companies'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            suffix = 2
            while Company.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f'{base_slug}-{suffix}'
                suffix += 1
            self.slug = slug

        if not self.invite_code:
            self.invite_code = generate_invite_code()
        super().save(*args, **kwargs)


class EmployeeProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='employee_profile')
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='employees')
    job_title = models.CharField(max_length=120, blank=True)
    is_company_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['company__name', 'user__first_name', 'user__last_name', 'user__username']

    def __str__(self):
        full_name = self.user.get_full_name().strip() or self.user.username
        return f'{full_name} · {self.company.name}'


class ExpenseClaim(models.Model):
    STATUS_SUBMITTED = 'submitted'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_REIMBURSED = 'reimbursed'
    STATUS_CHOICES = [
        (STATUS_SUBMITTED, 'Inviata'),
        (STATUS_APPROVED, 'Approvata'),
        (STATUS_REJECTED, 'Respinta'),
        (STATUS_REIMBURSED, 'Rimborsata'),
    ]

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='claims')
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name='claims')
    title = models.CharField(max_length=160)
    category = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='EUR')
    expense_date = models.DateField()
    receipt = models.FileField(upload_to='receipts/%Y/%m/', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUBMITTED)
    admin_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-expense_date', '-submitted_at']

    def __str__(self):
        return f'{self.title} · {self.employee}'

    def save(self, *args, **kwargs):
        if self.employee_id:
            self.company = self.employee.company
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('dashboard')

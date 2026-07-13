from django.contrib import admin

from .models import Company, EmployeeProfile, ExpenseClaim


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
	list_display = ('name', 'slug', 'invite_code', 'is_active', 'allow_self_registration', 'created_at')
	list_filter = ('is_active', 'allow_self_registration')
	search_fields = ('name', 'slug', 'invite_code')
	prepopulated_fields = {'slug': ('name',)}


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'company', 'job_title', 'is_company_admin', 'created_at')
	list_filter = ('company',)
	search_fields = ('user__username', 'user__first_name', 'user__last_name', 'company__name')


@admin.register(ExpenseClaim)
class ExpenseClaimAdmin(admin.ModelAdmin):
	list_display = ('title', 'employee', 'company', 'amount', 'currency', 'expense_date', 'status')
	list_filter = ('status', 'company', 'currency')
	search_fields = ('title', 'category', 'employee__user__username', 'employee__user__first_name', 'employee__user__last_name')

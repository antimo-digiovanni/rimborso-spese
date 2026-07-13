from django.urls import path

from .views import (
    EmployeeLoginView,
    EmployeeLogoutView,
    claim_detail,
    claim_pdf_report,
    company_dashboard,
    create_claim,
    dashboard,
    home,
    profile,
    register,
    review_claim,
)

urlpatterns = [
    path('', home, name='home'),
    path('accedi/', EmployeeLoginView.as_view(), name='login'),
    path('esci/', EmployeeLogoutView.as_view(), name='logout'),
    path('registrati/', register, name='register'),
    path('dashboard/', dashboard, name='dashboard'),
    path('profilo/', profile, name='profile'),
    path('azienda/', company_dashboard, name='company_dashboard'),
    path('azienda/rimborsi/<int:claim_id>/', review_claim, name='review_claim'),
    path('rimborsi/nuovo/', create_claim, name='create_claim'),
    path('rimborsi/report/pdf/', claim_pdf_report, name='claim_pdf_report'),
    path('rimborsi/<int:claim_id>/', claim_detail, name='claim_detail'),
]
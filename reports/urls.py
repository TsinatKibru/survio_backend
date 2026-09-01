from django.urls import path
from . import views

urlpatterns = [
    # List all forms available for reporting
    path('forms/', views.FormReportListView.as_view(), name='report-form-list'),

    # JSON analytics summary for a specific form
    path('forms/<int:form_id>/summary/', views.FormReportSummaryView.as_view(), name='report-summary'),

    # KoboToolbox-style PDF download
    path('forms/<int:form_id>/pdf/', views.FormReportPDFView.as_view(), name='report-pdf'),

    # Excel workbook download (Summary + Raw Data tabs)
    path('forms/<int:form_id>/excel/', views.FormReportExcelView.as_view(), name='report-excel'),
]

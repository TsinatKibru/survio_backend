from django.urls import path
from . import views

urlpatterns = [
    path('', views.AllSubmissionsView.as_view(), name='submission-list'),
    path('create/', views.SubmissionCreateView.as_view(), name='submission-create'),
    path('mine/', views.MySubmissionsView.as_view(), name='my-submissions'),
    path('stats/', views.DashboardStatsView.as_view(), name='dashboard-stats'),
    path('global-stats/', views.GlobalAnalyticsView.as_view(), name='global-stats'),
    path('export-compliance-csv/', views.ExportComplianceCSVView.as_view(), name='export-compliance-csv'),
    path('export-compliance-excel/', views.ExportComplianceExcelView.as_view(), name='export-compliance-excel'),
    path('export-compliance-pdf/', views.ExportCompliancePDFView.as_view(), name='export-compliance-pdf'),
    path('<int:pk>/', views.SubmissionDetailView.as_view(), name='submission-detail'),
]

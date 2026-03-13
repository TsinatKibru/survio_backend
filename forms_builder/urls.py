from django.urls import path
from . import views

urlpatterns = [
    path('', views.FormListView.as_view(), name='form-list'),
    path('create/', views.FormCreateView.as_view(), name='form-create'),
    path('<int:pk>/', views.FormDetailView.as_view(), name='form-detail'),
    path('<int:pk>/edit/', views.FormUpdateView.as_view(), name='form-update'),
    path('my-assignments/', views.MyAssignmentsView.as_view(), name='my-assignments'),
    path('pending/', views.PendingTasksView.as_view(), name='pending-tasks'),
]

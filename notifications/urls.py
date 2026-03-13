from django.urls import path
from . import views

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='notification-list'),
    path('<int:pk>/', views.NotificationUpdateView.as_view(), name='notification-update'),
    path('preferences/', views.PreferenceView.as_view(), name='notification-preferences'),
]

from django.utils import timezone
from django.db import models
from rest_framework import generics, permissions
from .models import Ad
from .serializers import AdSerializer

class AdListView(generics.ListAPIView):
    serializer_class = AdSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        today = timezone.now().date()
        return Ad.objects.filter(
            is_active=True
        ).filter(
            # Start date check: NULL or <= today
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=today)
        ).filter(
            # End date check: NULL or >= today
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=today)
        )

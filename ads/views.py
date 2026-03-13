from rest_framework import generics, permissions
from .models import Ad
from .serializers import AdSerializer

class AdListView(generics.ListAPIView):
    serializer_class = AdSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Ad.objects.filter(is_active=True)

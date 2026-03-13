from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from .admin import survio_admin_site

schema_view = get_schema_view(
   openapi.Info(
      title="Survio API",
      default_version='v1',
      description="API documentation for Survio platform",
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

from django.http import JsonResponse

def home_view(request):
    return JsonResponse({"status": "running", "message": "Survio API is alive"})

urlpatterns = [
    path('', home_view),
    path('admin/', survio_admin_site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/forms/', include('forms_builder.urls')),
    path('api/submissions/', include('submissions.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/ads/', include('ads.urls')),
    # Swagger
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

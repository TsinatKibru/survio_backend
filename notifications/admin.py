from django.contrib import admin
from .models import Notification, NotificationPreference
from survio.admin import survio_admin_site

@admin.register(Notification, site=survio_admin_site)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read')
    search_fields = ('title', 'body', 'recipient__username')
    list_per_page = 10

@admin.register(NotificationPreference, site=survio_admin_site)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'email_enabled', 'in_app_enabled')
    list_per_page = 10

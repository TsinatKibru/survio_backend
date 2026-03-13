from django.contrib import admin
from .models import Ad
from survio.admin import survio_admin_site

@admin.register(Ad, site=survio_admin_site)
class AdAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'start_date', 'end_date', 'order')
    list_filter = ('is_active',)
    search_fields = ('title', 'description')

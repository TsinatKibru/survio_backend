from django.contrib import admin
from .models import Ad, NewsItem
from survio.admin import survio_admin_site

@admin.register(Ad, site=survio_admin_site)
class AdAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'start_date', 'end_date', 'order')
    list_filter = ('is_active',)
    search_fields = ('title', 'description')
    list_per_page = 10


@admin.register(NewsItem, site=survio_admin_site)
class NewsItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'tag', 'published_date', 'is_published')
    list_filter = ('tag', 'is_published')
    search_fields = ('title', 'description')
    list_per_page = 10

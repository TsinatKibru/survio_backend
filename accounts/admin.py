from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Industry, Category
from survio.admin import survio_admin_site

@admin.register(Industry, site=survio_admin_site)
class IndustryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active')
    search_fields = ('name',)
    prepopulated_fields = {'code': ('name',)}

@admin.register(Category, site=survio_admin_site)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active')
    search_fields = ('name',)
    prepopulated_fields = {'code': ('name',)}

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'industry', 'category', 'is_staff')
    list_filter = ('role', 'is_staff', 'industry', 'category')
    fieldsets = UserAdmin.fieldsets + (
        ('Survio Roles & Profile', {'fields': ('role', 'phone', 'organization', 'position', 'industry', 'category', 'profile_picture', 'is_onboarded')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Survio Roles & Profile', {'fields': ('role', 'industry', 'category', 'is_onboarded')}),
    )

survio_admin_site.register(User, CustomUserAdmin)

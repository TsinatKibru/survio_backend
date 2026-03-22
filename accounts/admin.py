from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Industry, Category
from survio.admin import survio_admin_site

@admin.register(Industry, site=survio_admin_site)
class IndustryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    search_fields = ('name',)
    exclude = ('code',)
    list_per_page = 10

@admin.register(Category, site=survio_admin_site)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    search_fields = ('name',)
    exclude = ('code',)
    list_per_page = 10

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'industry', 'category', 'is_staff')
    list_filter = ('role', 'is_staff', 'industry', 'category')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Survio Roles & Profile', {'fields': ('role', 'phone', 'organization', 'position', 'industry', 'category', 'profile_picture', 'is_onboarded')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        ('Survio Roles & Profile', {'fields': ('role', 'industry', 'category', 'is_onboarded')}),
    )
    list_per_page = 10

survio_admin_site.register(User, CustomUserAdmin)

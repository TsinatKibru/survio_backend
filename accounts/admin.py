from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms
from django.contrib.auth.models import Permission
from .models import User, Industry, Category, Role
from survio.admin import survio_admin_site

# Only show permissions from these app labels in the Role form
RELEVANT_APP_LABELS = {'accounts', 'forms_builder', 'submissions', 'notifications', 'ads'}

class RoleAdminForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.filter(
            content_type__app_label__in=RELEVANT_APP_LABELS
        ).select_related('content_type').order_by('content_type__app_label', 'content_type__model', 'codename'),
        required=False,
        widget=admin.widgets.FilteredSelectMultiple('permissions', is_stacked=False),
        help_text='Only shows permissions relevant to this application. Django internals are hidden.'
    )

    class Meta:
        model = Role
        fields = '__all__'


@admin.register(Role, site=survio_admin_site)
class RoleAdmin(admin.ModelAdmin):
    form = RoleAdminForm
    list_display = ('name', 'code', 'description', 'user_count', 'created_at')
    search_fields = ('name', 'code')
    # Use filter_horizontal for a side-by-side permission picker (professional RBAC UX)
    filter_horizontal = ('permissions',)
    # Remove 'user_permissions' from the User form -- now managed via Role
    fieldsets = (
        (None, {'fields': ('name', 'code', 'description')}),
        ('Permissions for this Role', {
            'description': 'Assign Django permissions to this role. All users with this role inherit these permissions.',
            'fields': ('permissions',),
        }),
    )
    readonly_fields = ('created_at',)

    @admin.display(description='Users')
    def user_count(self, obj):
        return obj.users.count()


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
    list_display = ('username', 'email', 'role', 'industry', 'category', 'is_active')
    list_filter = ('role_obj', 'is_active', 'is_staff', 'industry', 'category')
    
    # Base fieldsets (no user_permissions — managed via Role now)
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Account Status', {
            'fields': ('is_active', 'is_staff', 'is_superuser'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Survio Role & Profile', {
            'fields': ('role_obj', 'phone', 'organization', 'position', 'profile_picture', 'is_onboarded'),
        }),
        ('Factory / Industry', {
            'description': 'Not required for Superadmin and Admin roles.',
            'fields': ('industry', 'category'),
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        ('Survio Role & Profile', {
            'fields': ('role_obj', 'first_name', 'last_name', 'email', 'phone', 'organization', 'position'),
        }),
        ('Factory / Industry', {
            'description': 'Leave blank for Superadmin / Admin roles.',
            'fields': ('industry', 'category'),
        }),
    )
    list_per_page = 20

    def get_readonly_fields(self, request, obj=None):
        """
        For existing Superadmin users, make industry/category read-only
        to reinforce that they are global roles.
        """
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and obj.role_obj and obj.role_obj.code == 'superadmin':
            readonly += ['industry', 'category']
        return readonly


survio_admin_site.register(User, CustomUserAdmin)

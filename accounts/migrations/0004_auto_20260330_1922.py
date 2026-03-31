from django.db import migrations

def populate_roles(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    User = apps.get_model('accounts', 'User')

    # 1. Create Roles
    superadmin_role, _ = Role.objects.get_or_create(
        code='superadmin', 
        defaults={'name': 'Super Admin', 'description': 'Global administrative access.'}
    )
    admin_role, _ = Role.objects.get_or_create(
        code='admin', 
        defaults={'name': 'Admin', 'description': 'Organization level administrative access.'}
    )
    companyuser_role, _ = Role.objects.get_or_create(
        code='companyuser', 
        defaults={'name': 'Company User', 'description': 'Standard entry and viewing access.'}
    )

    # 2. Map existing users
    for user in User.objects.all():
        old_role = getattr(user, 'old_role', None)
        if old_role == 'superadmin':
            user.role_obj = superadmin_role
        elif old_role == 'admin':
            user.role_obj = admin_role
        elif old_role == 'user':
            user.role_obj = companyuser_role
        
        # Default for anyone else (e.g. if old_role was empty/null)
        if not user.role_obj:
            if user.is_superuser:
                user.role_obj = superadmin_role
            else:
                user.role_obj = companyuser_role
                
        user.save()

def reverse_populate_roles(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    for user in User.objects.all():
        if user.role_obj:
            if user.role_obj.code == 'companyuser':
                user.old_role = 'user'
            else:
                user.old_role = user.role_obj.code
            user.save()

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0003_rename_role_user_old_role_role_user_role_obj'),
    ]

    operations = [
        migrations.RunPython(populate_roles, reverse_populate_roles),
    ]

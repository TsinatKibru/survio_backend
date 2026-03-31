from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission

class RolePermissionBackend(ModelBackend):
    """
    Custom authentication backend that allowing users to inherit permissions
    from their assigned Role (accounts.models.Role).
    """

    def get_user_permissions(self, user_obj, obj=None):
        """
        Returns a set of permission strings that this user has through their role.
        """
        if not user_obj.is_active or user_obj.is_anonymous or not hasattr(user_obj, 'role_obj'):
            return set()
        
        # Prefetch permissions if they involve a role
        if user_obj.role_obj:
            perms = user_obj.role_obj.permissions.all().select_related('content_type')
            return {f"{p.content_type.app_label}.{p.codename}" for p in perms}
            
        return set()

    def get_all_permissions(self, user_obj, obj=None):
        """
        Combines role-based permissions with direct user permissions and group permissions.
        """
        if not user_obj.is_active or user_obj.is_anonymous:
            return set()
            
        return {
            *self.get_user_permissions(user_obj, obj),
            *super().get_user_permissions(user_obj, obj), # Direct user perms
            *self.get_group_permissions(user_obj, obj),   # Group perms
        }

    def has_perm(self, user_obj, perm, obj=None):
        """
        Returns True if the user has the specified permission.
        """
        return perm in self.get_all_permissions(user_obj, obj)

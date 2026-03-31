from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.is_superuser or (request.user.role_obj and request.user.role_obj.code == 'superadmin')


class IsAdminOrAbove(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if not request.user.role_obj:
            return False
        return request.user.role_obj.code in ['superadmin', 'admin']

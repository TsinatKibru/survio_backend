from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.text import slugify


class Industry(models.Model):
    name = models.CharField(max_length=200)
    code = models.SlugField(unique=True)
    category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name='industries', null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'Industries'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name).replace('-', '_')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=200)
    code = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name).replace('-', '_')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Role(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    permissions = models.ManyToManyField('auth.Permission', blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.code:
            from django.utils.text import slugify
            self.code = slugify(self.name).replace('-', '_')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"


class User(AbstractUser):
    # New Dynamic Role field
    role_obj = models.ForeignKey(Role, on_delete=models.PROTECT, related_name='users')
    
    phone = models.CharField(max_length=20, blank=True)
    organization = models.CharField(max_length=200, blank=True)
    position = models.CharField(max_length=200, blank=True)
    industry = models.ForeignKey(Industry, null=True, blank=True, on_delete=models.SET_NULL)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    is_onboarded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        """
        Auto-sync is_staff based on role:
        - superadmin/admin → is_staff=True (can access Django admin panel)
        - companyuser      → is_staff=False (Flutter app only)
        - Others           → Respect existing is_staff value
        """
        if self.role_obj:
            if self.role_obj.code in ('superadmin', 'admin'):
                self.is_staff = True
            elif self.role_obj.code == 'companyuser':
                if not self.is_superuser:
                    self.is_staff = False
            # For other roles (like Auditor), we don't force it to False 
            # so the admin can manually grant is_staff in the dashboard.
        super().save(*args, **kwargs)

    def __str__(self):
        role_label = self.role_obj.code if self.role_obj else 'No Role'
        return f'{self.get_full_name() or self.username} ({role_label})'

    @property
    def role(self):
        """Compatibility property — returns role code string for API/Flutter."""
        return self.role_obj.code if self.role_obj else None

    @property
    def is_super_admin(self):
        return self.role == 'superadmin'

    @property
    def is_admin_or_above(self):
        if self.is_superuser:
            return True
        return self.role in ['superadmin', 'admin']

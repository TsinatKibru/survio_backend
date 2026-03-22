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


class User(AbstractUser):
    ROLE_SUPERADMIN = 'superadmin'
    ROLE_ADMIN = 'admin'
    ROLE_USER = 'user'
    ROLE_CHOICES = [
        (ROLE_SUPERADMIN, 'Super Admin'),
        (ROLE_ADMIN, 'Admin'),
        (ROLE_USER, 'Field User'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_USER)
    phone = models.CharField(max_length=20, blank=True)
    organization = models.CharField(max_length=200, blank=True)
    position = models.CharField(max_length=200, blank=True)
    industry = models.ForeignKey(Industry, null=True, blank=True, on_delete=models.SET_NULL)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    is_onboarded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.role})'

    @property
    def is_super_admin(self):
        return self.role == self.ROLE_SUPERADMIN

    @property
    def is_admin_or_above(self):
        return self.role in [self.ROLE_SUPERADMIN, self.ROLE_ADMIN] or self.is_superuser

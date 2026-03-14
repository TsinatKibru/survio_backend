from django.db import models
from django.conf import settings


class Notification(models.Model):
    TYPE_FORM_DUE = 'form_due'
    TYPE_FORM_OVERDUE = 'form_overdue'
    TYPE_ANNOUNCEMENT = 'announcement'
    TYPE_REMINDER = 'reminder'
    TYPE_CHOICES = [
        (TYPE_FORM_DUE, 'Form Due'),
        (TYPE_FORM_OVERDUE, 'Form Overdue'),
        (TYPE_ANNOUNCEMENT, 'Announcement'),
        (TYPE_REMINDER, 'Reminder'),
    ]

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    title = models.CharField(max_length=300)
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    related_form_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.notification_type} → {self.recipient}: {self.title}'


class NotificationPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_pref')
    email_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
    reminder_days_before = models.IntegerField(default=3, help_text='Send reminder N days before due date')
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)

    def __str__(self):
        return f'Prefs for {self.user}'


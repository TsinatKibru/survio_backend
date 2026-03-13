from rest_framework import serializers
from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'notification_type', 'title', 'body', 'is_read', 'related_form_id', 'created_at']
        read_only_fields = ['id', 'notification_type', 'title', 'body', 'related_form_id', 'created_at']


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ['email_enabled', 'in_app_enabled', 'reminder_days_before', 'quiet_hours_start', 'quiet_hours_end']

"""
Submission signals — fires in-app notifications on submission events.
No Redis, no Celery, no cron needed. Triggered inline by Django ORM signals.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Submission


@receiver(post_save, sender=Submission)
def notify_on_submission(sender, instance, created, **kwargs):
    """Create an in-app notification when a user submits a report."""
    if not created:
        return
    if instance.status != Submission.STATUS_SUBMITTED:
        return

    try:
        from notifications.models import Notification
        period_label = instance.period.label if instance.period else 'current period'
        form_title = instance.form.title if instance.form else 'form'
        late_note = ' (submitted after due date)' if instance.is_late else ''

        Notification.objects.create(
            recipient=instance.submitted_by,
            notification_type=Notification.TYPE_ANNOUNCEMENT,
            title=f'✅ {form_title} submitted',
            body=f'Your report for {period_label} has been received{late_note}. '
                 f'Organization: {instance.industry_name}.',
            related_form_id=instance.form_id,
        )
    except Exception:
        pass  # Never break the submission flow due to notification failure

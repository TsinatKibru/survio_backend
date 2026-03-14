from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import models
from forms_builder.models import Form, FormAssignment
from submissions.models import Submission
from .models import Notification, NotificationPreference
from datetime import timedelta

User = get_user_model()

def check_pending_forms():
    """
    Periodic task to check for users who haven't filled their required forms.
    Runs daily or as configured in celery beat.
    """
    today = timezone.now().date()
    
    # 1. Monthly Forms: Check if users have submitted the monthly form for the current month
    monthly_forms = Form.objects.filter(schedule_type=Form.SCHEDULE_MONTHLY, is_active=True)
    
    for form in monthly_forms:
        # Get users who should fill this form
        # For simplicity, we assume users with matching category should fill it
        target_users = User.objects.filter(category__code=form.category, role='field_user')
        if form.category == 'all':
            target_users = User.objects.filter(role='field_user')
            
        for user in target_users:
            # Check if user has a submitted entry for this month
            has_submitted = Submission.objects.filter(
                form=form,
                submitted_by=user,
                status=Submission.STATUS_SUBMITTED,
                submitted_at__year=today.year,
                submitted_at__month=today.month
            ).exists()
            
            if not has_submitted:
                # Create notification if not already notified today
                notified_today = Notification.objects.filter(
                    recipient=user,
                    notification_type=Notification.TYPE_REMINDER,
                    related_form_id=form.id,
                    created_at__date=today
                ).exists()
                
                if not notified_today:
                    Notification.objects.create(
                        recipient=user,
                        notification_type=Notification.TYPE_REMINDER,
                        title="Monthly Form Reminder",
                        body=f"You haven't submitted the '{form.title}' for {today.strftime('%B %Y')} yet. Please fill it as soon as possible.",
                        related_form_id=form.id
                    )

def send_due_date_alerts():
    """Checks for FormAssignments that are approaching their due date using per-user thresholds."""
    today = timezone.now().date()
    
    # Find all unique thresholds in use, plus the default 3
    thresholds = set(NotificationPreference.objects.values_list('reminder_days_before', flat=True))
    thresholds.add(3)

    for days in thresholds:
        target_date = today + timedelta(days=days)
        
        # Build query to find matching assignments for this specific threshold group
        # This handles both customized users and those using defaults (or no pref object)
        query = models.Q(due_date=target_date, is_active=True)
        
        if days == 3:
            # Match users with pref=3 OR no preference record at all
            user_filter = (
                models.Q(user__notification_pref__reminder_days_before=3) | 
                models.Q(user__notification_pref__isnull=True)
            )
            # Only if in_app is enabled or no record (implicit enable)
            enable_filter = (
                models.Q(user__notification_pref__in_app_enabled=True) |
                models.Q(user__notification_pref__isnull=True)
            )
        else:
            user_filter = models.Q(user__notification_pref__reminder_days_before=days)
            enable_filter = models.Q(user__notification_pref__in_app_enabled=True)

        assignments = FormAssignment.objects.filter(
            query & user_filter & enable_filter
        ).select_related('user', 'form')
        
        for assignment in assignments:
            # Check for duplication within the same day to be safe 
            already_notified = Notification.objects.filter(
                recipient=assignment.user,
                notification_type=Notification.TYPE_FORM_DUE,
                related_form_id=assignment.form.id,
                created_at__date=today
            ).exists()
            
            if not already_notified:
                Notification.objects.create(
                    recipient=assignment.user,
                    notification_type=Notification.TYPE_FORM_DUE,
                    title="Form Due Soon",
                    body=f"Your assignment for '{assignment.form.title}' is due in {days} days.",
                    related_form_id=assignment.form.id
                )

from django.utils import timezone
from django.contrib.auth import get_user_model
from forms_builder.models import Form, FormAssignment
from submissions.models import Submission
from .models import Notification
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
    """Checks for FormAssignments that are approaching their due date."""
    today = timezone.now().date()
    warning_date = today + timedelta(days=3)
    
    assignments = FormAssignment.objects.filter(
        due_date=warning_date,
        is_active=True
    ).select_related('user', 'form')
    
    for assignment in assignments:
        Notification.objects.create(
            recipient=assignment.user,
            notification_type=Notification.TYPE_FORM_DUE,
            title="Form Due Soon",
            body=f"Your assignment for '{assignment.form.title}' is due in 3 days.",
            related_form_id=assignment.form.id
        )

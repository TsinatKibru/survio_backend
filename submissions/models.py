from django.db import models
from django.conf import settings
from forms_builder.models import Form, Question, ReportingPeriod


class Submission(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SUBMITTED, 'Submitted'),
    ]

    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='submissions')
    # V2: Reference to the specific reporting window this submission covers
    period = models.ForeignKey(
        ReportingPeriod,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='submissions',
        help_text='The reporting period this submission covers (e.g., March 2026)'
    )
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='submissions')
    # V2: Hard FK to the Organization (Industry) - not just a text snapshot
    organization = models.ForeignKey(
        'accounts.Industry',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='submissions',
        help_text='The factory/organization this report belongs to'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    # V2: Track late submissions (backfilling)
    is_late = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Snapshot fields - kept for denormalized reporting
    food_category = models.CharField(max_length=200, blank=True)
    industry_name = models.CharField(max_length=200, blank=True)
    # V2: Snapshot form version at time of submission
    form_version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['-created_at']
        # V2: CRITICAL - prevent duplicate submissions per org per period
        constraints = [
            models.UniqueConstraint(
                fields=['form', 'period', 'organization'],
                condition=models.Q(period__isnull=False, organization__isnull=False),
                name='unique_submission_per_org_per_period'
            )
        ]

    def __str__(self):
        return f'{self.form.title} by {self.organization or self.submitted_by} [{self.status}]'


class Answer(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    value = models.TextField(blank=True)
    # V2: Snapshot question label at time of submission (audit-proof)
    question_label_snapshot = models.CharField(
        max_length=500, blank=True,
        help_text='Question label snapshotted at submission time. Preserves history if form is edited later.'
    )
    image = models.ImageField(upload_to='answers/', null=True, blank=True)

    def __str__(self):
        return f'[{self.submission_id}] Q{self.question_id}: {self.value[:50]}'

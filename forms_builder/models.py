from django.db import models
from django.utils.text import slugify
from django.conf import settings


class Form(models.Model):
    SCHEDULE_DAILY = 'daily'
    SCHEDULE_WEEKLY = 'weekly'
    SCHEDULE_MONTHLY = 'monthly'
    SCHEDULE_QUARTERLY = 'quarterly'
    SCHEDULE_BIANNUAL = 'biannual'
    SCHEDULE_ANNUAL = 'annual'
    SCHEDULE_CHOICES = [
        (SCHEDULE_DAILY, 'Daily'),
        (SCHEDULE_WEEKLY, 'Weekly'),
        (SCHEDULE_MONTHLY, 'Monthly'),
        (SCHEDULE_QUARTERLY, 'Quarterly'),
        (SCHEDULE_BIANNUAL, 'Bi-Annual'),
        (SCHEDULE_ANNUAL, 'Annual'),
    ]

    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    # V2: Dynamic ForeignKey link - category is now admin-manageable
    category = models.ForeignKey(
        'accounts.Category',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='forms',
        help_text='Leave blank for forms applicable to all categories'
    )
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_CHOICES, default=SCHEDULE_MONTHLY)
    # V2: Submission window config
    opens_on_day = models.PositiveIntegerField(default=1, help_text='Day of period the form opens (1=start)')
    due_on_day = models.PositiveIntegerField(default=10, help_text='Day of period the submission is due')
    closes_on_day = models.PositiveIntegerField(default=15, help_text='Day of period the form locks (no more submissions)')
    version = models.PositiveIntegerField(default=1, help_text='Increment when form questions change significantly')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_forms')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} v{self.version}'


class ReportingPeriod(models.Model):
    """
    V2: Represents a specific reporting window for a form.
    Admin creates these with specific dates — could be monthly, quarterly, annual, anything.
    Status is COMPUTED from the dates (no scheduler needed, always accurate).
    """
    STATUS_OPEN = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_UPCOMING = 'upcoming'
    STATUS_OVERDUE = 'overdue'  # past due_date but before close_date

    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='periods')
    label = models.CharField(max_length=100, help_text='Human readable label, e.g. "March 2026"')
    period_start = models.DateField(help_text='Start of reporting period')
    period_end = models.DateField(help_text='End of reporting period')
    due_date = models.DateField(help_text='Soft deadline - triggers warning in app')
    close_date = models.DateField(help_text='Hard deadline - form locks after this date')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-period_start']
        unique_together = ['form', 'period_start']

    @property
    def status(self):
        """Computed live from dates — no scheduler or stored field needed."""
        from django.utils import timezone
        today = timezone.now().date()
        if today < self.period_start:
            return self.STATUS_UPCOMING
        elif today <= self.due_date:
            return self.STATUS_OPEN
        elif today <= self.close_date:
            return self.STATUS_OVERDUE  # can still submit, but flagged as late
        else:
            return self.STATUS_CLOSED

    @property
    def is_open(self):
        return self.status in (self.STATUS_OPEN, self.STATUS_OVERDUE)

    @property
    def days_until_due(self):
        from django.utils import timezone
        delta = self.due_date - timezone.now().date()
        return delta.days

    def __str__(self):
        return f'{self.form.title} - {self.label} [{self.status}]'


class Section(models.Model):
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='sections')
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.form.title} > {self.title}'


class Question(models.Model):
    TYPE_TEXT = 'text'
    TYPE_NUMBER = 'number'
    TYPE_DECIMAL = 'decimal'
    TYPE_SELECT = 'select'
    TYPE_MULTISELECT = 'multiselect'
    TYPE_DATE = 'date'
    TYPE_YES_NO = 'yes_no'
    TYPE_IMAGE = 'image'
    TYPE_LOCATION = 'location'
    TYPE_TEXTAREA = 'textarea'
    TYPE_PHONE = 'phone'
    TYPE_EMAIL = 'email'

    TYPE_CHOICES = [
        (TYPE_TEXT, 'Short Text'),
        (TYPE_NUMBER, 'Integer Number'),
        (TYPE_DECIMAL, 'Decimal Number'),
        (TYPE_SELECT, 'Select One'),
        (TYPE_MULTISELECT, 'Select Multiple'),
        (TYPE_DATE, 'Date'),
        (TYPE_YES_NO, 'Yes / No'),
        (TYPE_IMAGE, 'Image Upload'),
        (TYPE_LOCATION, 'GPS Location'),
        (TYPE_TEXTAREA, 'Long Text / Notes'),
        (TYPE_PHONE, 'Phone Number'),
        (TYPE_EMAIL, 'Email Address'),
    ]

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='questions')
    label = models.CharField(max_length=500)
    hint = models.CharField(max_length=500, blank=True)
    question_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    is_required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    depends_on = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='dependents')
    depends_on_value = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.section} > Q{self.order}: {self.label[:50]}'


class QuestionOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    label = models.CharField(max_length=300)
    value = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def save(self, *args, **kwargs):
        if not self.value:
            # Match the pattern used in seed_data.py: lowercase, underscores, alphanumeric only
            import re
            clean = self.label.lower().replace(' ', '_')
            self.value = re.sub(r'[^a-zA-Z0-9_]', '', clean)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.question.label[:30]} → {self.label}'


class FormAssignment(models.Model):
    """
    V2: Assign a form to a specific industry (organization).
    When assigned, every user in that industry will see the form.
    """
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='assignments')
    # V2: assignment is at the Industry/Organization level, not individual user
    industry = models.ForeignKey(
        'accounts.Industry',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='form_assignments',
        help_text='Assign to a specific factory. If blank, applies via category.'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='form_assignments',
        help_text='Assign to a specific user (overrides industry assignment)'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [['form', 'industry'], ['form', 'user']]

    def __str__(self):
        target = self.industry or self.user
        return f'{self.form.title} → {target}'

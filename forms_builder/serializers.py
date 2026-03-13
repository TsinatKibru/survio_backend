from rest_framework import serializers
from django.utils import timezone
from .models import Form, Section, Question, QuestionOption, FormAssignment, ReportingPeriod


# ─────────────────────────────────────────────────────────────
# Primitive serializers
# ─────────────────────────────────────────────────────────────

class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ['id', 'label', 'value', 'order']


class QuestionSerializer(serializers.ModelSerializer):
    options = QuestionOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            'id', 'label', 'hint', 'question_type', 'is_required', 'order',
            'depends_on', 'depends_on_value', 'options',
        ]


class SectionSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Section
        fields = ['id', 'title', 'description', 'order', 'questions']


class ReportingPeriodSerializer(serializers.ModelSerializer):
    # status is a computed @property, so expose via SerializerMethodField
    status = serializers.SerializerMethodField()
    days_until_due = serializers.SerializerMethodField()

    class Meta:
        model = ReportingPeriod
        fields = ['id', 'label', 'period_start', 'period_end', 'due_date', 'close_date', 'status', 'days_until_due']

    def get_status(self, obj):
        return obj.status

    def get_days_until_due(self, obj):
        return obj.days_until_due


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _get_active_period(form, user=None):
    """
    Returns the period whose submission window contains today.
    Prioritizes unsubmitted periods if user is provided.
    """
    today = timezone.now().date()
    active_periods = form.periods.filter(period_start__lte=today, close_date__gte=today).order_by('period_start')
    
    if not user or not user.is_authenticated or not hasattr(user, 'industry') or not user.industry:
        return active_periods.last() # Return newest by default

    # Prioritize the oldest unsubmitted active period
    from submissions.models import Submission
    for period in active_periods:
        exists = Submission.objects.filter(
            form=form,
            period=period,
            organization=user.industry,
        ).exists()
        if not exists:
            return period
            
    # If all active are submitted, return the most recent one
    return active_periods.last()


def _is_submitted_by(form, user, period=None):
    """
    True if the user's organisation already submitted for the given period.
    If period is None, checks the 'currently recommended' active period.
    """
    if not user or not user.is_authenticated or not hasattr(user, 'industry') or not user.industry:
        return False
    
    target_period = period or _get_active_period(form, user)
    if not target_period:
        return False
        
    from submissions.models import Submission
    return Submission.objects.filter(
        form=form,
        period=target_period,
        organization=user.industry,
    ).exists()


# ─────────────────────────────────────────────────────────────
# Form serializers
# ─────────────────────────────────────────────────────────────

class FormListSerializer(serializers.ModelSerializer):
    """Lightweight — no sections. Used in lists and submission confirmations."""
    section_count = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    current_period = serializers.SerializerMethodField()
    is_submitted = serializers.SerializerMethodField()

    class Meta:
        model = Form
        fields = [
            'id', 'title', 'description', 'category', 'category_name',
            'schedule_type', 'version', 'is_active',
            'section_count', 'question_count',
            'current_period', 'is_submitted', 'created_at',
        ]

    def get_section_count(self, obj):
        return obj.sections.count()

    def get_question_count(self, obj):
        return Question.objects.filter(section__form=obj).count()

    def get_category_name(self, obj):
        return obj.category.name if obj.category else None

    def get_current_period(self, obj):
        """Returns the active period; falls back to next upcoming if none active."""
        request = self.context.get('request')
        forced_period = self.context.get('forced_period')
        if forced_period:
            data = ReportingPeriodSerializer(forced_period).data
            # Check if backlog
            newest_active = obj.periods.filter(period_start__lte=timezone.now().date(), close_date__gte=timezone.now().date()).order_by('-period_start').first()
            if newest_active and forced_period.period_start < newest_active.period_start:
                data['is_backlog'] = True
            return data

        user = request.user if request else None
        
        period = _get_active_period(obj, user)
        upcoming = (
            obj.periods
            .filter(period_start__gt=timezone.now().date())
            .order_by('period_start')
            .first()
        )
        if upcoming:
            return ReportingPeriodSerializer(upcoming).data
        return None

    def get_is_submitted(self, obj):
        request = self.context.get('request')
        return _is_submitted_by(obj, request.user if request else None)


class FormDetailSerializer(serializers.ModelSerializer):
    """Full detail including sections and questions."""
    sections = SectionSerializer(many=True, read_only=True)
    category_name = serializers.SerializerMethodField()
    current_period = serializers.SerializerMethodField()
    is_submitted = serializers.SerializerMethodField()

    class Meta:
        model = Form
        fields = [
            'id', 'title', 'description', 'category', 'category_name',
            'schedule_type', 'version', 'is_active',
            'sections', 'current_period', 'is_submitted',
            'created_at', 'updated_at',
        ]

    def get_category_name(self, obj):
        return obj.category.name if obj.category else None

    def get_current_period(self, obj):
        request = self.context.get('request')
        user = request.user if request else None
        
        period = _get_active_period(obj, user)
        if period:
            data = ReportingPeriodSerializer(period).data
            newest_active = obj.periods.filter(period_start__lte=timezone.now().date(), close_date__gte=timezone.now().date()).order_by('-period_start').first()
            if newest_active and period.period_start < newest_active.period_start:
                data['is_backlog'] = True
            return data
        upcoming = (
            obj.periods
            .filter(period_start__gt=timezone.now().date())
            .order_by('period_start')
            .first()
        )
        if upcoming:
            return ReportingPeriodSerializer(upcoming).data
        return None

    def get_is_submitted(self, obj):
        request = self.context.get('request')
        return _is_submitted_by(obj, request.user if request else None)


class FormAssignmentSerializer(serializers.ModelSerializer):
    form = FormListSerializer(read_only=True)

    class Meta:
        model = FormAssignment
        fields = ['id', 'form', 'industry', 'is_active', 'assigned_at']

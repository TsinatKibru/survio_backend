from rest_framework import serializers
from django.utils import timezone
from .models import Submission, Answer
from forms_builder.serializers import FormListSerializer


class AnswerSerializer(serializers.ModelSerializer):
    question_label = serializers.SerializerMethodField()

    class Meta:
        model = Answer
        fields = ['question', 'value', 'image', 'question_label']

    def get_question_label(self, obj):
        return obj.question_label_snapshot or (obj.question.label if obj.question else None)


class SubmissionCreateSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True)

    class Meta:
        model = Submission
        # period is optional; if not provided, the view will derive it
        fields = ['form', 'period', 'status', 'answers']

    def validate(self, data):
        """Block double-submission for the same org+period."""
        request = self.context.get('request')
        if not request:
            return data
        user = request.user
        form = data.get('form')
        period = data.get('period') # Explicitly provided by mobile app
        
        if not form or not user.industry:
            return data

        # If period not provided, find the 'smart' active period (same as perform_create logic)
        if not period:
            from forms_builder.serializers import _get_active_period
            period = _get_active_period(form, user)

        if period:
            already_submitted = Submission.objects.filter(
                form=form,
                period=period,
                organization=user.industry,
            ).exists()
            if already_submitted:
                raise serializers.ValidationError(
                    f"Your organization has already submitted for the '{period.label}' period."
                )

        return data

    def create(self, validated_data):
        answers_data = validated_data.pop('answers')
        submission = Submission.objects.create(**validated_data)
        for answer_data in answers_data:
            Answer.objects.create(submission=submission, **answer_data)
        return submission


class SubmissionListSerializer(serializers.ModelSerializer):
    form = FormListSerializer(read_only=True)
    submitted_by_name = serializers.CharField(source='submitted_by.get_full_name', read_only=True)
    period_label = serializers.CharField(source='period.label', read_only=True, default='')

    class Meta:
        model = Submission
        fields = [
            'id', 'form', 'status', 'period_label', 'food_category', 'industry_name',
            'submitted_by_name', 'submitted_at', 'is_late', 'created_at',
        ]


class SubmissionDetailSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True, read_only=True)
    form = FormListSerializer(read_only=True)
    period_label = serializers.CharField(source='period.label', read_only=True, default='')

    class Meta:
        model = Submission
        fields = [
            'id', 'form', 'status', 'period_label', 'food_category', 'industry_name',
            'answers', 'submitted_at', 'is_late', 'created_at', 'updated_at',
        ]

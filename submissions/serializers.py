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
            
        answers_data = data.get('answers', [])
        
        # 1. Validate Answers strictly against Question types
        import re
        for ans in answers_data:
            q = ans.get('question')
            val = ans.get('value', '').strip() if ans.get('value') else ''
            
            if not q: continue
            
            # A. Required Check
            if q.is_required and not val:
                raise serializers.ValidationError({f"question_{q.id}": f"{q.label} is required."})
                
            if not val: continue
                
            # B. Format Check
            if q.question_type == 'number':
                if not val.isdigit() or int(val) < 0:
                    raise serializers.ValidationError({f"question_{q.id}": f"{q.label} must be a positive whole number."})
            elif q.question_type == 'decimal':
                try:
                    d = float(val)
                    if d < 0:
                        raise serializers.ValidationError({f"question_{q.id}": f"{q.label} cannot be negative."})
                except ValueError:
                    raise serializers.ValidationError({f"question_{q.id}": f"{q.label} must be a valid number."})
            elif q.question_type == 'email':
                if not re.match(r'^[^@]+@[^@]+\.[^@]+$', val):
                    raise serializers.ValidationError({f"question_{q.id}": f"{q.label} must be a valid email address."})
            elif q.question_type == 'phone':
                if len(val) < 8:
                    raise serializers.ValidationError({f"question_{q.id}": f"{q.label} must be a valid phone number."})

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
    is_editable = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            'id', 'form', 'status', 'period_label', 'food_category', 'industry_name',
            'submitted_by_name', 'submitted_at', 'is_late', 'created_at', 'is_editable'
        ]

    def get_is_editable(self, obj):
        return obj.period.is_open if obj.period else False


class SubmissionDetailSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True, read_only=True)
    form = FormListSerializer(read_only=True)
    period_label = serializers.CharField(source='period.label', read_only=True, default='')
    is_editable = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            'id', 'form', 'status', 'period_label', 'food_category', 'industry_name',
            'answers', 'submitted_at', 'is_late', 'created_at', 'updated_at', 'is_editable'
        ]

    def get_is_editable(self, obj):
        return obj.period.is_open if obj.period else False


class SubmissionUpdateSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True)

    class Meta:
        model = Submission
        fields = ['status', 'answers']

    def validate(self, data):
        # Allow editing only if the reporting period is still active
        submission = self.instance
        if not submission:
            return data
            
        if submission.period and not submission.period.is_open:
            raise serializers.ValidationError("This reporting period has closed. You can no longer edit this submission.")

        # Re-use the answer validation from SubmissionCreateSerializer
        answers_data = data.get('answers', [])
        
        import re
        for ans in answers_data:
            q = ans.get('question')
            val = ans.get('value', '').strip() if ans.get('value') else ''
            
            if not q: continue
            
            if q.is_required and not val:
                raise serializers.ValidationError({f"question_{q.id}": f"{q.label} is required."})
                
            if not val: continue
                
            if q.question_type == 'number':
                if not val.isdigit() or int(val) < 0:
                    raise serializers.ValidationError({f"question_{q.id}": f"{q.label} must be a positive whole number."})
            elif q.question_type == 'decimal':
                try:
                    d = float(val)
                    if d < 0:
                        raise serializers.ValidationError({f"question_{q.id}": f"{q.label} cannot be negative."})
                except ValueError:
                    raise serializers.ValidationError({f"question_{q.id}": f"{q.label} must be a valid number."})
            elif q.question_type == 'email':
                if not re.match(r'^[^@]+@[^@]+\.[^@]+$', val):
                    raise serializers.ValidationError({f"question_{q.id}": f"{q.label} must be a valid email address."})
            elif q.question_type == 'phone':
                if len(val) < 8:
                    raise serializers.ValidationError({f"question_{q.id}": f"{q.label} must be a valid phone number."})

        return data

    def update(self, instance, validated_data):
        # Update submission fields
        instance.status = validated_data.get('status', instance.status)
        instance.save()

        # Update answers
        if 'answers' in validated_data:
            answers_data = validated_data.pop('answers')
            for answer_data in answers_data:
                question = answer_data.get('question')
                value = answer_data.get('value')
                
                try:
                    answer = Answer.objects.get(submission=instance, question=question)
                    answer.value = value
                    if 'image' in answer_data:
                        answer.image = answer_data['image']
                    answer.save()
                except Answer.DoesNotExist:
                    answer = Answer.objects.create(submission=instance, **answer_data)
                    
                if not answer.question_label_snapshot and question:
                    answer.question_label_snapshot = question.label
                    answer.save(update_fields=['question_label_snapshot'])
                    
        return instance

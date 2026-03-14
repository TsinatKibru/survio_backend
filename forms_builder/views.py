from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Form, FormAssignment
from .serializers import FormListSerializer, FormDetailSerializer, FormAssignmentSerializer
from accounts.permissions import IsAdminOrAbove
from django.utils import timezone


class FormListView(generics.ListAPIView):
    """List forms available to the requesting user."""
    serializer_class = FormListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin_or_above:
            return Form.objects.filter(is_active=True).select_related('category')
            
        from django.db.models import Q
        # V2: Filter by FK-based category (ForeignKey to Category model)
        q_filter = Q(assignments__user=user, assignments__is_active=True)
        if user.category:
            # Match by the Category FK object
            q_filter |= Q(category=user.category)
        # Also include forms with no category restriction (null = applies to all)
        q_filter |= Q(category__isnull=True)
            
        return Form.objects.filter(q_filter, is_active=True).select_related('category').distinct()


class FormDetailView(generics.RetrieveAPIView):
    serializer_class = FormDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Form.objects.filter(is_active=True)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        period_id = self.request.query_params.get('period')
        if period_id:
            from .models import ReportingPeriod
            period = get_object_or_404(ReportingPeriod, id=period_id, form_id=self.kwargs['pk'])
            context['forced_period'] = period
        return context


class FormCreateView(generics.CreateAPIView):
    serializer_class = FormDetailSerializer
    permission_classes = [IsAdminOrAbove]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class FormUpdateView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FormDetailSerializer
    permission_classes = [IsAdminOrAbove]
    queryset = Form.objects.all()


class MyAssignmentsView(generics.ListAPIView):
    """My pending form assignments."""
    serializer_class = FormAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return FormAssignment.objects.filter(
            user=self.request.user,
            is_active=True,
        ).select_related('form')

class PendingTasksView(generics.ListAPIView):
    """
    Returns every unsubmitted, open reporting period as an individual 'task'.
    If a form has 2 open periods (backlog + current), it returns 2 entries.
    """
    serializer_class = FormListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # We don't actually use the queryset directly as we need to explode periods
        return Form.objects.none()

    def list(self, request, *args, **kwargs):
        user = request.user
        today = timezone.now().date()
        from django.db.models import Q
        from .models import ReportingPeriod
        from submissions.models import Submission

        # 1. Find all forms assigned to this user
        q_filter = Q(assignments__industry=user.industry, assignments__is_active=True)
        q_filter |= Q(assignments__user=user, assignments__is_active=True)
        if user.category:
            q_filter |= Q(category=user.category)
        q_filter |= Q(category__isnull=True)
        
        assigned_forms = Form.objects.filter(q_filter, is_active=True).distinct()

        tasks = []
        for form in assigned_forms:
            # 2. Find all open periods for this form
            active_periods = form.periods.filter(
                period_start__lte=today,
                close_date__gte=today
            ).order_by('period_start')

            for period in active_periods:
                # 3. Check if submitted
                exists = Submission.objects.filter(
                    form=form,
                    period=period,
                    organization=user.industry,
                ).exists()

                if not exists:
                    # Explode this form-period combo into a task
                    # We inject the period into the context so the serializer can use it
                    serializer = self.get_serializer(form, context={'request': request, 'forced_period': period})
                    tasks.append(serializer.data)

        return Response(tasks)

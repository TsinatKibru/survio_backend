from django.contrib import admin
from forms_builder.models import Form, ReportingPeriod
from submissions.models import Submission
from accounts.models import User, Industry, Category
from django.db.models import Count, Q
from django.utils import timezone

class SurvioAdminSite(admin.AdminSite):
    site_header = "Survio Administration"
    site_title = "Survio Admin"
    index_title = "Welcome to Survio Admin"
    index_template = "admin/index.html"

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        user = request.user
        
        # Base querysets
        submissions_qs = Submission.objects.all()
        forms_qs = Form.objects.filter(is_active=True)
        users_qs = User.objects.all()

        if user.role == User.ROLE_ADMIN and user.category:
            # Role: Admin - isolated to their category
            submissions_qs = submissions_qs.filter(food_category=user.category.code)
            users_qs = users_qs.filter(category=user.category)
            forms_qs = forms_qs.filter(category__in=[user.category.code, 'all'])
            extra_context['is_restricted'] = True
            extra_context['admin_category'] = user.category.name
        else:
            extra_context['is_restricted'] = False

        extra_context['total_users'] = users_qs.count()
        extra_context['total_submissions'] = submissions_qs.count()
        extra_context['active_forms'] = forms_qs.count()
        
        # Chart Data
        category_stats = submissions_qs.values('food_category').annotate(count=Count('id'))
        extra_context['category_labels'] = [s['food_category'] or 'Unknown' for s in category_stats]
        extra_context['category_data'] = [s['count'] for s in category_stats]
        
        extra_context['submitted_count'] = submissions_qs.filter(status='submitted').count()
        extra_context['draft_count'] = submissions_qs.filter(status='draft').count()

        today = timezone.now().date()

        # 1. Heatmap (Category Stats)
        heatmap_data = []
        for cat in Category.objects.filter(is_active=True):
            f_ids = Form.objects.filter(category=cat, is_active=True).values_list('id', flat=True)
            required = ReportingPeriod.objects.filter(form_id__in=f_ids, period_start__lte=today).count()
            submitted = submissions_qs.filter(food_category=cat.name).count()
            rate = int((submitted / required * 100)) if required > 0 else 0
            heatmap_data.append({
                "name": cat.name,
                "rate": rate,
                "status": "critical" if rate < 30 else ("lagging" if rate < 70 else "compliant")
            })
        extra_context['heatmap'] = heatmap_data

        # 2. Industry Performance
        industry_perf = []
        for ind in Industry.objects.filter(is_active=True)[:10]: # Limit to top 10
            q_assigned = Q(assignments__industry=ind) | Q(category=ind.category) | Q(category__isnull=True)
            f_ids = Form.objects.filter(q_assigned, is_active=True).values_list('id', flat=True).distinct()
            required = ReportingPeriod.objects.filter(form_id__in=f_ids, period_start__lte=today).count()
            submitted = submissions_qs.filter(organization=ind).count()
            rate = int((submitted / required * 100)) if required > 0 else 0
            industry_perf.append({
                "name": ind.name,
                "category": ind.category.name if ind.category else "General",
                "rate": rate,
                "submitted": submitted,
                "required": required
            })
        extra_context['industries'] = sorted(industry_perf, key=lambda x: x['rate'], reverse=True)
        
        # 3. Dynamic Success Rate for the Top Card
        # Calculated as total submissions / total required across all active categories
        total_required = sum(item['required'] for item in industry_perf)
        total_submitted = sum(item['submitted'] for item in industry_perf)
        extra_context['success_rate'] = int((total_submitted / total_required * 100)) if total_required > 0 else 0
        
        return super().index(request, extra_context)

survio_admin_site = SurvioAdminSite(name='survio_admin')

import json
from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from forms_builder.models import Form, ReportingPeriod
from submissions.models import Submission
from accounts.models import User, Industry, Category
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta, date
from calendar import month_abbr


class SurvioAdminSite(admin.AdminSite):
    site_header = "Food and Beverage Industry R&D Center"
    site_title = "FBRDC Admin"
    index_title = "Management Dashboard"
    index_template = "admin/index.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'industry-performance/',
                self.admin_view(self.industry_performance_view),
                name='industry-performance',
            ),
        ]
        return custom_urls + urls

    def industry_performance_view(self, request):
        """Dedicated full industry performance page."""
        user = request.user
        submissions_qs = Submission.objects.all()

        if user.role == User.ROLE_ADMIN and user.category:
            submissions_qs = submissions_qs.filter(food_category=user.category.code)

        today = timezone.now().date()

        industry_perf = []
        for ind in Industry.objects.filter(is_active=True).select_related('category').order_by('category__name', 'name'):
            q_assigned = Q(assignments__industry=ind) | Q(category=ind.category) | Q(category__isnull=True)
            f_ids = Form.objects.filter(q_assigned, is_active=True).values_list('id', flat=True).distinct()
            required = ReportingPeriod.objects.filter(form_id__in=f_ids, period_start__lte=today).count()
            submitted = submissions_qs.filter(organization=ind, status='submitted').count()
            rate = int((submitted / required * 100)) if required > 0 else 0
            if rate > 100:
                rate = 100
            status = "critical" if rate < 30 else ("lagging" if rate < 70 else "compliant")
            industry_perf.append({
                "name": ind.name,
                "category": ind.category.name if ind.category else "General",
                "rate": rate,
                "submitted": submitted,
                "required": required,
                "status": status,
            })

        # Sort by category then rate desc
        industry_perf.sort(key=lambda x: (x['category'], -x['rate']))

        categories = sorted(set(i['category'] for i in industry_perf))

        context = {
            **self.each_context(request),
            'title': 'All Industry Performance',
            'industries': industry_perf,
            'categories': categories,
            'total': len(industry_perf),
        }
        return render(request, 'admin/industry_performance.html', context)

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        user = request.user

        # Base querysets
        submissions_qs = Submission.objects.all()
        forms_qs = Form.objects.filter(is_active=True)
        users_qs = User.objects.all()

        if user.role == User.ROLE_ADMIN and user.category:
            submissions_qs = submissions_qs.filter(food_category=user.category.code)
            users_qs = users_qs.filter(category=user.category)
            forms_qs = forms_qs.filter(category__in=[user.category.code, 'all'])
            extra_context['is_restricted'] = True
            extra_context['admin_category'] = user.category.name
        else:
            extra_context['is_restricted'] = False

        # ── Date Filtering ──────────────────────────────────────────────────────
        today = timezone.now().date()
        raw_start = request.GET.get('start_date')
        raw_end = request.GET.get('end_date')

        try:
            from datetime import datetime
            start_date = datetime.strptime(raw_start, '%Y-%m-%d').date() if raw_start else today - timedelta(days=30)
            end_date   = datetime.strptime(raw_end,   '%Y-%m-%d').date() if raw_end   else today
        except ValueError:
            start_date = today - timedelta(days=30)
            end_date   = today

        extra_context['start_date'] = start_date.isoformat()
        extra_context['end_date']   = end_date.isoformat()

        period_qs = submissions_qs.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)

        # Previous period (same length) for trend comparison
        span = (end_date - start_date).days or 1
        prev_start = start_date - timedelta(days=span)
        prev_end   = start_date - timedelta(days=1)
        prev_qs    = submissions_qs.filter(created_at__date__gte=prev_start, created_at__date__lte=prev_end)

        cur_count  = period_qs.count()
        prev_count = prev_qs.count()
        if prev_count > 0:
            trend = round((cur_count - prev_count) / prev_count * 100)
        else:
            trend = 0
        extra_context['submissions_trend']     = trend
        extra_context['submissions_trend_abs'] = abs(trend)

        # ── Stat Cards ──────────────────────────────────────────────────────────
        extra_context['total_users']        = users_qs.count()
        extra_context['total_submissions']  = cur_count
        extra_context['active_forms']       = forms_qs.count()

        # ── Submissions by Category (bar chart) ─────────────────────────────────
        category_stats = period_qs.values('food_category').annotate(count=Count('id'))
        extra_context['category_labels'] = json.dumps([s['food_category'] or 'Unknown' for s in category_stats])
        extra_context['category_data']   = json.dumps([s['count'] for s in category_stats])

        # ── Compliance Over Time (6-month multi-line chart) ─────────────────────
        months  = []
        month_dates = []
        for i in range(5, -1, -1):
            d = today.replace(day=1) - timedelta(days=1)
            # go back i full months from the start of this month
            y = today.year
            m = today.month - i
            while m <= 0:
                m += 12
                y -= 1
            month_dates.append((y, m))
            months.append(f"{month_abbr[m]} {y}")

        extra_context['line_labels'] = json.dumps(months)

        line_datasets = []
        color_map = ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b', '#fd7e14']
        active_categories = list(Category.objects.filter(is_active=True))

        for idx, cat in enumerate(active_categories):
            data = []
            f_ids = list(Form.objects.filter(category=cat, is_active=True).values_list('id', flat=True))
            inds_in_cat = Industry.objects.filter(category=cat, is_active=True).count()

            for (y, m) in month_dates:
                if m == 12:
                    month_end = date(y + 1, 1, 1) - timedelta(days=1)
                else:
                    month_end = date(y, m + 1, 1) - timedelta(days=1)
                month_start = date(y, m, 1)

                required_periods = ReportingPeriod.objects.filter(
                    form_id__in=f_ids,
                    period_start__lte=month_end,
                ).count()
                required = required_periods * inds_in_cat
                submitted = submissions_qs.filter(
                    food_category=cat.name,
                    status='submitted',
                    created_at__date__lte=month_end,
                ).count()
                rate = min(int(submitted / required * 100), 100) if required > 0 else 0
                data.append(rate)

            line_datasets.append({
                'label': cat.name,
                'data': data,
                'color': color_map[idx % len(color_map)],
            })

        extra_context['line_datasets'] = json.dumps(line_datasets)

        # ── Heatmap (Category Stats, always uses all-time data for heatmap) ─────
        heatmap_data = []
        for cat in active_categories:
            f_ids = Form.objects.filter(category=cat, is_active=True).values_list('id', flat=True)
            required_periods = ReportingPeriod.objects.filter(form_id__in=f_ids, period_start__lte=today).count()
            inds_in_cat = Industry.objects.filter(category=cat, is_active=True).count()
            required = required_periods * inds_in_cat
            submitted = submissions_qs.filter(food_category=cat.name, status='submitted').count()
            rate = min(int(submitted / required * 100), 100) if required > 0 else 0
            heatmap_data.append({
                "name": cat.name,
                "rate": rate,
                "status": "critical" if rate < 30 else ("lagging" if rate < 70 else "compliant")
            })
        extra_context['heatmap'] = heatmap_data

        # ── Industry Performance (Top 10) ────────────────────────────────────────
        industry_perf = []
        for ind in Industry.objects.filter(is_active=True):
            q_assigned = Q(assignments__industry=ind) | Q(category=ind.category) | Q(category__isnull=True)
            f_ids = Form.objects.filter(q_assigned, is_active=True).values_list('id', flat=True).distinct()
            required = ReportingPeriod.objects.filter(form_id__in=f_ids, period_start__lte=today).count()
            submitted = submissions_qs.filter(organization=ind, status='submitted').count()
            rate = min(int(submitted / required * 100), 100) if required > 0 else 0
            industry_perf.append({
                "name": ind.name,
                "category": ind.category.name if ind.category else "General",
                "rate": rate,
                "submitted": submitted,
                "required": required,
                "status": "critical" if rate < 30 else ("lagging" if rate < 70 else "compliant"),
            })

        sorted_industries = sorted(industry_perf, key=lambda x: x['rate'], reverse=True)
        extra_context['industries'] = sorted_industries[:10]
        extra_context['has_more_industries'] = len(sorted_industries) > 10
        extra_context['total_industries'] = len(sorted_industries)

        # ── Overall Success Rate ─────────────────────────────────────────────────
        total_required  = sum(item['required']  for item in industry_perf)
        total_submitted = sum(item['submitted'] for item in industry_perf)
        extra_context['success_rate'] = int(total_submitted / total_required * 100) if total_required > 0 else 0

        # ── Live Submission Feed (last 5 submitted) ──────────────────────────────
        live_submissions = (
            Submission.objects
            .filter(status='submitted')
            .select_related('organization', 'submitted_by')
            .order_by('-submitted_at', '-created_at')[:5]
        )
        extra_context['live_submissions'] = live_submissions

        return super().index(request, extra_context)


survio_admin_site = SurvioAdminSite(name='survio_admin')

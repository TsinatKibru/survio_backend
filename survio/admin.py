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

def get_edible_oil_correlation():
    """Returns data comparing Vitamin A/D utilized vs Fortified Oil produced."""
    oil_submissions = Submission.objects.filter(
        form__category__code='edible_oil',
        status='submitted'
    ).select_related('organization')
    
    scatter_data = []
    for sub in oil_submissions:
        answers = sub.answers.all()
        # Corrected labels from database
        vit_utilized = next((a.value for a in answers if 'Vitamin A and D utilized (kg/month)' in a.question.label), None)
        oil_produced = next((a.value for a in answers if 'fortified edible oil (ton/month)' in a.question.label), None)
        
        if vit_utilized and oil_produced:
            try:
                scatter_data.append({
                    'x': float(vit_utilized.replace(',', '')),
                    'y': float(oil_produced.replace(',', '')),
                    'factory': sub.organization.name if sub.organization else 'Unknown'
                })
            except (ValueError, AttributeError):
                pass
                
    return scatter_data

def get_supply_chain_vulnerability():
    """Returns data comparing stock available vs planned production."""
    submissions = Submission.objects.filter(status='submitted').select_related('organization')
    
    vulnerability_data = []
    for sub in submissions:
        answers = sub.answers.all()
        # Corrected labels from database
        stock = next((a.value for a in answers if 'Vitamin A and D available in stock (kg)' in a.question.label), None)
        plan = next((a.value for a in answers if 'Plan to produce fortified edible oil' in a.question.label), None)
        
        if stock and plan:
            try:
                stock_val = float(stock.replace(',', ''))
                plan_val = float(plan.replace(',', ''))
                if plan_val > 0:
                    is_at_risk = stock_val < (plan_val * 0.1) # Risk if stock is < 10% of monthly plan
                    vulnerability_data.append({
                        'factory': sub.organization.name if sub.organization else 'Unknown',
                        'stock': stock_val,
                        'plan': plan_val,
                        'is_risk': is_at_risk
                    })
            except (ValueError, AttributeError):
                pass
                
    vulnerability_data.sort(key=lambda x: (x['stock'] / (x['plan'] or 1)))
    return vulnerability_data[:10]


class SurvioAdminSite(admin.AdminSite):
    site_header = "Food and Beverage Industry R&D Center"
    site_title = "FF-IMS Admin"
    index_title = "Management Dashboard"
    index_template = "admin/index.html"
    login_template = "admin/login.html"
    site_url = None  # Removes the "View site" link from the header

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'industry-performance/',
                self.admin_view(self.industry_performance_view),
                name='industry-performance',
            ),
            path(
                'question-analytics/',
                self.admin_view(self.question_analytics_view),
                name='question-analytics',
            ),
        ]
        return custom_urls + urls

    def industry_performance_view(self, request):
        """Dedicated full industry performance page."""
        from django.core.paginator import Paginator

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

        # All categories from full list (for filter chips)
        categories = sorted(set(i['category'] for i in industry_perf))

        # Filter by search and category
        search_query = request.GET.get('q', '').strip().lower()
        cat_filter = request.GET.get('cat', 'all')
        
        filtered_perf = []
        for item in industry_perf:
            if search_query and search_query not in item['name'].lower():
                continue
            if cat_filter != 'all' and item['category'] != cat_filter:
                continue
            filtered_perf.append(item)

        # Check if this is a full print request
        is_print = request.GET.get('print') == '1'

        if is_print:
            # Bypass pagination for print mode
            page_obj = None
            paginator = None
            industries_to_render = filtered_perf
        else:
            # Paginate — 10 per page
            from django.core.paginator import Paginator
            paginator = Paginator(filtered_perf, 10)
            page_number = request.GET.get('page', 1)
            page_obj = paginator.get_page(page_number)
            industries_to_render = page_obj

        context = {
            **self.each_context(request),
            'title': 'All Industry Performance',
            'industries': industries_to_render,
            'page_obj': page_obj,
            'paginator': paginator,
            'categories': categories,
            'total': len(filtered_perf),
            'search_query': request.GET.get('q', '').strip(),
            'active_cat': cat_filter,
            'is_print': is_print,
        }
        return render(request, 'admin/industry_performance.html', context)

    def question_analytics_view(self, request):
        """View for advanced analytics with real-time aggregation & drill-down."""
        from forms_builder.models import Question
        from accounts.models import Industry
        from submissions.models import Answer
        from django.db.models import Avg, Sum, Count
        
        # 1. Filters & Normalization
        cat_param = request.GET.get('category', 'edible_oil')
        cat_code = cat_param.lower().replace(' ', '_')

        # Get available categories for this user
        available_cats = Category.objects.filter(is_active=True)
        user = request.user
        if user.role == User.ROLE_ADMIN and user.category:
            available_cats = available_cats.filter(code=user.category.code)
            # Override cat_code if restricted
            cat_code = user.category.code

        selected_cat = available_cats.filter(code=cat_code).first()
        if not selected_cat and available_cats.exists():
            selected_cat = available_cats.first()
            cat_code = selected_cat.code

        # Safely convert to integers, ignoring non-numeric strings
        industry_ids = []
        for i in request.GET.getlist('industry_ids'):
            if i:
                try: industry_ids.append(int(i))
                except ValueError: pass

        drill_down_q = request.GET.get('drill_down_q')
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        
        today = timezone.now().date()
        def safe_date(date_str, default):
            if not date_str: return default
            try: return date.fromisoformat(date_str)
            except (ValueError, TypeError): return default

        start_date = safe_date(start_date_str, today - timedelta(days=90))
        end_date = safe_date(end_date_str, today)
        
        # 2. Main Querysets
        submissions = Submission.objects.filter(status='submitted').select_related('organization')
        if selected_cat:
            submissions = submissions.filter(form__category=selected_cat)
        if industry_ids:
            submissions = submissions.filter(organization_id__in=industry_ids)
        
        submissions = submissions.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)

        # 2.5 Drill Down logic
        if drill_down_q:
            drill_label = request.GET.get('drill_down_label', '')
            drill_data = []
            final_label = drill_label

            if drill_down_q == '0' and drill_label:
                # Special Case: Drill down into pivoted Salt data
                # Prefetch answers to avoid N+1 inside the loop
                submissions = submissions.prefetch_related('answers')
                
                for sub in submissions:
                    ans_map = {a.question_id: a.value for a in sub.answers.all()}
                    
                    # Search capacity slots
                    metric_groups = [(370, [371, 372, 373]), (374, [375, 376, 377]), (378, [379, 380, 381]), (382, [383, 384, 385])]
                    metric_labels = ["Installed Capacity", "Max. Attained Capacity", "Actual Production"]
                    
                    for type_id, m_ids in metric_groups:
                        p_type = ans_map.get(type_id)
                        if not p_type: continue
                        clean_type = p_type.replace('_', ' ').replace('-', ' ').title()
                        for idx, m_id in enumerate(m_ids):
                            full_l = f"{clean_type} ({metric_labels[idx]})"
                            if full_l == drill_label:
                                val_str = ans_map.get(m_id)
                                if val_str:
                                    try:
                                        drill_data.append({
                                            'submission': sub, 
                                            'value': val_str
                                        })
                                    except: pass
                    
                    # Search packaging slots
                    pkg_groups = [(386, 387, 388), (389, 390, 391), (392, 393, 394), (405, 406, 407)]
                    for t_id, a_id, u_id in pkg_groups:
                        p_type = ans_map.get(t_id)
                        if not p_type: continue
                        clean_p = p_type.replace('_', ' ').replace('-', ' ').title()
                        full_l = f"{clean_p} (Required Amount)"
                        if full_l == drill_label:
                            val_str = ans_map.get(a_id)
                            if val_str:
                                drill_data.append({
                                    'submission': sub,
                                    'value': val_str
                                })
            else:
                # Standard Case: Drill down into specific Question ID
                try:
                    q = Question.objects.get(id=drill_down_q)
                    final_label = q.label
                    drill_data = Answer.objects.filter(
                        question=q, 
                        submission__in=submissions
                    ).select_related('submission__organization')
                except Question.DoesNotExist:
                    pass
                
            return render(request, 'admin/analytics_drilldown_partial.html', {
                'question': {'label': final_label},
                'answers': drill_data
            })

        # 3. Master Aggregation Table
        explorer_qs = Question.objects.filter(
            section__form__category=selected_cat,
            question_type__in=['number', 'decimal', 'yes_no']
        ).order_by('section__order', 'order') if selected_cat else Question.objects.none()

        explorer_data = []
        
        # --- SPECIAL SALT PIVOT LOGIC ---
        if selected_cat and selected_cat.code == 'salt':
            # 1. Capacity Blocks: (type_id, [metric_ids])
            metric_groups = [
                (370, [371, 372, 373]), (374, [375, 376, 377]),
                (378, [379, 380, 381]), (382, [383, 384, 385]),
            ]
            # 2. Packaging Blocks: (type_id, amount_id, unit_id)
            pkg_groups = [
                (386, 387, 388), (389, 390, 391),
                (392, 393, 394), (405, 406, 407),
            ]
            
            salt_pivot = {}

            # Get all relevant answers in one query
            all_q_ids = [370, 374, 378, 382, 371, 372, 373, 375, 376, 377, 379, 380, 381, 383, 384, 385,
                        386, 387, 388, 389, 390, 391, 392, 393, 394, 405, 406, 407]
            answers_qs = Answer.objects.filter(
                submission__in=submissions,
                question_id__in=all_q_ids
            ).values('submission_id', 'question_id', 'value')

            sub_map = {}
            for a in answers_qs:
                if a['submission_id'] not in sub_map: sub_map[a['submission_id']] = {}
                sub_map[a['submission_id']][a['question_id']] = a['value']

            for sub_id, ans_map in sub_map.items():
                # A. Capacity Pivot
                for type_id, metric_ids in metric_groups:
                    prod_type = ans_map.get(type_id)
                    if not prod_type: continue
                    # Clean label
                    clean_type = prod_type.replace('_', ' ').replace('-', ' ').title()
                    
                    metric_labels = ["Installed Capacity", "Max. Attained Capacity", "Actual Production"]
                    for idx, m_id in enumerate(metric_ids):
                        val_str = ans_map.get(m_id)
                        if not val_str: continue
                        try:
                            val = float(val_str.replace(',', '').split()[0])
                            key = (f"{clean_type} ({metric_labels[idx]})", "ton/day")
                            if key not in salt_pivot: salt_pivot[key] = []
                            salt_pivot[key].append(val)
                        except: pass
                
                # B. Packaging Pivot
                for t_id, a_id, u_id in pkg_groups:
                    p_type = ans_map.get(t_id)
                    amount_str = ans_map.get(a_id)
                    unit_str = ans_map.get(u_id) or "Qty"
                    if not p_type or not amount_str: continue
                    
                    clean_p = p_type.replace('_', ' ').replace('-', ' ').title()
                    try:
                        val = float(amount_str.replace(',', '').split()[0])
                        key = (f"{clean_p} (Required Amount)", unit_str)
                        if key not in salt_pivot: salt_pivot[key] = []
                        salt_pivot[key].append(val)
                    except: pass

            # Convert pivot to explorer_data items
            for (label, unit), vals in salt_pivot.items():
                if not vals: continue
                v_sum = round(sum(vals), 1)
                explorer_data.append({
                    'id': 0, 'label': label,
                    'avg': round(v_sum / len(vals), 1),
                    'total_val': v_sum,
                    'sample_size': len(vals),
                    'unit': unit,
                    'type': 'decimal'
                })
            
            # Exclude IDs from standard loop
            explorer_qs = explorer_qs.exclude(id__in=all_q_ids)

        for q in explorer_qs:
            ans_qs = Answer.objects.filter(question=q, submission__in=submissions)
            count = ans_qs.count()
            if count == 0: continue

            if q.question_type == 'yes_no':
                yes_count = ans_qs.filter(value__iexact='yes').count()
                avg = round((yes_count / count) * 100, 1)
                total_sum = yes_count
                unit = "% Yes"
            else:
                vals = []
                for a in ans_qs:
                    try: vals.append(float(a.value.replace(',', '').split()[0]))
                    except (ValueError, AttributeError, IndexError): pass
                
                if vals:
                    avg = round(sum(vals)/len(vals), 1)
                    total_sum = round(sum(vals), 1)
                    unit = q.label.split('(')[-1].split(')')[0] if '(' in q.label else ""
                else:
                    avg = 0
                    total_sum = 0
                    unit = ""

            explorer_data.append({
                'id': q.id,
                'label': q.label,
                'avg': avg,
                'total_val': total_sum,
                'sample_size': count,
                'unit': unit,
                'type': q.question_type
            })
            
        # 4. Standard Metrics Cards (Quick Calcs)
        responses_count = submissions.count()
        factories_qs = Industry.objects.filter(category=selected_cat) if selected_cat else Industry.objects.all()
        factories_count = factories_qs.count()
        
        # Efficiency calculation
        total_eff = 0
        eff_count = 0
        risk_count = 0
        
        # Pre-calculate labels for stock calculation based on category
        stock_label = 'stock'
        if selected_cat and selected_cat.code == 'salt': stock_label = 'Potassium iodate'
        elif selected_cat and selected_cat.code == 'edible_oil': stock_label = 'Vitamin'

        for fact in factories_qs:
            f_subs = submissions.filter(organization=fact)
            if not f_subs.exists(): continue
            
            latest_sub = f_subs.order_by('-created_at').first()
            ans = latest_sub.answers.all()
            
            # Efficiency
            actual = next((a.value for a in ans if 'Actual' in a.question.label), "0")
            inst = next((a.value for a in ans if 'Installed' in a.question.label), "1")
            try:
                act_v = float(actual.replace(',', '').split()[0])
                inst_v = float(inst.replace(',', '').split()[0])
                eff = min(100, (act_v / inst_v) * 100) if inst_v > 0 else 0
                total_eff += eff
                eff_count += 1
            except: pass

            # Stock Days
            stock_ans = next((a.value for a in ans if stock_label in a.question.label), "0")
            try:
                s_val = float(stock_ans.replace(',', '').split()[0])
                stock_days = round(s_val * 1.5)
                if stock_days < 15: risk_count += 1
            except: pass

        # 5. Yes/No Summary
        yesno_summary = []
        yesno_qs = Question.objects.filter(section__form__category=selected_cat, question_type='yes_no')[:5] if selected_cat else Question.objects.none()
        for q in yesno_qs:
            y_ans = Answer.objects.filter(question=q, submission__in=submissions)
            y_count = y_ans.count()
            if y_count > 0:
                yes_p = round((y_ans.filter(value__iexact='yes').count() / y_count) * 100)
                yesno_summary.append({'label': q.hint or q.label, 'p': yes_p})

        # Industry metadata for filtering
        industries_metadata = []
        ind_qs = Industry.objects.all().select_related('category')
        if selected_cat:
            ind_qs = ind_qs.filter(category=selected_cat)
        
        for i in ind_qs:
            industries_metadata.append({
                'id': i.id,
                'name': i.name,
                'selected': i.id in industry_ids
            })

        context = {
            **self.each_context(request),
            'title': 'Strategic Data Explorer',
            'explorer_data': explorer_data,
            'selected_cat': selected_cat,
            'responses_count': responses_count,
            'factories_count': factories_count,
            'drill_down_q': drill_down_q,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'category_choices': [(c.code, c.name) for c in available_cats],
            'industries': industries_metadata,
            'selected_industry_ids': industry_ids,
            'avg_efficiency': round(total_eff / eff_count) if eff_count > 0 else 0,
            'factories_at_risk': risk_count,
            'yesno_summary': yesno_summary,
        }

        if request.headers.get('HX-Request') or request.GET.get('partial'):
            return render(request, 'admin/question_analytics_partial.html', context)
        return render(request, 'admin/question_analytics.html', context)

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

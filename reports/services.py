"""
reports/services.py

Dynamic Form Summary Report Engine.

Three classes:
  - QuestionReportAggregator   — computes per-question stats from Answer querysets
  - FormReportBuilder          — orchestrates form→section→question→aggregation into a report dict
  - PDFReportRenderer          — renders a FormReportBuilder output to a PDF BytesIO stream
"""

import io
import statistics
from collections import Counter
from datetime import datetime

from django.db.models import Q

from forms_builder.models import Form, Question, QuestionOption
from submissions.models import Answer, Submission


# ─── Aggregator ───────────────────────────────────────────────────────────────

class QuestionReportAggregator:
    """
    Aggregates Answer values for a single Question into a stats dict.
    Dispatches by question_type to the appropriate method.
    """

    CATEGORICAL_TYPES = {'select', 'yes_no', 'multiselect'}
    NUMERIC_TYPES = {'number', 'decimal'}
    TEXT_TYPES = {'text', 'textarea', 'phone', 'email'}
    MEDIA_TYPES = {'image', 'location'}

    def aggregate(self, question, answers_qs, total_submissions):
        """
        Main entry point. Returns a dict describing the aggregated results.
        """
        non_blank_answers = answers_qs.exclude(value='')
        answered_count = non_blank_answers.count()
        missing_count = total_submissions - answered_count

        base = {
            'question_id': question.id,
            'label': question.label,
            'type': question.question_type,
            'answered_count': answered_count,
            'missing_count': missing_count,
            'total_count': total_submissions,
        }

        qt = question.question_type

        if qt in self.CATEGORICAL_TYPES:
            base.update(self._agg_categorical(question, non_blank_answers))
        elif qt in self.NUMERIC_TYPES:
            base.update(self._agg_numeric(non_blank_answers))
        elif qt in self.TEXT_TYPES:
            base.update(self._agg_text(non_blank_answers))
        elif qt in self.MEDIA_TYPES:
            base.update(self._agg_media(answers_qs))
        else:
            base['raw_responses'] = list(non_blank_answers.values_list('value', flat=True)[:50])

        return base

    def _agg_categorical(self, question, answers_qs):
        """
        For select / yes_no / multiselect questions.
        Returns a sorted list of {label, value_key, count, percentage}.
        For multiselect, splits comma-separated values first.
        """
        options = {opt.value: opt.label for opt in question.options.all()}

        raw_values = list(answers_qs.values_list('value', flat=True))

        # multiselect: each answer may be "opt1,opt2,opt3"
        all_tokens = []
        if question.question_type == 'multiselect':
            for v in raw_values:
                all_tokens.extend([t.strip() for t in v.split(',') if t.strip()])
        else:
            all_tokens = [v.strip() for v in raw_values if v.strip()]

        counts = Counter(all_tokens)
        total = sum(counts.values()) or 1  # avoid division by zero

        choices = []
        # Show known options first (in defined order), then any unexpected values
        for value_key, label in options.items():
            count = counts.pop(value_key, 0)
            choices.append({
                'label': label,
                'value_key': value_key,
                'count': count,
                'percentage': round(count / total * 100, 2),
            })
        # Leftover (unexpected raw values — should be rare)
        for value_key, count in counts.items():
            choices.append({
                'label': value_key,
                'value_key': value_key,
                'count': count,
                'percentage': round(count / total * 100, 2),
            })

        choices.sort(key=lambda x: x['count'], reverse=True)
        return {'choices': choices}

    def _agg_numeric(self, answers_qs):
        """
        For number / decimal questions.
        Returns mean, median, mode, std_dev, min, max, sum.
        Matches KoboToolbox notation: uses '*' when stat is undefined.
        """
        raw = list(answers_qs.values_list('value', flat=True))
        parsed = []
        for v in raw:
            try:
                f = float(v)
                parsed.append(f)
            except (ValueError, TypeError):
                pass  # skip blanks and non-numeric junk

        if not parsed:
            return {
                'stats': {
                    'mean': '*', 'median': '*', 'mode': '*',
                    'std_dev': '*', 'min': '*', 'max': '*', 'sum': '*',
                    'valid_count': 0
                }
            }

        def fmt(v):
            return round(v, 2) if isinstance(v, float) else v

        try:
            mode_val = fmt(statistics.mode(parsed))
        except statistics.StatisticsError:
            mode_val = '*'

        try:
            std_dev = fmt(statistics.stdev(parsed)) if len(parsed) > 1 else '*'
        except statistics.StatisticsError:
            std_dev = '*'

        return {
            'stats': {
                'mean': fmt(statistics.mean(parsed)),
                'median': fmt(statistics.median(parsed)),
                'mode': mode_val,
                'std_dev': std_dev,
                'min': fmt(min(parsed)),
                'max': fmt(max(parsed)),
                'sum': fmt(sum(parsed)),
                'valid_count': len(parsed),
            }
        }

    def _agg_text(self, answers_qs):
        """
        For text / textarea / phone / email questions.
        Returns frequency-sorted unique values (top 50) + total unique count.
        """
        raw = list(answers_qs.values_list('value', flat=True))
        counts = Counter(v.strip() for v in raw if v.strip())
        top = [
            {'value': val, 'count': cnt}
            for val, cnt in counts.most_common(50)
        ]
        return {
            'text_responses': top,
            'unique_count': len(counts),
        }

    def _agg_media(self, answers_qs):
        """
        For image / location questions.
        Returns count of non-null uploads.
        """
        upload_count = answers_qs.filter(
            Q(image__isnull=False) | (~Q(value='') & Q(image__isnull=True))
        ).count()
        return {
            'upload_count': upload_count,
        }


# ─── Builder ──────────────────────────────────────────────────────────────────

class FormReportBuilder:
    """
    Orchestrates building a complete report dict for a given Form,
    optionally filtered by reporting period, industry, or category.
    """

    def build(self, form_id, period_id=None, industry_id=None, category_id=None):
        """
        Returns a structured report dict. Raises Form.DoesNotExist if form_id invalid.
        """
        form = Form.objects.get(pk=form_id)
        agg = QuestionReportAggregator()

        # ── Submission filter ──────────────────────────────────────────────
        sub_filter = Q(form=form, status=Submission.STATUS_SUBMITTED)
        filter_labels = []

        if period_id:
            sub_filter &= Q(period_id=period_id)
            from forms_builder.models import ReportingPeriod
            try:
                period = ReportingPeriod.objects.get(pk=period_id)
                filter_labels.append(f'Period: {period.label}')
            except ReportingPeriod.DoesNotExist:
                filter_labels.append(f'Period ID: {period_id}')

        if industry_id:
            sub_filter &= Q(organization_id=industry_id)
            from accounts.models import Industry
            try:
                ind = Industry.objects.get(pk=industry_id)
                filter_labels.append(f'Factory: {ind.name}')
            except Industry.DoesNotExist:
                filter_labels.append(f'Industry ID: {industry_id}')

        if category_id:
            sub_filter &= Q(organization__category_id=category_id)
            from accounts.models import Category
            try:
                cat = Category.objects.get(pk=category_id)
                filter_labels.append(f'Category: {cat.name}')
            except Category.DoesNotExist:
                filter_labels.append(f'Category ID: {category_id}')

        submissions = Submission.objects.filter(sub_filter)
        total_submissions = submissions.count()
        submission_ids = list(submissions.values_list('id', flat=True))

        # ── Build per-section, per-question results ────────────────────────
        sections_data = []
        for section in form.sections.all().prefetch_related(
            'questions', 'questions__options'
        ):
            questions_data = []
            for question in section.questions.all():
                answers_qs = Answer.objects.filter(
                    submission_id__in=submission_ids,
                    question=question,
                )
                q_data = agg.aggregate(question, answers_qs, total_submissions)
                questions_data.append(q_data)

            sections_data.append({
                'section_id': section.id,
                'title': section.title,
                'description': section.description,
                'questions': questions_data,
            })

        return {
            'form_id': form.id,
            'form_title': form.title,
            'category': form.category.name if form.category else None,
            'schedule_type': form.schedule_type,
            'generated_at': datetime.now().isoformat(),
            'total_submissions': total_submissions,
            'filters_applied': filter_labels if filter_labels else ['All submissions'],
            'sections': sections_data,
        }


# ─── PDF Renderer ─────────────────────────────────────────────────────────────

class PDFReportRenderer:
    """
    Renders a FormReportBuilder output dict to a PDF BytesIO stream
    using reportlab (already installed in this project).

    Layout matches KoboToolbox report style:
      - Page header: form title + generated date + automated-report disclaimer
      - Per section: bold section heading
      - Per question: label, type badge, response rate, then stats/choices/text
      - Footer: page X of Y
    """

    # Colours — match existing ExportCompliancePDFView palette
    HEADER_COLOR = '#2E5FA3'
    TABLE_HEADER_COLOR = '#4e73df'
    ALT_ROW_COLOR = '#F2F2F2'

    def render(self, report_data):
        """Returns a BytesIO containing the PDF bytes."""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable,
        )
        from reportlab.graphics.shapes import Rect, String, Line, Drawing

        from reportlab.lib.enums import TA_LEFT, TA_CENTER

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=1.5 * cm,
            rightMargin=1.5 * cm,
            topMargin=2.0 * cm,
            bottomMargin=2.0 * cm,
        )

        styles = getSampleStyleSheet()
        W = A4[0] - 3 * cm  # usable width

        # Custom styles
        title_style = ParagraphStyle(
            'ReportTitle', parent=styles['Title'],
            fontSize=16, spaceAfter=4,
            textColor=colors.HexColor(self.HEADER_COLOR),
        )
        subtitle_style = ParagraphStyle(
            'Subtitle', parent=styles['Normal'],
            fontSize=8, textColor=colors.grey, spaceAfter=12,
        )
        disclaimer_style = ParagraphStyle(
            'Disclaimer', parent=styles['Italic'],
            fontSize=7.5, textColor=colors.HexColor('#888888'), spaceAfter=16,
        )
        section_style = ParagraphStyle(
            'SectionHeading', parent=styles['Heading2'],
            fontSize=12, textColor=colors.HexColor(self.HEADER_COLOR),
            spaceBefore=14, spaceAfter=4,
        )
        q_label_style = ParagraphStyle(
            'QuestionLabel', parent=styles['Normal'],
            fontSize=10, fontName='Helvetica-Bold',
            spaceBefore=10, spaceAfter=2,
        )
        q_meta_style = ParagraphStyle(
            'QuestionMeta', parent=styles['Normal'],
            fontSize=8, textColor=colors.grey, spaceAfter=6,
        )
        normal = styles['Normal']

        header_color = colors.HexColor(self.TABLE_HEADER_COLOR)
        alt_color    = colors.HexColor(self.ALT_ROW_COLOR)

        # KoboToolbox palette — one color per bar
        BAR_COLORS = [
            '#4472C4','#E8734A','#F4BE00','#70AD47','#44A4C4',
            '#FF8C00','#9B59B6','#1ABC9C','#E74C3C','#3498DB',
            '#F39C12','#2ECC71','#E91E63','#00BCD4','#8BC34A',
        ]

        def make_bar_chart(choices, chart_width=None, q_type='select'):
            """
            Draws a KoboToolbox-style bar chart as a reportlab Drawing.
            - SELECT_ONE / yes_no  -> horizontal bars
            - SELECT_MULTIPLE     -> vertical bars
            Only includes choices with count > 0.
            """
            active = [c for c in choices if c['count'] > 0]
            if not active:
                return None

            cw = chart_width or float(W)

            if q_type == 'multiselect':
                # Vertical bar chart
                n = len(active)
                bar_w = min(40, max(18, (cw - 60) / n))
                chart_h = 160.0
                pad_left = 40.0
                pad_bottom = 50.0
                total_w = pad_left + n * bar_w * 1.4 + 20
                d = Drawing(total_w, chart_h + pad_bottom)

                max_val = max(c['count'] for c in active) or 1
                scale = (chart_h - 30) / max_val

                # Y-axis grid lines + labels
                steps = min(5, max_val)
                for i in range(steps + 1):
                    y_val = int(max_val * i / steps)
                    y_pos = pad_bottom + y_val * scale
                    d.add(Line(pad_left - 4, y_pos, total_w - 10, y_pos,
                               strokeColor=colors.HexColor('#DDDDDD'), strokeWidth=0.4))
                    d.add(String(pad_left - 6, y_pos - 3, str(y_val),
                                 fontSize=6, textAnchor='end',
                                 fillColor=colors.HexColor('#666666')))

                for i, choice in enumerate(active):
                    x = pad_left + i * bar_w * 1.4
                    h = choice['count'] * scale
                    c = colors.HexColor(BAR_COLORS[i % len(BAR_COLORS)])
                    d.add(Rect(x, pad_bottom, bar_w, h, fillColor=c, strokeColor=colors.white, strokeWidth=0.5))
                    # count label above bar
                    d.add(String(x + bar_w / 2, pad_bottom + h + 2, str(choice['count']),
                                 fontSize=6, textAnchor='middle', fillColor=colors.HexColor('#333333')))
                    # x label (truncated, rotated)
                    lbl = choice['label'][:14] + ('…' if len(choice['label']) > 14 else '')
                    # draw rotated label manually as angled string
                    from reportlab.graphics.shapes import String as GString
                    s = GString(x + bar_w / 2, pad_bottom - 4, lbl)
                    s.fontSize = 6
                    s.textAnchor = 'end'
                    s.fillColor = colors.HexColor('#333333')
                    import math
                    d.add(s)
                return d

            else:
                # Horizontal bar chart (SELECT_ONE / yes_no)
                bar_h = 14.0
                gap   = 5.0
                pad_left   = 130.0  # space for labels
                pad_right  = 50.0   # space for count+% text
                chart_area  = cw - pad_left - pad_right
                n = len(active)
                drawing_h = n * (bar_h + gap) + 24

                d = Drawing(cw, drawing_h)
                max_val = max(c['count'] for c in active) or 1

                # Light vertical grid lines
                for tick in range(0, int(max_val) + 2, max(1, int(max_val // 4))):
                    x = pad_left + tick / max_val * chart_area
                    d.add(Line(x, 0, x, drawing_h - 16,
                               strokeColor=colors.HexColor('#EEEEEE'), strokeWidth=0.5))
                    d.add(String(x, drawing_h - 14, str(tick),
                                 fontSize=5.5, textAnchor='middle',
                                 fillColor=colors.HexColor('#999999')))

                for i, choice in enumerate(active):
                    y = drawing_h - 20 - i * (bar_h + gap)
                    bar_len = choice['count'] / max_val * chart_area
                    c = colors.HexColor(BAR_COLORS[i % len(BAR_COLORS)])

                    # Label on left
                    lbl = choice['label']
                    if len(lbl) > 22:
                        lbl = lbl[:20] + '…'
                    d.add(String(pad_left - 4, y + 2, lbl,
                                 fontSize=7, textAnchor='end',
                                 fillColor=colors.HexColor('#333333')))

                    # Bar
                    d.add(Rect(pad_left, y, bar_len, bar_h,
                               fillColor=c, strokeColor=colors.white, strokeWidth=0.3))

                    # Count + pct on right
                    d.add(String(pad_left + bar_len + 4, y + 2,
                                 f"{choice['count']} ({choice['percentage']}%)",
                                 fontSize=6.5, textAnchor='start',
                                 fillColor=colors.HexColor('#555555')))
                return d

        def make_freq_table(rows, col_widths=None):
            """Builds a frequency/percentage table."""
            header = [['Value / Option', 'Count', '%']]
            data = header + [[r['label'], r['count'], f"{r['percentage']}%"] for r in rows]
            col_w = col_widths or [W * 0.65, W * 0.15, W * 0.20]
            t = Table(data, colWidths=col_w, repeatRows=1)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), header_color),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, alt_color]),
                ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CCCCCC')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
            ]))
            return t

        def make_stats_table(stats):
            """Builds a 4-column KoboToolbox-style stats table: Mean / Median / Mode / Std Dev."""
            headers = ['Mean', 'Median', 'Mode', 'Standard deviation']
            values  = [
                str(stats.get('mean', '*')),
                str(stats.get('median', '*')),
                str(stats.get('mode', '*')),
                str(stats.get('std_dev', '*')),
            ]
            data  = [headers, values]
            col_w = [W / 4] * 4
            t = Table(data, colWidths=col_w)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('BACKGROUND', (0, 1), (-1, 1), alt_color),
                ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CCCCCC')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
            ]))
            return t

        # ── Page numbering ─────────────────────────────────────────────────
        def on_later_pages(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 7)
            canvas.setFillColor(colors.grey)
            canvas.drawRightString(A4[0] - 1.5 * cm, 1.0 * cm, f'Page {doc.page}')
            canvas.drawCentredString(
                A4[0] / 2, 1.0 * cm,
                'Monthly collected data from food processing factories | FF-IMS'
            )
            canvas.restoreState()

        # ── Assemble elements ──────────────────────────────────────────────
        elements = []

        elements.append(Paragraph(report_data['form_title'], title_style))
        elements.append(Paragraph(
            f"Generated: {report_data['generated_at'][:19].replace('T', ' ')}  |  "
            f"Total Submissions: {report_data['total_submissions']}  |  "
            f"Filters: {', '.join(report_data['filters_applied'])}",
            subtitle_style,
        ))
        elements.append(Paragraph(
            "This is an automated report based on raw data submitted to this project. "
            "Please conduct proper data cleaning prior to using the figures on this page.",
            disclaimer_style,
        ))
        elements.append(HRFlowable(width=W, thickness=0.5, color=colors.HexColor('#CCCCCC')))

        TYPE_LABELS = {
            'select': 'SELECT_ONE', 'multiselect': 'SELECT_MULTIPLE',
            'number': 'INTEGER', 'decimal': 'DECIMAL',
            'text': 'TEXT', 'textarea': 'TEXT', 'yes_no': 'SELECT_ONE',
            'image': 'IMAGE', 'phone': 'TEXT', 'email': 'TEXT',
            'location': 'LOCATION', 'date': 'DATE',
        }

        for section in report_data['sections']:
            elements.append(Paragraph(section['title'], section_style))
            if section.get('description'):
                elements.append(Paragraph(section['description'], subtitle_style))

            for q in section['questions']:
                type_badge = TYPE_LABELS.get(q['type'], q['type'].upper())
                answered   = q['answered_count']
                total      = q['total_count']
                missing    = q['missing_count']

                elements.append(Paragraph(q['label'], q_label_style))
                elements.append(Paragraph(
                    f"TYPE: {type_badge}. {answered} out of {total} respondents answered this question. "
                    f"({missing} were without data.)",
                    q_meta_style,
                ))

                # Categorical — bar chart + frequency table
                if q.get('choices') and answered > 0:
                    chart = make_bar_chart(q['choices'], chart_width=float(W), q_type=q['type'])
                    if chart:
                        elements.append(chart)
                        elements.append(Spacer(1, 6))
                    active_choices = [c for c in q['choices'] if c['count'] > 0]
                    if active_choices:
                        elements.append(make_freq_table(active_choices))
                        elements.append(Spacer(1, 8))

                # Numeric — 4-column stats table
                if q.get('stats') and q['stats'].get('valid_count', 0) > 0:
                    elements.append(make_stats_table(q['stats']))
                    elements.append(Spacer(1, 8))

                # Text responses
                if q.get('text_responses') and q['text_responses']:
                    rows = [
                        {'label': r['value'], 'count': r['count'],
                         'percentage': round(r['count'] / answered * 100, 2) if answered else 0}
                        for r in q['text_responses']
                    ]
                    elements.append(make_freq_table(rows, col_widths=[W * 0.70, W * 0.15, W * 0.15]))
                    elements.append(Spacer(1, 8))

                # Image/media
                if 'upload_count' in q:
                    elements.append(Paragraph(f"Total uploads: {q['upload_count']}", normal))
                    elements.append(Spacer(1, 6))

        doc.build(elements, onFirstPage=on_later_pages, onLaterPages=on_later_pages)
        buf.seek(0)
        return buf


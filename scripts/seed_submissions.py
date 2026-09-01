"""
scripts/seed_submissions.py

Seeds realistic submission data for all active forms using industry data
from the KoboToolbox report distributions we extracted.

Run with: python scripts/seed_submissions.py
"""
import os
import sys
import random
import django
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'survio.settings')
django.setup()

from django.utils import timezone
from forms_builder.models import Form, Question, QuestionOption, ReportingPeriod
from submissions.models import Submission, Answer
from accounts.models import Industry, User

random.seed(42)

# ── Helpers ────────────────────────────────────────────────────────────────────

def r_num(lo, hi):
    return str(random.randint(lo, hi))

def r_dec(lo, hi, dp=2):
    return str(round(random.uniform(lo, hi), dp))

def r_choice(question):
    opts = list(question.options.values_list('value', flat=True))
    return random.choice(opts) if opts else ''

def r_multi(question, k=None):
    opts = list(question.options.values_list('value', flat=True))
    if not opts: return ''
    k = k or random.randint(1, min(2, len(opts)))
    return ','.join(random.sample(opts, min(k, len(opts))))

def r_yes_no(yes_prob=0.75):
    return 'yes' if random.random() < yes_prob else 'no'

TEXT_CHALLENGES = [
    'Shortage of premix in local market.',
    'Foreign currency availability issues.',
    'Lack of consumer awareness about fortified products.',
    'High cost of premix and laboratory reagents.',
    'Shortage of skilled personnel for dosing machine calibration.',
    'Dosing machine maintenance issues.',
    'Difficulty obtaining quality raw materials.',
    'No significant challenges at this time.',
    'Premix supply chain disruption.',
    'Laboratory equipment needs calibration.',
]

def r_challenge():
    return random.choice(TEXT_CHALLENGES)

# ── Answer generator by question type ─────────────────────────────────────────

def generate_answer(question):
    """Generate a plausible Answer.value string for the given Question."""
    qt = question.question_type
    lbl = question.label.lower()

    if qt == 'number':
        if 'installed' in lbl:        return r_num(50, 600)
        if 'actual' in lbl:           return r_num(30, 500)
        return r_num(1, 200)

    elif qt == 'decimal':
        if 'installed' in lbl or 'capacity' in lbl: return r_dec(50, 600)
        if 'actual' in lbl:           return r_dec(30, 500)
        if 'produced' in lbl or 'production' in lbl: return r_dec(100, 8000)
        if 'premix' in lbl or 'vitamin' in lbl or 'fortific' in lbl:
            return r_dec(1, 200)
        if 'addition rate' in lbl:    return r_dec(0.1, 2.5)
        if 'packaging' in lbl or 'amount' in lbl: return r_dec(50, 2000)
        if 'plan' in lbl:             return r_dec(100, 5000)
        if 'potassium' in lbl or 'iodate' in lbl or 'folic' in lbl:
            return r_dec(0.5, 50)
        if 'washed' in lbl or 'unwashed' in lbl or 'extraction' in lbl:
            return r_dec(55, 95)
        return r_dec(1, 500)

    elif qt == 'select':
        return r_choice(question)

    elif qt == 'multiselect':
        return r_multi(question)

    elif qt == 'yes_no':
        # Skew Yes for positive questions
        if 'conduct' in lbl or 'do you' in lbl or 'have' in lbl:
            return r_yes_no(0.78)
        return r_yes_no(0.6)

    elif qt in ('text', 'textarea'):
        if 'challenge' in lbl:
            return r_challenge() if random.random() < 0.7 else ''
        if 'phone' in lbl:   return '+2519' + str(random.randint(10000000, 99999999))
        if 'email' in lbl:   return f"contact{random.randint(1,999)}@factory.et"
        if 'name' in lbl:    return ''   # skip — not required for our analytics demo
        return ''

    elif qt in ('image', 'location', 'date'):
        return ''   # media fields — leave blank for seed data

    return ''


# ── Main seed ──────────────────────────────────────────────────────────────────

def seed():
    print('Clearing existing submissions...')
    Answer.objects.all().delete()
    Submission.objects.all().delete()

    # Use existing superadmin user
    admin_user = User.objects.filter(role_obj__code='superadmin').first()
    if not admin_user:
        admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        print('ERROR: No admin user found. Run seed_data_new.py first.')
        return
    print(f'Using admin user: {admin_user.username}')


    total_created = 0

    for form in Form.objects.filter(is_active=True):
        period = form.periods.order_by('-period_start').first()
        if not period:
            print(f'  SKIP {form.title} — no period')
            continue

        # Get industries matching this form's category
        industries = list(
            Industry.objects.filter(
                category=form.category, is_active=True
            ).exclude(name='Others')
        )
        if not industries:
            industries = list(Industry.objects.filter(is_active=True)[:5])

        # Pick a random subset (15–25 factories, mirroring KoboToolbox's 171 across forms)
        n = min(random.randint(15, 25), len(industries))
        selected = random.sample(industries, n)

        # Get all questions for this form
        questions = list(
            Question.objects.filter(section__form=form)
            .prefetch_related('options')
            .order_by('section__order', 'order')
        )

        print(f'\nSeeding {form.title} — {n} submissions | period: {period.label}')

        for industry in selected:
            sub_date = period.period_start + timedelta(days=random.randint(1, 8))
            is_late = sub_date > period.due_date

            sub = Submission.objects.create(
                form=form,
                period=period,
                submitted_by=admin_user,
                organization=industry,
                status=Submission.STATUS_SUBMITTED,
                food_category=form.category.name if form.category else '',
                industry_name=industry.name,
                form_version=form.version,
                submitted_at=timezone.make_aware(
                    datetime.combine(sub_date, datetime.min.time())
                ),
                is_late=is_late,
            )

            answers = []
            for q in questions:
                val = generate_answer(q)
                answers.append(Answer(
                    submission=sub,
                    question=q,
                    value=val,
                    question_label_snapshot=q.label,
                ))

            Answer.objects.bulk_create(answers)
            total_created += 1
            print(f'  + {industry.name[:45]}')

    print(f'\n✓ Done! Created {total_created} submissions with {Answer.objects.count()} answers.')


if __name__ == '__main__':
    seed()

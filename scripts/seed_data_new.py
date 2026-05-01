import os
import django
import sys
import re
from datetime import date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'survio.settings')
django.setup()

from accounts.models import Industry, Category, User, Role
from forms_builder.models import Form, Section, Question, QuestionOption, ReportingPeriod


def seed_data():
    print("Clearing old form data...")
    ReportingPeriod.objects.all().delete()
    Form.objects.all().delete()
    Section.objects.all().delete()
    Question.objects.all().delete()

    # We DO NOT delete Industry and Category so existing users keep their FK relationships.

    print("Seeding roles...")
    Role.objects.update_or_create(code='superadmin', defaults={
        'name': 'Super Admin',
        'description': 'Global system administrator. Full access to all data, settings, and users.'
    })
    Role.objects.update_or_create(code='admin', defaults={
        'name': 'Admin',
        'description': 'Organization-level administrator. Can view and manage forms and submissions.'
    })
    Role.objects.update_or_create(code='companyuser', defaults={
        'name': 'Company User',
        'description': 'Standard factory user. Can submit forms assigned to their industry.'
    })

    print("Seeding categories...")
    cats = {
        'edible_oil':   Category.objects.get_or_create(name='Edible Oil',   code='edible_oil')[0],
        'wheat_flour':  Category.objects.get_or_create(name='Wheat Flour',  code='wheat_flour')[0],
        'salt':         Category.objects.get_or_create(name='Salt',          code='salt')[0],
        'maize_flour':  Category.objects.get_or_create(name='Maize Flour',  code='maize_flour')[0],
        'csb_plus':     Category.objects.get_or_create(name='CSB+',         code='csb_plus')[0],
    }

    print("Seeding industries...")

    def seed_industries(prefix, names, cat_key):
        for name in names:
            code = (prefix + re.sub(r'[^a-zA-Z0-9_]', '', name.lower().replace(' ', '_')))[:50]
            Industry.objects.update_or_create(code=code, defaults={'name': name, 'category': cats[cat_key]})

    seed_industries('oil_', [
        "Health care edible oil factory", "Abay Edible oil factory", "Addis Mojo edible oil factory",
        "Alimpex plc", "Articraft industrial plc", "BBZ edible oil factory", "Emmy edible oil factory",
        "Giftii foods and packaging plc", "Hamaresa edible oil factory", "Hava industrial Plc", "Jerr PLC",
        "Kokeb kana edible oil", "Kunifira Agro processing plc", "Leos edible oil factory",
        "Mulu Work Gebeyehu Edible oil Factory", "Phebila industrial plc",
        "Rich Land Biochemical Production Plc.", "Ronge Ethiopia edible oil factory",
        "Selagoja edible oil factory", "Shemu Plc", "Tasty edible oil factory",
        "Unity edible oil factory", "W.A edible oil factory", "Yayirate edible oil factory", "Others"
    ], 'edible_oil')

    seed_industries('flour_', [
        "K.O.J.J Food Complex", "Addis Dallas Industries Plc.", "Admas Flour factory", "Africa plc",
        "AH-WAN PLC", "Alihenan Food Complex", "Alpha food complex", "Alvima food complex",
        "Chilalo food complex", "DH Geda", "Dina Food processing", "Diredawa food complex",
        "Echa Food Complex", "Eshet Food Complex", "Fiker Food processing",
        "Gonde Adama Food complex", "Hawassa Flour Factory", "Hora food complex",
        "Kality Food share company", "Kombolcha flour factory", "Misrak Flour factory",
        "Modjo flour factory", "Nefas silk food complex", "Omer Awad flour factory",
        "Shoa Flour Factory", "Others"
    ], 'wheat_flour')

    seed_industries('salt_', [
        "Ella Trading", "Green Star Trading PLC", "Ibex Waliya Salt Production",
        "Mesob Salt Production", "Nurmaso Salt Production PLC", "Sodaking salt processing PLC",
        "Sali Salt", "Afar Salt Share Company", "Berhale salt factory", "Dobi salt refinery",
        "Duda salt factory", "Hina Salt refinery", "Kala salt refinery", "Laki salt refinery",
        "Saba salt refinery", "Salit Salt factory", "Others"
    ], 'salt')

    seed_industries('maize_', ["Others"], 'maize_flour')
    seed_industries('csb_',   ["Others"], 'csb_plus')

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def make_form(title, cat_key):
        today = date.today()
        form = Form.objects.create(
            title=title,
            category=cats[cat_key],
            schedule_type='monthly',
            opens_on_day=1,
            due_on_day=10,
            closes_on_day=15,
        )
        ReportingPeriod.objects.create(
            form=form,
            label=today.strftime('%B %Y'),
            period_start=date(today.year, today.month, 1),
            period_end=date(today.year, today.month, 28),
            due_date=date(today.year, today.month, 10),
            close_date=date(today.year, today.month, 15),
        )
        return form

    def yesno(q):
        QuestionOption.objects.create(question=q, label="Yes", value="yes", order=1)
        QuestionOption.objects.create(question=q, label="No",  value="no",  order=2)

    def opts(q, items):
        """items: list of (label, value) tuples"""
        for i, (label, value) in enumerate(items):
            QuestionOption.objects.create(question=q, label=label, value=value, order=i)

    # ─── FORM I: Wheat Flour ───────────────────────────────────────────────────
    print("Creating Wheat Flour Checklist...")
    f = make_form("Wheat Flour Checklist", 'wheat_flour')

    s = Section.objects.create(form=f, title="Production Data", order=1)
    for i, (label, qt) in enumerate([
        ("Installed Production Capacity (ton/day)",               "number"),
        ("Actual Production Capacity (ton/day)",                  "number"),
        ("Amount Fortified Flour Produced (ton/month)",           "decimal"),
        ("Amount of Premix Purchased in the last month (kg/month)", "decimal"),
        ("Amount of Premix Utilized (kg/month)",                  "decimal"),
        ("Amount of Premix Available in Store (kg)",              "decimal"),
    ], 1):
        Question.objects.create(section=s, label=label, question_type=qt, is_required=True, order=i)

    s = Section.objects.create(form=f, title="Packaging", order=2)
    q = Question.objects.create(section=s, label="Final Product Packaging Material Type", question_type='select', order=1)
    opts(q, [
        ("Polypropylene bag with food grade inner", "pp_food_grade"),
        ("Polypropylene bag",                        "pp_bag"),
        ("Laminated paper bag (kg/month)",           "laminated_paper"),
        ("Poly Ethylene Teraphetalet (PET) (kg/month)", "pet"),
        ("Other (kg/month)",                         "other"),
    ])
    Question.objects.create(section=s, label="Amount (kg/month)", question_type='decimal', order=2)

    s = Section.objects.create(form=f, title="Fortification Technology", order=3)
    q = Question.objects.create(section=s, label="Type of Technology used for Wheat Flour Fortification", question_type='select', order=1)
    opts(q, [
        ("Continuous (Micro feeder and screw conveyor)", "continuous"),
        ("Batch Mixer",                                  "batch"),
    ])

    s = Section.objects.create(form=f, title="Quality Assurance & Compliance", order=4)
    q5 = Question.objects.create(section=s, label="Do you Conduct Fortification Lab Analysis?", question_type='yes_no', order=1)
    yesno(q5)
    q6 = Question.objects.create(section=s, label="Do you conduct third party laboratory test result?", question_type='yes_no', order=2)
    yesno(q6)
    Question.objects.create(section=s, label="Upload third party lab test result (photo)", question_type='image', depends_on=q6, depends_on_value="yes", order=3)
    q7 = Question.objects.create(section=s, label="Do you conduct dosing machine calibration?", question_type='yes_no', order=4)
    yesno(q7)
    Question.objects.create(section=s, label="Upload dosing machine calibration record (photo)", question_type='image', depends_on=q7, depends_on_value="yes", order=5)
    q8 = Question.objects.create(section=s, label="Did you conduct monthly premix reconciliation?", question_type='yes_no', order=6)
    yesno(q8)
    Question.objects.create(section=s, label="If yes, what is the actual addition rate per ton?", question_type='decimal', depends_on=q8, depends_on_value="yes", order=7)
    q10 = Question.objects.create(section=s, label="Do you Conduct Induction Training?", question_type='yes_no', order=8)
    yesno(q10)

    s = Section.objects.create(form=f, title="Next Month Plan", order=5)
    Question.objects.create(section=s, label="Plan to Produce Fortified Wheat Flour for the next month (ton/month)", question_type='decimal', order=1)
    Question.objects.create(section=s, label="Amount of Premix to be utilized for the next month (kg/month)",        question_type='decimal', order=2)
    Question.objects.create(section=s, label="Challenges related to Food Fortification?",                             question_type='textarea', order=3)

    # ─── FORM II: Edible Oil ──────────────────────────────────────────────────
    print("Creating Edible Oil Checklist...")
    f = make_form("Edible Oil Checklist", 'edible_oil')

    s = Section.objects.create(form=f, title="Production Data", order=1)
    for i, (label, qt) in enumerate([
        ("Installed Production Capacity (ton/day)",                     "number"),
        ("Actual Production Capacity (ton/day)",                        "number"),
        ("Amount Produced Fortified Edible Oil (ton/month)",            "decimal"),
        ("Amount of Vitamin A & D Purchased in the last One month",     "decimal"),
        ("Amount of Vitamin A & D Utilized (kg/month)",                 "decimal"),
        ("Amount of Vitamin A & D Available in Store (kg)",             "decimal"),
    ], 1):
        Question.objects.create(section=s, label=label, question_type=qt, is_required=True, order=i)

    s = Section.objects.create(form=f, title="Packaging", order=2)
    q = Question.objects.create(section=s, label="Edible Oil Packaging Material Type", question_type='select', order=1)
    opts(q, [
        ("Polypropylene bag with food grade inner", "pp_food_grade"),
        ("Polypropylene bag",                        "pp_bag"),
        ("Laminated paper bag (kg/month)",           "laminated_paper"),
        ("Poly Ethylene Teraphetalet (PET) (kg/month)", "pet"),
        ("Other (kg/month)",                         "other"),
    ])
    Question.objects.create(section=s, label="Amount (kg/month)", question_type='decimal', order=2)

    s = Section.objects.create(form=f, title="Fortification Technology", order=3)
    q = Question.objects.create(section=s, label="Type of Technology used for Edible Oil Fortification", question_type='select', order=1)
    opts(q, [
        ("Continuous (Micro feeder and screw conveyor)", "continuous"),
        ("Batch Mixer",                                  "batch"),
        ("Two Stage",                                    "two_stage"),
    ])

    s = Section.objects.create(form=f, title="Quality Assurance & Compliance", order=4)
    q_skilled = Question.objects.create(section=s, label="Do you have skilled personnel to conduct edible oil fortification production?", question_type='yes_no', order=1)
    yesno(q_skilled)
    q_lab = Question.objects.create(section=s, label="Do you Conduct FF Lab Analysis?", question_type='yes_no', order=2)
    yesno(q_lab)
    q_method = Question.objects.create(section=s, label="What methods of Lab Analysis in practices for fortified edible oil?", question_type='multiselect', order=3)
    opts(q_method, [
        ("Qualitative",      "qualitative"),
        ("Semi-qualitative", "semi_qualitative"),
        ("Quantitative",     "quantitative"),
        ("All",              "all"),
    ])
    q_rec = Question.objects.create(section=s, label="Did you conduct monthly premix reconciliation?", question_type='yes_no', order=4)
    yesno(q_rec)
    Question.objects.create(section=s, label="If yes, what is the actual addition rate per ton?", question_type='decimal', depends_on=q_rec, depends_on_value="yes", order=5)
    q_train = Question.objects.create(section=s, label="Do you Conduct Induction Training FF?", question_type='yes_no', order=6)
    yesno(q_train)

    s = Section.objects.create(form=f, title="Next Month Plan", order=5)
    Question.objects.create(section=s, label="Plan to Produce Fortified Edible Oil for the next month (ton/month)", question_type='decimal', order=1)
    Question.objects.create(section=s, label="Amount of Fortificant to be utilized for the next month (kg/month)",  question_type='decimal', order=2)
    Question.objects.create(section=s, label="Challenges related to Food Fortification?",                            question_type='textarea', order=3)

    # ─── FORM III: Salt (DFS-IoFA) ────────────────────────────────────────────
    print("Creating Salt (DFS-IoFA) Checklist...")
    f = make_form("Salt (DFS-IoFA) Checklist", 'salt')

    s = Section.objects.create(form=f, title="Product Type", order=1)
    q = Question.objects.create(section=s, label="Select Product Type", question_type='select', is_required=True, order=1)
    opts(q, [
        ("Table Salt",              "table_salt"),
        ("Non-iodized Salt",        "non_iodized"),
        ("Lick Salt (Animal feed)", "lick_salt"),
        ("Other, Specify",          "other"),
    ])

    s = Section.objects.create(form=f, title="Production Capacity", order=2)
    for i, label in enumerate(["Installed Ton per Hour", "Max. Attained Ton per Hour", "Actual Ton per Hour"], 1):
        Question.objects.create(section=s, label=label, question_type='decimal', is_required=True, order=i)

    s = Section.objects.create(form=f, title="Packaging Materials", order=3)
    q = Question.objects.create(section=s, label="Type of Packaging Materials and Amount? (Multiple Response)", question_type='multiselect', order=1)
    opts(q, [
        ("High Density Ethylene (HDPE)",        "hdpe"),
        ("Poly Ethylene",                        "poly_ethylene"),
        ("Polypropylene bag (PP bag)",           "pp_bag"),
        ("Low Density Polyethylene (LDPE)",      "ldpe"),
        ("Paper",                                "paper"),
        ("Carton",                               "carton"),
        ("Plastic Jar",                          "plastic_jar"),
        ("Other, Specify",                       "other"),
    ])
    Question.objects.create(section=s, label="Amount of packaging used this month (Kg, Ton or Quintal)", question_type='decimal', order=2)

    s = Section.objects.create(form=f, title="Salt Processing", order=4)
    Question.objects.create(section=s, label="Washed Salt (Extraction rate %)",   question_type='decimal', order=1)
    Question.objects.create(section=s, label="Unwashed Salt (Extraction rate %)", question_type='decimal', order=2)

    s = Section.objects.create(form=f, title="Inputs Used for Salt Processing (per day)", order=5)
    Question.objects.create(section=s, label="Potassium Iodate (Kg)", question_type='decimal', order=1)
    Question.objects.create(section=s, label="Folic Acid (Kg)",       question_type='decimal', order=2)

    s = Section.objects.create(form=f, title="Quality Analysis", order=6)
    q_rec_salt = Question.objects.create(section=s, label="Did you conduct monthly premix reconciliation?", question_type='yes_no', order=1)
    yesno(q_rec_salt)

    q_iodine_method = Question.objects.create(section=s, label="What methods of Lab Analysis in practices for salt iodine content?", question_type='multiselect', order=2)
    opts(q_iodine_method, [
        ("Titration", "titration"),
        ("WYD",       "wyd"),
        ("Both",      "both"),
    ])

    q_folic_method = Question.objects.create(section=s, label="What methods of Lab Analysis in practices for salt folic acid content?", question_type='multiselect', order=3)
    opts(q_folic_method, [
        ("HPL",                          "hpl"),
        ("Microbiological Rapid Test Kit", "microbiological_rapid"),
        ("Liquid Chromatography",        "liquid_chromatography"),
        ("Spectrophotometer",            "spectrophotometer"),
        ("Other specify",                "other"),
    ])

    q_rec_folic = Question.objects.create(section=s, label="Did you conduct monthly premix reconciliation (Folic Acid)?", question_type='yes_no', order=4)
    yesno(q_rec_folic)

    Question.objects.create(section=s, label="Addition rate of Potassium Iodate per day of salt in Quintals", question_type='decimal', order=5)
    Question.objects.create(section=s, label="Addition rate of Folic Acid per day of salt in Quintals",       question_type='decimal', order=6)

    q_outsource = Question.objects.create(section=s, label="Does the Company outsource quality Analysis?", question_type='yes_no', order=7)
    yesno(q_outsource)

    Question.objects.create(section=s, label="Challenges related to Food Fortification?", question_type='textarea', order=8)

    # ─── FORM IV: Maize Flour (same structure as Wheat Flour) ─────────────────
    print("Creating Maize Flour Checklist...")
    f = make_form("Maize Flour Checklist", 'maize_flour')

    s = Section.objects.create(form=f, title="Production Data", order=1)
    for i, (label, qt) in enumerate([
        ("Installed Production Capacity (ton/day)",               "number"),
        ("Actual Production Capacity (ton/day)",                  "number"),
        ("Amount Fortified Flour Produced (ton/month)",           "decimal"),
        ("Amount of Premix Purchased in the last month (kg/month)", "decimal"),
        ("Amount of Premix Utilized (kg/month)",                  "decimal"),
        ("Amount of Premix Available in Store (kg)",              "decimal"),
    ], 1):
        Question.objects.create(section=s, label=label, question_type=qt, is_required=True, order=i)

    s = Section.objects.create(form=f, title="Packaging", order=2)
    q = Question.objects.create(section=s, label="Final Product Packaging Material Type", question_type='select', order=1)
    opts(q, [
        ("Polypropylene bag with food grade inner", "pp_food_grade"),
        ("Polypropylene bag",                        "pp_bag"),
        ("Laminated paper bag (kg/month)",           "laminated_paper"),
        ("Poly Ethylene Teraphetalet (PET) (kg/month)", "pet"),
        ("Other (kg/month)",                         "other"),
    ])
    Question.objects.create(section=s, label="Amount (kg/month)", question_type='decimal', order=2)

    s = Section.objects.create(form=f, title="Fortification Technology", order=3)
    q = Question.objects.create(section=s, label="Type of Technology used for Maize Flour Fortification", question_type='select', order=1)
    opts(q, [
        ("Continuous (Micro feeder and screw conveyor)", "continuous"),
        ("Batch Mixer",                                  "batch"),
    ])

    s = Section.objects.create(form=f, title="Quality Assurance & Compliance", order=4)
    q5 = Question.objects.create(section=s, label="Do you Conduct Fortification Lab Analysis?", question_type='yes_no', order=1)
    yesno(q5)
    q6 = Question.objects.create(section=s, label="Do you conduct third party laboratory test result?", question_type='yes_no', order=2)
    yesno(q6)
    Question.objects.create(section=s, label="Upload third party lab test result (photo)", question_type='image', depends_on=q6, depends_on_value="yes", order=3)
    q7 = Question.objects.create(section=s, label="Do you conduct dosing machine calibration?", question_type='yes_no', order=4)
    yesno(q7)
    Question.objects.create(section=s, label="Upload dosing machine calibration record (photo)", question_type='image', depends_on=q7, depends_on_value="yes", order=5)
    q8 = Question.objects.create(section=s, label="Did you conduct monthly premix reconciliation?", question_type='yes_no', order=6)
    yesno(q8)
    Question.objects.create(section=s, label="If yes, what is the actual addition rate per ton?", question_type='decimal', depends_on=q8, depends_on_value="yes", order=7)
    q10 = Question.objects.create(section=s, label="Do you Conduct Induction Training?", question_type='yes_no', order=8)
    yesno(q10)

    s = Section.objects.create(form=f, title="Next Month Plan", order=5)
    Question.objects.create(section=s, label="Plan to Produce Fortified Maize Flour for the next month (ton/month)", question_type='decimal', order=1)
    Question.objects.create(section=s, label="Amount of Premix to be utilized for the next month (kg/month)",        question_type='decimal', order=2)
    Question.objects.create(section=s, label="Challenges related to Food Fortification?",                             question_type='textarea', order=3)

    # ─── FORM V: CSB+ (same structure as Wheat Flour) ─────────────────────────
    print("Creating CSB+ Checklist...")
    f = make_form("CSB+ Flour Checklist", 'csb_plus')

    s = Section.objects.create(form=f, title="Production Data", order=1)
    for i, (label, qt) in enumerate([
        ("Installed Production Capacity (ton/day)",               "number"),
        ("Actual Production Capacity (ton/day)",                  "number"),
        ("Amount Fortified Flour Produced (ton/month)",           "decimal"),
        ("Amount of Premix Purchased in the last month (kg/month)", "decimal"),
        ("Amount of Premix Utilized (kg/month)",                  "decimal"),
        ("Amount of Premix Available in Store (kg)",              "decimal"),
    ], 1):
        Question.objects.create(section=s, label=label, question_type=qt, is_required=True, order=i)

    s = Section.objects.create(form=f, title="Packaging", order=2)
    q = Question.objects.create(section=s, label="Final Product Packaging Material Type", question_type='select', order=1)
    opts(q, [
        ("Polypropylene bag with food grade inner", "pp_food_grade"),
        ("Polypropylene bag",                        "pp_bag"),
        ("Laminated paper bag (kg/month)",           "laminated_paper"),
        ("Poly Ethylene Teraphetalet (PET) (kg/month)", "pet"),
        ("Other (kg/month)",                         "other"),
    ])
    Question.objects.create(section=s, label="Amount (kg/month)", question_type='decimal', order=2)

    s = Section.objects.create(form=f, title="Fortification Technology", order=3)
    q = Question.objects.create(section=s, label="Type of Technology used for CSB+ Flour Fortification", question_type='select', order=1)
    opts(q, [
        ("Continuous (Micro feeder and screw conveyor)", "continuous"),
        ("Batch Mixer",                                  "batch"),
    ])

    s = Section.objects.create(form=f, title="Quality Assurance & Compliance", order=4)
    q5 = Question.objects.create(section=s, label="Do you Conduct Fortification Lab Analysis?", question_type='yes_no', order=1)
    yesno(q5)
    q6 = Question.objects.create(section=s, label="Do you conduct third party laboratory test result?", question_type='yes_no', order=2)
    yesno(q6)
    Question.objects.create(section=s, label="Upload third party lab test result (photo)", question_type='image', depends_on=q6, depends_on_value="yes", order=3)
    q7 = Question.objects.create(section=s, label="Do you conduct dosing machine calibration?", question_type='yes_no', order=4)
    yesno(q7)
    Question.objects.create(section=s, label="Upload dosing machine calibration record (photo)", question_type='image', depends_on=q7, depends_on_value="yes", order=5)
    q8 = Question.objects.create(section=s, label="Did you conduct monthly premix reconciliation?", question_type='yes_no', order=6)
    yesno(q8)
    Question.objects.create(section=s, label="If yes, what is the actual addition rate per ton?", question_type='decimal', depends_on=q8, depends_on_value="yes", order=7)
    q10 = Question.objects.create(section=s, label="Do you Conduct Induction Training?", question_type='yes_no', order=8)
    yesno(q10)

    s = Section.objects.create(form=f, title="Next Month Plan", order=5)
    Question.objects.create(section=s, label="Plan to Produce Fortified CSB+ Flour for the next month (ton/month)", question_type='decimal', order=1)
    Question.objects.create(section=s, label="Amount of Premix to be utilized for the next month (kg/month)",       question_type='decimal', order=2)
    Question.objects.create(section=s, label="Challenges related to Food Fortification?",                            question_type='textarea', order=3)

    print("\n✅ Seeding complete!")
    print(f"  Forms:     {Form.objects.count()}")
    print(f"  Sections:  {Section.objects.count()}")
    print(f"  Questions: {Question.objects.count()}")
    print(f"  Categories:{Category.objects.count()}")
    print(f"  Industries:{Industry.objects.count()}")


if __name__ == "__main__":
    seed_data()

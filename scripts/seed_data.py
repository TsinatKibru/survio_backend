import os
import django
import sys
import re
from datetime import date

# Add the project root to sys.path
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
    
    # We DO NOT delete Industry and Category anymore so existing 
    # users don't lose their foreign key relationships (Upsert approach).
    
    print("Seeding roles...")
    roles = {
        'superadmin': Role.objects.update_or_create(
            code='superadmin',
            defaults={
                'name': 'Super Admin',
                'description': (
                    'Global system administrator. '
                    'Full access to all data, settings, and users across all industries and categories. '
                    'Does NOT require industry or category assignment.'
                )
            }
        )[0],
        'admin': Role.objects.update_or_create(
            code='admin',
            defaults={
                'name': 'Admin',
                'description': (
                    'Organization-level administrator. '
                    'Can view industry, form, question, reporting period, section, answer, and submission.'
                )
            }
        )[0],
        'companyuser': Role.objects.update_or_create(
            code='companyuser',
            defaults={
                'name': 'Company User',
                'description': (
                    'Standard factory/company user. '
                    'Can submit and view forms assigned to their industry. '
                    'Must be linked to an industry and category.'
                )
            }
        )[0],
    }

    print("Seeding categories...")
    categories = {
        'edible_oil': Category.objects.get_or_create(name='Edible Oil', code='edible_oil')[0],
        'wheat_flour': Category.objects.get_or_create(name='Wheat Flour', code='wheat_flour')[0],
        'salt': Category.objects.get_or_create(name='Salt', code='salt')[0],
    }

    print("Seeding industries linked to categories...")
    oil_factories = ["Health care edible oil factory", "Abay Edible oil factory", "Addis Mojo edible oil factory", "Alimpex plc", "Articraft industrial plc", "BBZ edible oil factory", "Emmy edible oil factory", "Giftii foods and packaging plc", "Hamaresa edible oil factory", "Hava industrial Plc", "Jerr PLC", "Kokeb kana edible oil", "Kunifira Agro processing plc", "Leos edible oil factory", "Mulu Work Gebeyehu Edible oil Factory", "Phebila industrial plc", "Rich Land Biochemical Production Plc.", "Ronge Ethiopia edible oil factory", "Selagoja edible oil factory", "Shemu Plc", "Tasty edible oil factory", "Unity edible oil factory", "W.A edible oil factory", "Yayirate edible oil factory", "Others"]
    for name in oil_factories:
        code = f"oil_{name.lower().replace(' ', '_')}"
        Industry.objects.update_or_create(code=code, defaults={'name': name, 'category': categories['edible_oil']})

    flour_factories = ["K.O.J.J Food Complex", "Addis Dallas Industries Plc.", "Admas Flour factory", "Africa plc", "AH-WAN PLC", "Alihenan Food Complex", "Alpha food complex", "Alvima food complex", "Chilalo food complex", "DH Geda", "Dina Food processing", "Diredawa food complex", "Echa Food Complex", "Eshet Food Complex", "Fiker Food processing", "Gonde Adama Food complex", "Hawassa Flour Factory", "Hora food complex", "Kality Food share company", "Kombolcha flour factory", "Misrak Flour factory", "Modjo flour factory", "Nefas silk food complex", "Omer Awad flour factory", "Shoa Flour Factory", "Others"]
    for name in flour_factories:
        code = f"flour_{name.lower().replace(' ', '_')}"
        Industry.objects.update_or_create(code=code, defaults={'name': name, 'category': categories['wheat_flour']})

    salt_factories = ["Ella Trading", "Green Star Trading PLC", "Ibex Waliya Salt Production", "Mesob Salt Production", "Nurmaso Salt Production PLC", "Sodaking salt processing PLC", "Sali Salt", "Afar Salt Share Company", "Berhale salt factory", "Dobi salt refinery", "Duda salt factory", "Hina Salt refinery", "Kala salt refinery", "Laki salt refinery", "Saba salt refinery", "Salit Salt factory", "Others"]
    for name in salt_factories:
        code = f"salt_{name.lower().replace(' ', '_')}"
        Industry.objects.update_or_create(code=code, defaults={'name': name, 'category': categories['salt']})

    def create_form_with_period(title, cat_key):
        """Create a form linked to a Category FK, and seed a March 2026 reporting period."""
        form = Form.objects.create(
            title=title,
            category=categories[cat_key],  # V2: ForeignKey, not string
            schedule_type='monthly',
            opens_on_day=1,
            due_on_day=10,
            closes_on_day=15,
        )
        # Seed the current period (March 2026) for immediate testing
        today = date.today()
        ReportingPeriod.objects.create(
            form=form,
            label=today.strftime('%B %Y'),
            period_start=date(today.year, today.month, 1),
            period_end=date(today.year, today.month, 28),
            due_date=date(today.year, today.month, 10),
            close_date=date(today.year, today.month, 15),
        )
        return form

    def add_entrant_info(section, start_order):
        Question.objects.create(section=section, label="Name (Entrant name)", question_type='text', is_required=True, order=start_order)
        Question.objects.create(section=section, label="Position", question_type='text', order=start_order+1)
        Question.objects.create(section=section, label="Phone Number", question_type='phone', is_required=True, order=start_order+2)
        Question.objects.create(section=section, label="E-mail", question_type='email', order=start_order+3)

    # ==========================================
    # EDIBLE OIL FORM
    # ==========================================
    print("Creating EDIBLE OIL survey form...")
    form_oil = create_form_with_period("Monthly Edible Oil Production Data", 'edible_oil')

    s3_oil = Section.objects.create(form=form_oil, title="EDIBLE OIL PRODUCTION", order=1)
    o_fields = [
        ("Installed production Capacity (ton/day)", "number"),
        ("Actual production capacity (ton/day)", "number"),
        ("Amount of produced fortified edible oil (ton/month)", "decimal"),
        ("Amount of vitamin A & D purchased in the last one month", "decimal"),
        ("Amount of Vitamin A and D utilized (kg/month)", "decimal"),
        ("Amount of Vitamin A and D available in stock (kg)", "decimal"),
    ]
    for i, (label, q_type) in enumerate(o_fields):
        Question.objects.create(section=s3_oil, label=label, question_type=q_type, order=i+1)

    q_oil_pack = Question.objects.create(section=s3_oil, label="Edible oil Packaging Material Type", question_type='select', order=7)
    oil_pack_opts = ["Polypropylene bag with food grade inner liner (kg/month)", "Polypropylene bag", "PET bottle", "Jerrycan", "Tinplate", "Glass bottle", "Bulk (Tanker)", "Others"]
    for i, opt in enumerate(oil_pack_opts):
        QuestionOption.objects.create(question=q_oil_pack, label=opt, value=re.sub(r'[^a-zA-Z0-9_]', '', opt.lower().replace(' ', '_')), order=i)
    
    Question.objects.create(section=s3_oil, label="Amount (Packaging)", question_type='decimal', order=8)

    s4_oil = Section.objects.create(form=form_oil, title="FORTIFICATION TECHNOLOGY", order=3)
    q_oil_tech = Question.objects.create(section=s4_oil, label="Type of technology used for edible oil fortification", question_type='multiselect', order=1)
    
    tech_opts = [
        ("Continuous (Micro feeder pump and recirculation pipe system)", "continuous"),
        ("Batch Mixer", "batch"),
        ("Two Stage", "two_stage")
    ]
    for i, (label, val) in enumerate(tech_opts):
        QuestionOption.objects.create(question=q_oil_tech, label=label, value=val, order=i)

    # --- Continuous Dependents ---
    q_cont_record = Question.objects.create(
        section=s4_oil, 
        label="If the technology is continuous, do you measure and record edible oil production rate", 
        question_type='yes_no', 
        depends_on=q_oil_tech, 
        depends_on_value="continuous",
        order=2
    )
    QuestionOption.objects.create(question=q_cont_record, label="Yes", value="yes", order=1)
    QuestionOption.objects.create(question=q_cont_record, label="No", value="no", order=2)

    q_cont_challenges = Question.objects.create(
        section=s4_oil, 
        label="If the technology is continuous, challenges in relation to micro feeder", 
        question_type='multiselect', 
        depends_on=q_oil_tech, 
        depends_on_value="continuous",
        order=3
    )
    challenge_opts = ["Micro feeder operation (calibration, speed adjustment)", "Maintenance", "Electrical (power) connection systems", "Pre blend preparation", "Pre blend loading", "Proper functionality inspection", "Other"]
    for i, opt in enumerate(challenge_opts):
        QuestionOption.objects.create(question=q_cont_challenges, label=opt, value=re.sub(r'[^a-zA-Z0-9_]', '', opt.lower().replace(' ', '_')), order=i)

    # --- Batch Dependents ---
    q_batch_doc = Question.objects.create(
        section=s4_oil, 
        label="If the technology is batch, do you have proper documentation for mixing time", 
        question_type='yes_no', 
        depends_on=q_oil_tech, 
        depends_on_value="batch",
        order=4
    )
    QuestionOption.objects.create(question=q_batch_doc, label="Yes", value="yes", order=1)
    QuestionOption.objects.create(question=q_batch_doc, label="No", value="no", order=2)

    Question.objects.create(
        section=s4_oil,
        label="Upload photo of batch mixing time documentation",
        question_type='image',
        depends_on=q_batch_doc,
        depends_on_value="yes",
        order=5
    )

    q_batch_time = Question.objects.create(
        section=s4_oil, 
        label="If the technology is batch, indicate mixing time", 
        question_type='select', 
        depends_on=q_oil_tech, 
        depends_on_value="batch",
        order=6
    )
    time_opts = ["Less than 30 min", "30 - 60 min", "60 - 90 min", "Above 90 min"]
    for i, opt in enumerate(time_opts):
        QuestionOption.objects.create(question=q_batch_time, label=opt, value=re.sub(r'[^a-zA-Z0-9_]', '', opt.lower().replace(' ', '_')), order=i)

    Question.objects.create(
        section=s4_oil, 
        label="If the Technology is Batch, indicate RPM.", 
        question_type='decimal', 
        depends_on=q_oil_tech, 
        depends_on_value="batch",
        order=7
    )

    # --- Two Stage Dependents ---
    q_two_doc = Question.objects.create(
        section=s4_oil, 
        label="If the technology is Two Stage, do you have proper documentation for mixing time", 
        question_type='yes_no', 
        depends_on=q_oil_tech, 
        depends_on_value="two_stage",
        order=8
    )
    QuestionOption.objects.create(question=q_two_doc, label="Yes", value="yes", order=1)
    QuestionOption.objects.create(question=q_two_doc, label="No", value="no", order=2)

    Question.objects.create(
        section=s4_oil, 
        label="If the Technology is Two Stage, indicate RPM.", 
        question_type='decimal', 
        depends_on=q_oil_tech, 
        depends_on_value="two_stage",
        order=9
    )
    Question.objects.create(
        section=s4_oil, 
        label="Volumetric/Pump Flow Rate(m3/h) For the Circulation Pump", 
        question_type='decimal', 
        depends_on=q_oil_tech, 
        depends_on_value="two_stage",
        order=10
    )

    s5_oil = Section.objects.create(form=form_oil, title="ADDITIONAL PRODUCT INFO (EDIBLE OIL)", order=4)
    q_oil_yesno = [
        "Do you have skilled personnel to conduct edible oil fortification production?",
        "Do you conduct FF lab analysis?",
        "Do you conduct induction training?"
    ]
    for i, label in enumerate(q_oil_yesno):
        q = Question.objects.create(section=s5_oil, label=label, question_type='yes_no', order=i+1)
        QuestionOption.objects.create(question=q, label="Yes", value="yes", order=1)
        QuestionOption.objects.create(question=q, label="No", value="no", order=2)

    Question.objects.create(section=s5_oil, label="Plan to produce fortified edible oil for the next month (ton/month)", question_type='decimal', order=4)
    Question.objects.create(section=s5_oil, label="Amount of fortificant to be utilized for the next month (kg/month)", question_type='decimal', order=5)
    Question.objects.create(section=s5_oil, label="Challenges related to Food Fortification?", question_type='textarea', order=6)

    # ==========================================
    # WHEAT FLOUR FORM
    # ==========================================
    print("Creating WHEAT FLOUR survey form...")
    form_flour = create_form_with_period("Monthly Wheat Flour Production Data", 'wheat_flour')

    s3_flour = Section.objects.create(form=form_flour, title="WHEAT FLOUR PRODUCTION", order=1)
    f_fields = [
        ("Installed production Capacity (ton/day)", "number"),
        ("Actual production capacity (ton/day)", "number"),
        ("Amount of fortified flour produced (ton/month)", "decimal"),
        ("Amount of premix purchased in the last one month (kg/month)", "decimal"),
        ("Amount of premix utilized (kg/month)", "decimal"),
        ("Amount of premix available in stock (Kg)", "decimal"),
    ]
    for i, (label, q_type) in enumerate(f_fields):
        Question.objects.create(section=s3_flour, label=label, question_type=q_type, order=i+1)

    q_flour_pack = Question.objects.create(section=s3_flour, label="Packaging Material Type", question_type='select', order=7)
    flour_pack_opts = ["Polypropylene bag with food grade inner liner (kg/month)", "Polypropylene bag", "Laminated Paper bag (kg/month)", "Poly Ethylene Teraphetalet (PET) (kg/month)", "Other (kg/month)"]
    for i, opt in enumerate(flour_pack_opts):
        QuestionOption.objects.create(question=q_flour_pack, label=opt, value=opt.lower().replace(' ', '_'), order=i)
    
    Question.objects.create(section=s3_flour, label="Amount (Packaging)", question_type='textarea', order=8)

    s4_flour = Section.objects.create(form=form_flour, title="FORTIFICATION TECHNOLOGY", order=3)
    q_flour_tech = Question.objects.create(section=s4_flour, label="Type of technology used for wheat flour fortification", question_type='multiselect', order=1)
    
    flour_tech_opts = [
        ("Continuous (Micro feeder and screw conveyor)", "continuous"),
        ("Batch Mixer", "batch")
    ]
    for i, (label, val) in enumerate(flour_tech_opts):
        QuestionOption.objects.create(question=q_flour_tech, label=label, value=val, order=i)

    # --- Continuous Dependents ---
    q_fl_cont_rate = Question.objects.create(
        section=s4_flour, 
        label="If the technology is continuous, do you measure and record flour production rate", 
        question_type='yes_no', 
        depends_on=q_flour_tech, 
        depends_on_value="continuous",
        order=2
    )
    QuestionOption.objects.create(question=q_fl_cont_rate, label="Yes", value="yes", order=1)
    QuestionOption.objects.create(question=q_fl_cont_rate, label="No", value="no", order=2)

    Question.objects.create(
        section=s4_flour,
        label="Photo of the flour production rate log",
        question_type='image',
        depends_on=q_fl_cont_rate,
        depends_on_value="yes",
        order=3
    )

    q_fl_cont_speed = Question.objects.create(
        section=s4_flour, 
        label="If the technology is continuous, do you periodically adjust and record micro feeder speed", 
        question_type='yes_no', 
        depends_on=q_flour_tech, 
        depends_on_value="continuous",
        order=4
    )
    QuestionOption.objects.create(question=q_fl_cont_speed, label="Yes", value="yes", order=1)
    QuestionOption.objects.create(question=q_fl_cont_speed, label="No", value="no", order=2)

    q_fl_cont_challenges = Question.objects.create(
        section=s4_flour, 
        label="If the technology is continuous, challenges in relation to micro feeder", 
        question_type='multiselect', 
        depends_on=q_flour_tech, 
        depends_on_value="continuous",
        order=5
    )
    fl_challenge_opts = ["Micro feeder operation (calibration, speed adjustment)", "Maintenance", "Electrical (power) connection systems", "Proper functionality inspection", "Other"]
    for i, opt in enumerate(fl_challenge_opts):
        QuestionOption.objects.create(question=q_fl_cont_challenges, label=opt, value=re.sub(r'[^a-zA-Z0-9_]', '', opt.lower().replace(' ', '_')), order=i)

    # --- Batch Dependents ---
    q_fl_batch_doc = Question.objects.create(
        section=s4_flour, 
        label="If the technology is batch, do you have proper documentation for mixing time", 
        question_type='yes_no', 
        depends_on=q_flour_tech, 
        depends_on_value="batch",
        order=6
    )
    QuestionOption.objects.create(question=q_fl_batch_doc, label="Yes", value="yes", order=1)
    QuestionOption.objects.create(question=q_fl_batch_doc, label="No", value="no", order=2)

    q_fl_batch_time = Question.objects.create(
        section=s4_flour, 
        label="If the technology is batch, indicate mixing time", 
        question_type='select', 
        depends_on=q_flour_tech, 
        depends_on_value="batch",
        order=7
    )
    fl_time_opts = ["Less than 5 min", "5 min", "10 min", "15 min", "20 min and above"]
    for i, opt in enumerate(fl_time_opts):
        QuestionOption.objects.create(question=q_fl_batch_time, label=opt, value=re.sub(r'[^a-zA-Z0-9_]', '', opt.lower().replace(' ', '_')), order=i)

    s5_flour = Section.objects.create(form=form_flour, title="ADDITIONAL PRODUCT INFO (WHEAT FLOUR)", order=4)
    flour_yesno = [
        "Do you have skilled personnel to conduct flour fortification production?",
        "Do you conduct fortification lab analysis?",
        "Do you conduct induction training?"
    ]
    for i, label in enumerate(flour_yesno):
        q = Question.objects.create(section=s5_flour, label=label, question_type='yes_no', order=i+1)
        QuestionOption.objects.create(question=q, label="Yes", value="yes", order=1)
        QuestionOption.objects.create(question=q, label="No", value="no", order=2)

    Question.objects.create(section=s5_flour, label="Plan to produce fortified wheat flour for the next month (ton/month)", question_type='decimal', order=4)
    Question.objects.create(section=s5_flour, label="Amount of PREMIX to be utilized for the next month (kg/month)", question_type='decimal', order=5)
    Question.objects.create(section=s5_flour, label="Challenges related to Food Fortification?", question_type='textarea', order=6)

    # ==========================================
    # SALT FORM (V3: Industry Detailed)
    # ==========================================
    print("Creating SALT survey form (Detailed)...")
    form_salt = create_form_with_period("Monthly Salt Production Data", 'salt')

    s1_salt = Section.objects.create(form=form_salt, title="TYPE OF PRODUCT AND PRODUCTION CAPACITY", order=1)
    # 4 Slots for Product Types
    for i in range(1, 5):
        Question.objects.create(section=s1_salt, label=f"Product Type {i}", question_type='select', order=(i-1)*4 + 1)
        Question.objects.create(section=s1_salt, label=f"Installed Capacity {i} (ton/day)", question_type='number', order=(i-1)*4 + 2)
        Question.objects.create(section=s1_salt, label=f"Max. Attained Capacity {i} (ton/day)", question_type='number', order=(i-1)*4 + 3)
        Question.objects.create(section=s1_salt, label=f"Actual Production {i} (ton/day)", question_type='number', order=(i-1)*4 + 4)

    s2_salt = Section.objects.create(form=form_salt, title="PACKAGING MATERIALS AND AMOUNT", order=2)
    for i in range(1, 4):
        Question.objects.create(section=s2_salt, label=f"Packaging Material Type {i}", question_type='select', order=(i-1)*3 + 1)
        Question.objects.create(section=s2_salt, label=f"Amount {i}", question_type='decimal', order=(i-1)*3 + 2)
        Question.objects.create(section=s2_salt, label=f"Unit {i}", question_type='select', order=(i-1)*3 + 3)

    s3_salt = Section.objects.create(form=form_salt, title="SALT PROCESSING INFO", order=3)
    Question.objects.create(section=s3_salt, label="Washed Salt Extraction rate (%)", question_type='decimal', order=1)
    Question.objects.create(section=s3_salt, label="Unwashed Salt Extraction rate (%)", question_type='decimal', order=2)

    s4_salt = Section.objects.create(form=form_salt, title="INPUTS USED PER DAY (QUINTAL)", order=4)
    Question.objects.create(section=s4_salt, label="Potassium iodate (kg)", question_type='decimal', order=1)
    Question.objects.create(section=s4_salt, label="Addition rate of potassium iodate per kg of salt", question_type='decimal', order=2)

    s5_salt = Section.objects.create(form=form_salt, title="SKILLED PERSONNEL (LABORATORY)", order=5)
    Question.objects.create(section=s5_salt, label="Male (Number)", question_type='number', order=1)
    Question.objects.create(section=s5_salt, label="Female (Number)", question_type='number', order=2)

    s6_salt = Section.objects.create(form=form_salt, title="QUALITY ANALYSIS", order=6)
    q_outsource = Question.objects.create(section=s6_salt, label="Does the company outsource quality analysis?", question_type='yes_no', order=1)
    QuestionOption.objects.create(question=q_outsource, label="Yes", value="yes", order=1)
    QuestionOption.objects.create(question=q_outsource, label="No", value="no", order=2)

    Question.objects.create(
        section=s6_salt,
        label="Laboratory Certificate / Outsourced Analysis Report",
        question_type='image',
        depends_on=q_outsource,
        depends_on_value='yes',
        order=2
    )

    s7_salt = Section.objects.create(form=form_salt, title="AVERAGE RAW MATERIAL PURCHASE PRICE", order=7)
    Question.objects.create(section=s7_salt, label="Washed Salt (Birr/kg)", question_type='decimal', order=1)
    Question.objects.create(section=s7_salt, label="Unwashed Salt (Birr/kg)", question_type='decimal', order=2)
    Question.objects.create(section=s7_salt, label="Potassium iodate (Birr/kg)", question_type='decimal', order=3)

    # Add units and materials for all packaging slots (3 slots)
    for i in range(1, 4):
        mat_q = Question.objects.get(section=s2_salt, label=f"Packaging Material Type {i}")
        for j, m in enumerate(["HDPE", "PP bag", "Paper", "Plastic jar", "Other"]):
            QuestionOption.objects.create(question=mat_q, label=m, value=m.lower().replace(' ', '_'), order=j)
        
        unit_q = Question.objects.get(section=s2_salt, label=f"Unit {i}")
        for j, u in enumerate(["K.G", "Ton", "Quintal", "Pcs"]):
            QuestionOption.objects.create(question=unit_q, label=u, value=u.lower(), order=j)

    # Add product types to s1_salt Product questions (all 4 slots)

    # Add product types to s1_salt Product questions (all 4 slots)
    for i in range(1, 5):
        p_q = Question.objects.get(section=s1_salt, label=f"Product Type {i}")
        for j, p in enumerate(["Table Salt", "Common Salt", "Non-iodized Salt", "Lick Salt"]):
            QuestionOption.objects.create(question=p_q, label=p, value=p.lower().replace(' ', '_'), order=j)

    print("Seeding completed successfully!")

if __name__ == "__main__":
    seed_data()

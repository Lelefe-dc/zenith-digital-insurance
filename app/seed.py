from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import get_settings
from .management_models import (
    Branch,
    Customer,
    InsuranceProduct,
    PolicyProfile,
    PremiumPayment,
    StaffUser,
    SystemSetting,
    WorkTask,
)
from .models import FAQArticle, Policy
from .security import hash_password

settings = get_settings()


def seed_demo_data(db: Session) -> None:
    if db.query(Policy).count() == 0:
        db.add_all([
            Policy(policy_number="ZEN-100001", holder_name="Demo Policyholder", dob=date(1990, 1, 1), status="Active", product="Motor Insurance", premium=850.00),
            Policy(policy_number="ZEN-100002", holder_name="Mpho Customer", dob=date(1987, 6, 15), status="Active", product="Property Insurance", premium=620.50),
            Policy(policy_number="ZEN-100003", holder_name="Test Client", dob=date(1978, 12, 10), status="Inactive", product="Funeral Cover", premium=140.00),
        ])
        db.flush()

    if db.query(FAQArticle).count() == 0:
        db.add_all([
            FAQArticle(
                category="Policies",
                question_en="What does my policy cover?",
                answer_en="Cover depends on your policy schedule and wording. Use My Policy for a limited summary, or speak to an agent for cover-specific advice.",
                question_st="Leano la ka le koahela eng?",
                answer_st="Tšireletso e ipapisitse le schedule le melao ea leano la hao. Sebelisa 'Leano la ka' bakeng sa kakaretso, kapa bua le moemeli bakeng sa lintlha tse itseng.",
            ),
            FAQArticle(
                category="Premiums & Payments",
                question_en="When is my premium due?",
                answer_en="Premium due dates are determined by your policy schedule. For account-specific payment information, please speak to a Zenith agent.",
                question_st="Premium ea ka e lefshoa neng?",
                answer_st="Letsatsi la tefo le fumanoa ho schedule ea leano la hao. Bakeng sa lintlha tsa ak'haonte ea hao, ka kopo bua le moemeli oa Zenith.",
            ),
            FAQArticle(
                category="Claims",
                question_en="What do I need to report a claim?",
                answer_en="Please have your policy number, incident date, a description of what happened, the location, contact details and any available photos or supporting documents.",
                question_st="Ke hloka eng ho tlaleha tleleime?",
                answer_st="Lokisa nomoro ea leano, letsatsi la ketsahalo, tlhaloso ea se etsahetseng, sebaka, lintlha tsa puisano le linepe kapa litokomane tse teng.",
            ),
            FAQArticle(
                category="Documents",
                question_en="Which documents can I upload?",
                answer_en="The assistant accepts common image and PDF evidence for claims. Exact document requirements vary by claim and product.",
                question_st="Ke litokomane life tseo nka li kenyang?",
                answer_st="Sisteme e amohela linepe tse tloaelehileng le PDF bakeng sa bopaki ba tleleime. Litlhoko li ka fapana ho ea ka sehlahisoa le tleleime.",
            ),
            FAQArticle(
                category="Contact & Service",
                question_en="How do I speak to an agent?",
                answer_en="Choose Speak to an Agent from the main menu, or type Agent at any point. The system will create a support request with your conversation context.",
                question_st="Nka bua joang le moemeli?",
                answer_st="Khetha 'Bua le Moemeli' menueng e kholo, kapa ngola 'Agent'. Sisteme e tla etsa kopo ea tšehetso e nang le lintlha tsa puisano ea hao.",
            ),
        ])

    if db.query(Branch).count() == 0:
        db.add_all([
            Branch(code="MAS", name="Maseru Head Office", location="Maseru"),
            Branch(code="TY", name="Teyateyaneng Branch", location="Berea"),
            Branch(code="MFT", name="Mafeteng Branch", location="Mafeteng"),
        ])
        db.flush()

    if db.query(InsuranceProduct).count() == 0:
        db.add_all([
            InsuranceProduct(code="MOTOR", name="Motor Insurance", category="General Insurance", description="Private and commercial motor cover.", base_premium=850.00),
            InsuranceProduct(code="PROPERTY", name="Property Insurance", category="General Insurance", description="Buildings and contents cover.", base_premium=620.50),
            InsuranceProduct(code="FUNERAL", name="Funeral Cover", category="Life & Funeral", description="Individual and family funeral protection.", base_premium=140.00),
            InsuranceProduct(code="LIFE", name="Life Insurance", category="Life & Funeral", description="Life protection and beneficiary cover.", base_premium=300.00),
        ])
        db.flush()

    admin_email = settings.management_admin_email.lower().strip()
    admin = db.query(StaffUser).filter(func.lower(StaffUser.email) == admin_email).first()
    if not admin:
        main_branch = db.query(Branch).filter(Branch.code == "MAS").first()
        admin = StaffUser(
            employee_number="EMP-ADMIN",
            full_name="System Administrator",
            email=admin_email,
            password_hash=hash_password(settings.management_admin_password),
            role="Administrator",
            department="Management",
            branch_id=main_branch.id if main_branch else None,
            active=True,
        )
        db.add(admin)
        db.flush()

    if db.query(Customer).count() == 0:
        db.add_all([
            Customer(customer_number="CUS-2026-000001", full_name="Demo Policyholder", national_id="DEMO-900101", date_of_birth=date(1990, 1, 1), mobile="58000001", email="demo.policyholder@example.com", district="Maseru", occupation="Business Owner", status="Active", source="seed"),
            Customer(customer_number="CUS-2026-000002", full_name="Mpho Customer", national_id="DEMO-870615", date_of_birth=date(1987, 6, 15), mobile="58000002", email="mpho.customer@example.com", district="Berea", occupation="Teacher", status="Active", source="seed"),
            Customer(customer_number="CUS-2026-000003", full_name="Test Client", national_id="DEMO-781210", date_of_birth=date(1978, 12, 10), mobile="58000003", email="test.client@example.com", district="Mafeteng", occupation="Trader", status="Inactive", source="seed"),
        ])
        db.flush()

    if db.query(PolicyProfile).count() == 0:
        main_branch = db.query(Branch).filter(Branch.code == "MAS").first()
        product_by_name = {x.name: x for x in db.query(InsuranceProduct).all()}
        customer_by_name = {x.full_name: x for x in db.query(Customer).all()}
        for policy in db.query(Policy).all():
            customer = customer_by_name.get(policy.holder_name)
            product = product_by_name.get(policy.product)
            if customer:
                db.add(PolicyProfile(
                    policy_id=policy.id,
                    customer_id=customer.id,
                    product_id=product.id if product else None,
                    branch_id=main_branch.id if main_branch else None,
                    agent_id=admin.id,
                    effective_date=date(2026, 1, 1),
                    expiry_date=date(2026, 12, 31),
                    sum_insured=250000.00 if policy.product == "Motor Insurance" else 150000.00,
                    payment_frequency="Monthly",
                    payment_status="Current" if policy.status == "Active" else "Stopped",
                    risk_address="Maseru, Lesotho",
                    notes="Seeded management profile",
                ))
        db.flush()

    if db.query(PremiumPayment).count() == 0:
        policy1 = db.query(Policy).filter(Policy.policy_number == "ZEN-100001").first()
        policy2 = db.query(Policy).filter(Policy.policy_number == "ZEN-100002").first()
        profile1 = db.query(PolicyProfile).filter(PolicyProfile.policy_id == policy1.id).first() if policy1 else None
        profile2 = db.query(PolicyProfile).filter(PolicyProfile.policy_id == policy2.id).first() if policy2 else None
        if policy1:
            db.add(PremiumPayment(reference="PAY-202609-0001", policy_id=policy1.id, customer_id=profile1.customer_id if profile1 else None, due_date=date(2026, 9, 1), amount=850.00, paid_amount=850.00, currency="LSL", method="Bank Transfer", status="Paid", transaction_reference="DEMO-TXN-001", paid_at=datetime.utcnow() - timedelta(days=3)))
        if policy2:
            db.add(PremiumPayment(reference="PAY-202609-0002", policy_id=policy2.id, customer_id=profile2.customer_id if profile2 else None, due_date=date(2026, 9, 1), amount=620.50, paid_amount=0.00, currency="LSL", method=None, status="Pending"))

    if db.query(WorkTask).count() == 0:
        db.add_all([
            WorkTask(reference="TSK-202609-0001", title="Review pending September premium", description="Follow up on the pending Property Insurance premium.", assigned_to_id=admin.id, created_by_id=admin.id, priority="High", status="Open", due_at=datetime.utcnow() + timedelta(days=1)),
            WorkTask(reference="TSK-202609-0002", title="Validate policy documents", description="Confirm that the seeded motor policy documents are complete.", assigned_to_id=admin.id, created_by_id=admin.id, priority="Normal", status="Open", due_at=datetime.utcnow() + timedelta(days=3)),
        ])

    if db.query(SystemSetting).count() == 0:
        db.add_all([
            SystemSetting(key="company.name", value="Zenith Horizon Insurance Company Limited", category="Company", updated_by_id=admin.id),
            SystemSetting(key="company.currency", value="LSL", category="Company", updated_by_id=admin.id),
            SystemSetting(key="claims.default_sla_days", value="5", category="Claims", updated_by_id=admin.id),
            SystemSetting(key="whatsapp.phase", value="deferred-until-management-complete", category="Integrations", updated_by_id=admin.id),
        ])

    db.commit()

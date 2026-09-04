from datetime import date
from sqlalchemy.orm import Session
from .models import Policy, FAQArticle


def seed_demo_data(db: Session) -> None:
    if db.query(Policy).count() == 0:
        db.add_all([
            Policy(policy_number="ZEN-100001", holder_name="Demo Policyholder", dob=date(1990, 1, 1), status="Active", product="Motor Insurance", premium=850.00),
            Policy(policy_number="ZEN-100002", holder_name="Mpho Customer", dob=date(1987, 6, 15), status="Active", product="Property Insurance", premium=620.50),
            Policy(policy_number="ZEN-100003", holder_name="Test Client", dob=date(1978, 12, 10), status="Inactive", product="Funeral Cover", premium=140.00),
        ])
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
    db.commit()

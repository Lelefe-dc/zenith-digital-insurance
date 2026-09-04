import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import Base
from app.management import create_customer, create_payment, create_policy, login
from app.management_models import Customer, InsuranceProduct, PolicyProfile, PremiumPayment, StaffUser
from app.management_schemas import CustomerCreate, LoginRequest, PaymentCreate, PolicyCreate
from app.security import hash_password, verify_password
from app.seed import seed_demo_data


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    seed_demo_data(db)
    return db


def test_password_hash_roundtrip():
    encoded = hash_password("a-strong-test-password")
    assert encoded != "a-strong-test-password"
    assert verify_password("a-strong-test-password", encoded)
    assert not verify_password("wrong-password", encoded)


def test_management_seed_creates_core_records():
    db = make_db()
    assert db.query(StaffUser).filter(StaffUser.role == "Administrator").count() == 1
    assert db.query(Customer).count() >= 3
    assert db.query(InsuranceProduct).count() >= 4
    assert db.query(PolicyProfile).count() >= 3
    assert db.query(PremiumPayment).count() >= 2


def test_login_and_create_customer_policy_payment():
    db = make_db()
    settings = get_settings()
    result = login(LoginRequest(email=settings.management_admin_email, password=settings.management_admin_password), db)
    assert result["token"]
    admin = db.query(StaffUser).filter(StaffUser.email == settings.management_admin_email.lower()).first()

    customer = create_customer(
        CustomerCreate(
            full_name="Management Test Client",
            national_id="TEST-MGMT-001",
            date_of_birth=date(1992, 4, 10),
            mobile="58009999",
            email="mgmt.test@example.com",
            district="Maseru",
        ),
        admin,
        db,
    )
    product = db.query(InsuranceProduct).filter(InsuranceProduct.code == "MOTOR").first()
    policy = create_policy(
        PolicyCreate(
            customer_id=customer["id"],
            product_id=product.id,
            premium=990.0,
            effective_date=date(2026, 9, 1),
            expiry_date=date(2027, 8, 31),
            sum_insured=300000.0,
        ),
        admin,
        db,
    )
    assert policy["policy_number"].startswith("ZEN-")

    payment = create_payment(
        PaymentCreate(policy_id=policy["id"], amount=990.0, paid_amount=990.0, status="Paid", method="Cash"),
        admin,
        db,
    )
    assert payment["status"] == "Paid"
    assert payment["paid_amount"] == 990.0

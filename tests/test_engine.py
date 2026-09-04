import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.engine import start_session, handle_message
from app.seed import seed_demo_data


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session(); seed_demo_data(db); return db


def test_policy_journey():
    db = make_db(); s = start_session(db, "tester")
    r = handle_message(db, s.session_id, "1"); assert "What would" in r.messages[-1]
    handle_message(db, s.session_id, "1")
    handle_message(db, s.session_id, "ZEN-100001")
    r = handle_message(db, s.session_id, "01/01/1990")
    assert any("Policy verified" in m for m in r.messages)


def test_quote_creates_reference():
    db = make_db(); s = start_session(db, "tester")
    handle_message(db, s.session_id, "1"); handle_message(db, s.session_id, "2")
    handle_message(db, s.session_id, "3"); handle_message(db, s.session_id, "Mpho Test")
    handle_message(db, s.session_id, "58000000"); handle_message(db, s.session_id, "4")
    handle_message(db, s.session_id, "50000")
    r = handle_message(db, s.session_id, "yes")
    assert any("ZQ-" in m for m in r.messages)


def test_claim_creates_reference():
    db = make_db(); s = start_session(db, "tester")
    handle_message(db, s.session_id, "1"); handle_message(db, s.session_id, "3")
    handle_message(db, s.session_id, "ZEN-100001"); handle_message(db, s.session_id, "01/09/2026")
    handle_message(db, s.session_id, "Vehicle damaged in a collision")
    handle_message(db, s.session_id, "Maseru")
    handle_message(db, s.session_id, "25000")
    r = handle_message(db, s.session_id, "58000000")
    assert r.claim_reference and r.claim_reference.startswith("ZC-")
    assert r.allow_attachment is True

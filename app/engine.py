from __future__ import annotations

import json
import re
import secrets
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from .models import AgentTicket, AuditEvent, Claim, ConversationSession, FAQArticle, Lead, Policy
from .schemas import ChatResponse, Option

PRODUCTS = {
    "1": ("Motor Insurance", [
        ("vehicle_make_model", "Please enter the vehicle make and model."),
        ("vehicle_year", "What year was the vehicle manufactured?"),
        ("vehicle_value", "What is the estimated vehicle value in Maloti?"),
        ("vehicle_use", "How is the vehicle mainly used? (Private/Business)"),
    ]),
    "2": ("Property Insurance", [
        ("property_type", "What type of property is it?"),
        ("property_location", "Where is the property located?"),
        ("property_value", "What is the estimated property value in Maloti?"),
    ]),
    "3": ("Funeral Cover", [
        ("insured_count", "How many people should be covered?"),
        ("cover_amount", "What cover amount would you like in Maloti?"),
    ]),
    "4": ("Life Insurance", [
        ("age", "What is the age of the person to be insured?"),
        ("cover_amount", "What cover amount would you like in Maloti?"),
    ]),
}

ST = {
    "menu": "U ka rata ho etsa eng?",
    "policy_number": "Ka kopo kenya nomoro ea leano la hao.",
    "policy_dob": "Kenya letsatsi la tsoalo ka dd/mm/yyyy.",
    "quote_product": "Khetha sehlahisoa sa inshorense.",
    "quote_name": "Lebitso le feletseng ke mang?",
    "quote_mobile": "Kenya nomoro ea mohala eo re ka ikopanyang le uena ho eona.",
    "quote_consent": "Na u lumella Zenith ho ikopanya le uena? Araba Ee kapa Che.",
    "claim_policy": "Kenya nomoro ea leano bakeng sa tleleime.",
    "claim_date": "Ketsahalo e etsahetse neng? Sebelisa dd/mm/yyyy.",
    "claim_description": "Ka bokhutšoanyane, hlalosa se etsahetseng.",
    "claim_location": "Ketsahalo e etsahetse hokae?",
    "claim_damage": "Boleng bo hakanyetsoang ba tahlehelo ka Maloti ke bokae? U ka ngola unknown.",
    "claim_contact": "Tiisa nomoro ea mohala eo claims e ka u fumanang ho eona.",
    "agent_reason": "Re bolelle ka bokhutšoanyane hore na u hloka thuso ka eng.",
}

EN = {
    "policy_number": "Please enter your policy number.",
    "policy_dob": "Enter the policyholder date of birth in dd/mm/yyyy format.",
    "quote_product": "Choose an insurance product.",
    "quote_name": "What is your full name?",
    "quote_mobile": "Enter the mobile number Zenith should use to contact you.",
    "quote_consent": "Do you consent to Zenith contacting you about this request? Reply Yes or No.",
    "claim_policy": "Enter the policy number for this claim.",
    "claim_date": "When did the incident happen? Use dd/mm/yyyy.",
    "claim_description": "Briefly describe what happened.",
    "claim_location": "Where did the incident happen?",
    "claim_damage": "What is the estimated loss/damage in Maloti? You may type unknown.",
    "claim_contact": "Confirm the mobile number the claims team should use to reach you.",
    "agent_reason": "In one short message, tell us what you need help with.",
}


def _ctx(s: ConversationSession) -> dict:
    try:
        return json.loads(s.context_json or "{}")
    except json.JSONDecodeError:
        return {}


def _save(s: ConversationSession, ctx: dict) -> None:
    s.context_json = json.dumps(ctx, ensure_ascii=False)


def _opts(items):
    return [Option(label=label, value=value) for label, value in items]


def _audit(db: Session, s: ConversationSession, event: str, payload: dict | None = None):
    db.add(AuditEvent(session_id=s.id, event_type=event, payload_json=json.dumps(payload or {}, default=str)))


def _ref(prefix: str) -> str:
    return f"{prefix}-{datetime.utcnow():%Y%m%d}-{secrets.token_hex(3).upper()}"


def _menu(s: ConversationSession) -> ChatResponse:
    if s.language == "st":
        msg = ST["menu"]
        items = [("1. Leano la ka", "1"), ("2. Kopa khotheishene", "2"), ("3. Tlaleha tleleime", "3"), ("4. Bua le moemeli", "4"), ("5. Lipotso tse tloaelehileng", "5")]
    else:
        msg = "What would you like to do?"
        items = [("1. My Policy", "1"), ("2. Get a Quote", "2"), ("3. Report a Claim", "3"), ("4. Speak to an Agent", "4"), ("5. Visit FAQ", "5")]
    return ChatResponse(session_id=s.id, messages=[msg], options=_opts(items), input_hint="Choose 1–5")


def _prompt(db: Session, s: ConversationSession) -> ChatResponse:
    state = s.state
    if state == "main_menu":
        return _menu(s)
    if state == "choose_language":
        return ChatResponse(session_id=s.id, messages=["Please choose your language / Ka kopo khetha puo."], options=_opts([("1. English", "1"), ("2. Sesotho", "2")]))
    if state == "quote_product":
        return ChatResponse(session_id=s.id, messages=[ST[state] if s.language == "st" else EN[state]], options=_opts([("1. Motor Insurance", "1"), ("2. Property Insurance", "2"), ("3. Funeral Cover", "3"), ("4. Life Insurance", "4")]))
    if state.startswith("quote_risk_"):
        idx = int(state.rsplit("_", 1)[1])
        key = _ctx(s).get("quote", {}).get("product_key", "1")
        return ChatResponse(session_id=s.id, messages=[PRODUCTS[key][1][idx][1]])
    if state == "faq_menu":
        rows = db.query(FAQArticle).filter(FAQArticle.active.is_(True)).all()
        items = [(f"{i}. {a.question_st if s.language == 'st' else a.question_en}", str(i)) for i, a in enumerate(rows, 1)]
        return ChatResponse(session_id=s.id, messages=["Khetha potso:" if s.language == "st" else "Choose a question:"], options=_opts(items))
    text = (ST if s.language == "st" else EN).get(state, "Please continue.")
    return ChatResponse(session_id=s.id, messages=[text])


def start_session(db: Session, user_id: str | None = None, channel: str = "web") -> ChatResponse:
    s = ConversationSession(id=str(uuid.uuid4()), channel_user_id=user_id or f"web-{uuid.uuid4().hex[:10]}", channel=channel, state="choose_language", context_json="{}")
    db.add(s)
    _audit(db, s, "session_started", {"channel": channel})
    db.commit()
    return ChatResponse(session_id=s.id, messages=["Welcome to Zenith Horizon Insurance Company Limited. Please choose your language."], options=_opts([("1. English", "1"), ("2. Sesotho", "2")]), input_hint="Reply 1 or 2")


def _valid_mobile(text: str) -> bool:
    n = re.sub(r"\D", "", text)
    return 8 <= len(n) <= 15


def _date(text: str):
    try:
        return datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        return None


def handle_message(db: Session, session_id: str, text: str) -> ChatResponse:
    s = db.get(ConversationSession, session_id)
    if not s:
        raise ValueError("Unknown session")
    raw, low = text.strip(), text.strip().lower()
    ctx = _ctx(s)

    if s.language and low in {"0", "menu", "main", "main menu"}:
        s.state, s.current_journey = "main_menu", None
        db.commit()
        return _menu(s)
    if s.language and low in {"agent", "moemeli"}:
        s.state, s.current_journey = "agent_reason", "agent"
        db.commit()
        return _prompt(db, s)
    if s.language and low in {"cancel", "emisa"}:
        s.state, s.current_journey, s.context_json = "main_menu", None, "{}"
        db.commit()
        return _menu(s)

    if s.state == "choose_language":
        if low not in {"1", "2", "english", "sesotho"}:
            return _prompt(db, s)
        s.language = "st" if low in {"2", "sesotho"} else "en"
        s.state = "main_menu"
        db.commit()
        return _menu(s)

    if s.state == "main_menu":
        routes = {"1": ("policy_number", "policy"), "2": ("quote_product", "quote"), "3": ("claim_policy", "claim"), "4": ("agent_reason", "agent"), "5": ("faq_menu", "faq")}
        if low not in routes:
            return _menu(s)
        s.state, s.current_journey = routes[low]
        _audit(db, s, "journey_started", {"journey": s.current_journey})
        db.commit()
        return _prompt(db, s)

    if s.state == "policy_number":
        ctx["policy_number"] = raw.upper()
        _save(s, ctx)
        s.state = "policy_dob"
        db.commit()
        return _prompt(db, s)

    if s.state == "policy_dob":
        dob = _date(raw)
        policy = None if not dob else db.query(Policy).filter(Policy.policy_number == ctx.get("policy_number"), Policy.dob == dob).first()
        if not policy:
            ctx["policy_attempts"] = ctx.get("policy_attempts", 0) + 1
            _save(s, ctx)
            if ctx["policy_attempts"] >= 3:
                s.state, s.current_journey = "agent_reason", "agent"
                db.commit()
                return ChatResponse(session_id=s.id, messages=["We could not verify the policy. Please tell us what you need and an agent will assist."])
            s.state = "policy_number"
            db.commit()
            return ChatResponse(session_id=s.id, messages=["We could not verify those details. Please try again."] + _prompt(db, s).messages)
        _audit(db, s, "policy_verified", {"policy_number": policy.policy_number})
        s.state, s.current_journey, s.context_json = "main_menu", None, "{}"
        db.commit()
        msg = f"Policy verified. {policy.product} — Status: {policy.status}. Premium: {policy.currency} {policy.premium:,.2f}."
        menu = _menu(s)
        return ChatResponse(session_id=s.id, messages=[msg] + menu.messages, options=menu.options)

    if s.state == "quote_product":
        if low not in PRODUCTS:
            return _prompt(db, s)
        ctx["quote"] = {"product_key": low, "product": PRODUCTS[low][0], "risk": {}}
        _save(s, ctx)
        s.state = "quote_name"
        db.commit()
        return _prompt(db, s)

    if s.state == "quote_name":
        if len(raw) < 3:
            return _prompt(db, s)
        ctx["quote"]["name"] = raw
        _save(s, ctx)
        s.state = "quote_mobile"
        db.commit()
        return _prompt(db, s)

    if s.state == "quote_mobile":
        if not _valid_mobile(raw):
            return ChatResponse(session_id=s.id, messages=["Please enter a valid mobile number."])
        ctx["quote"]["mobile"] = raw
        _save(s, ctx)
        s.state = "quote_risk_0"
        db.commit()
        return _prompt(db, s)

    if s.state.startswith("quote_risk_"):
        idx = int(s.state.rsplit("_", 1)[1])
        q = ctx["quote"]
        fields = PRODUCTS[q["product_key"]][1]
        q["risk"][fields[idx][0]] = raw
        _save(s, ctx)
        s.state = f"quote_risk_{idx + 1}" if idx + 1 < len(fields) else "quote_consent"
        db.commit()
        return _prompt(db, s)

    if s.state == "quote_consent":
        if low not in {"yes", "y", "ee", "e", "1", "no", "n", "che", "2"}:
            return _prompt(db, s)
        if low in {"no", "n", "che", "2"}:
            s.state, s.current_journey = "main_menu", None
            db.commit()
            return _menu(s)
        q = ctx["quote"]
        ref = _ref("ZQ")
        db.add(Lead(reference=ref, session_id=s.id, name=q["name"], mobile=q["mobile"], product=q["product"], risk_json=json.dumps(q["risk"]), consent=True))
        _audit(db, s, "lead_created", {"reference": ref})
        s.state, s.current_journey, s.context_json = "main_menu", None, "{}"
        db.commit()
        menu = _menu(s)
        return ChatResponse(session_id=s.id, messages=[f"Thank you. Your quote request has been received. Reference: {ref}."] + menu.messages, options=menu.options)

    if s.state == "claim_policy":
        policy = db.query(Policy).filter(Policy.policy_number == raw.upper()).first()
        if not policy:
            s.state, s.current_journey = "agent_reason", "agent"
            db.commit()
            return ChatResponse(session_id=s.id, messages=["We could not confirm that policy automatically. Please tell us what happened and an agent will assist you."])
        ctx["claim"] = {"policy_number": policy.policy_number}
        _save(s, ctx)
        s.state = "claim_date"
        db.commit()
        return _prompt(db, s)

    if s.state == "claim_date":
        d = _date(raw)
        if not d or d > datetime.utcnow().date():
            return ChatResponse(session_id=s.id, messages=["Enter a valid incident date in dd/mm/yyyy and do not use a future date."])
        ctx["claim"]["loss_date"] = d.isoformat()
        _save(s, ctx)
        s.state = "claim_description"
        db.commit()
        return _prompt(db, s)

    if s.state == "claim_description":
        if len(raw) < 10:
            return _prompt(db, s)
        ctx["claim"]["description"] = raw
        _save(s, ctx)
        s.state = "claim_location"
        db.commit()
        return _prompt(db, s)

    if s.state == "claim_location":
        ctx["claim"]["location"] = raw
        _save(s, ctx)
        s.state = "claim_damage"
        db.commit()
        return _prompt(db, s)

    if s.state == "claim_damage":
        value = None
        if low not in {"unknown", "n/a", "ha ke tsebe"}:
            try:
                value = float(re.sub(r"[^0-9.]", "", raw))
            except ValueError:
                return _prompt(db, s)
        ctx["claim"]["estimated_damage"] = value
        _save(s, ctx)
        s.state = "claim_contact"
        db.commit()
        return _prompt(db, s)

    if s.state == "claim_contact":
        if not _valid_mobile(raw):
            return ChatResponse(session_id=s.id, messages=["Please enter a valid contact number."])
        c = ctx["claim"]
        ref = _ref("ZC")
        db.add(Claim(reference=ref, session_id=s.id, policy_number=c["policy_number"], loss_date=datetime.fromisoformat(c["loss_date"]).date(), description=c["description"], location=c["location"], estimated_damage=c.get("estimated_damage"), contact=raw))
        _audit(db, s, "claim_created", {"reference": ref})
        s.state, s.current_journey, s.context_json = "main_menu", None, "{}"
        db.commit()
        menu = _menu(s)
        return ChatResponse(session_id=s.id, messages=[f"Your claim has been registered. Claim reference: {ref}. You can now attach supporting photos or PDF documents below."] + menu.messages, options=menu.options, claim_reference=ref, allow_attachment=True)

    if s.state == "agent_reason":
        if len(raw) < 3:
            return _prompt(db, s)
        ref = _ref("ZA")
        queue = "Claims" if "claim" in low else "Sales / quotations" if "quote" in low else "Policy servicing" if "policy" in low else "General support"
        db.add(AgentTicket(reference=ref, session_id=s.id, reason=raw, queue=queue, language=s.language or "en"))
        _audit(db, s, "agent_ticket_created", {"reference": ref, "queue": queue})
        s.state, s.current_journey, s.context_json = "main_menu", None, "{}"
        db.commit()
        menu = _menu(s)
        return ChatResponse(session_id=s.id, messages=[f"Your support request has been created. Reference: {ref}. Queue: {queue}."] + menu.messages, options=menu.options)

    if s.state == "faq_menu":
        rows = db.query(FAQArticle).filter(FAQArticle.active.is_(True)).all()
        try:
            idx = int(low) - 1
        except ValueError:
            idx = -1
        if not 0 <= idx < len(rows):
            return _prompt(db, s)
        a = rows[idx]
        answer = a.answer_st if s.language == "st" else a.answer_en
        _audit(db, s, "faq_viewed", {"article_id": a.id})
        s.state, s.current_journey = "main_menu", None
        db.commit()
        menu = _menu(s)
        return ChatResponse(session_id=s.id, messages=[answer] + menu.messages, options=menu.options)

    s.state = "main_menu"
    db.commit()
    return _menu(s)

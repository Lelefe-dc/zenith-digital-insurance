# Zenith Digital Insurance Assistant

A runnable implementation of the **Zenith Horizon Insurance Company Limited** digital insurance assistant project manual.

## What is implemented

- Branded customer chat simulator with the supplied Zenith logo.
- English and draft Sesotho conversation packs.
- Five required journeys: **My Policy, Get a Quote, Report a Claim, Speak to an Agent, FAQ**.
- Policy verification using policy number + date of birth, with neutral failure messages and retry limits.
- Product-specific quote/lead capture for Motor, Property, Funeral and Life insurance.
- First-notification-of-loss claim capture with generated claim references.
- Claim evidence upload for JPG, PNG, WEBP and PDF files with file-size/type controls.
- Human-agent support tickets with basic queue routing and conversation linkage.
- FAQ content stored in the database.
- Audit events for material journey actions.
- Operations dashboard for recent leads, claims and support tickets.
- Meta WhatsApp Cloud API webhook verification, inbound message handling and outbound text adapter.
- SQLite for quick local demo and PostgreSQL configuration via Docker Compose.
- Demo seed policies and automated journey tests.

## Quick start (local Python)

```bash
cd zenith-digital-insurance-assistant
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
./scripts/start.sh
```

Open:

- Customer simulator: `http://localhost:8000/`
- Operations dashboard: `http://localhost:8000/admin`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

The default demo admin token is `change-me`. Change it in `.env` before any shared deployment.

## Demo policy

Use these values to test **My Policy**:

- Policy number: `ZEN-100001`
- Date of birth: `01/01/1990`

Other seeded policies are `ZEN-100002` and `ZEN-100003`.

## Docker / PostgreSQL

```bash
docker compose up --build
```

Then visit `http://localhost:8000/`.

## WhatsApp Cloud API

The project includes the webhook route:

- `GET /webhooks/whatsapp` — Meta verification
- `POST /webhooks/whatsapp` — inbound messages

Set these in `.env` or your deployment secret store:

```env
WHATSAPP_VERIFY_TOKEN=...
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_APP_SECRET=...
```

Configure the public HTTPS callback in Meta to point to:

`https://YOUR-DOMAIN/webhooks/whatsapp`

When WhatsApp credentials are blank, the browser simulator continues to work and outbound WhatsApp messages are only logged.

## Production work still requiring Zenith decisions / credentials

This repository is a complete functional MVP, but production launch requires external business systems and approved credentials. In particular:

1. Replace the demo policy table/lookup with Zenith's real policy/customer API.
2. Connect the lead flow to Zenith's CRM or sales queue.
3. Connect claims to the authoritative claims platform and document store.
4. Connect a real live-agent/contact-centre platform for synchronous handoff.
5. Add a real OTP provider and enable stronger identity verification before exposing richer policy data.
6. Add malware scanning/object storage for uploaded documents; the demo stores files locally.
7. Have Zenith approve the final Sesotho translations, privacy notices, retention policy and customer wording.
8. Put the admin dashboard behind Zenith SSO/RBAC; the demo uses a shared token.
9. Add production observability, backups, rate limiting and formal secret management.

## Test

```bash
pytest -q
```

## Core project structure

```text
app/
  main.py          API, admin endpoints, upload handling
  engine.py        conversation state machine and business journeys
  models.py        database models
  seed.py          demo policies and FAQ content
  whatsapp.py      Meta WhatsApp webhook + outbound adapter
  static/          branded simulator and admin dashboard
scripts/start.sh
Dockerfile
docker-compose.yml
```

## Security note

The demo deliberately returns only a limited policy summary. Policy number + DOB should not be treated as sufficient authentication for sensitive production servicing. The project is structured so Zenith can add OTP/stronger verification before production.
# zenith-digital-insurance

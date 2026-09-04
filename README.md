# Zenith Digital Insurance Assistant

A runnable implementation of the **Zenith Horizon Insurance Company Limited** digital insurance assistant project manual.

## What is implemented

- Branded customer chat simulator with the Zenith logo.
- English and draft Sesotho conversation packs.
- Five required journeys: **My Policy, Get a Quote, Report a Claim, Speak to an Agent, FAQ**.
- Policy verification using policy number + date of birth, with neutral failure messages and retry limits.
- Product-specific quote/lead capture for Motor, Property, Funeral and Life insurance.
- First-notification-of-loss claim capture with generated claim references.
- Claim evidence upload for JPG, PNG, WEBP and PDF files with file-size/type controls.
- Human-agent support tickets with queue routing and conversation linkage.
- FAQ content stored in the database.
- Audit events for material journey actions.
- Operations dashboard for recent leads, claims and support tickets.
- Meta WhatsApp Cloud API webhook verification, inbound message handling and outbound text adapter.
- SQLite for quick local development and PostgreSQL for the Docker stack.
- Demo seed policies and automated journey tests.

## Recommended start: Docker

Docker Compose starts both the application and PostgreSQL, waits for PostgreSQL to become healthy, persists the database and claim uploads in named volumes, and exposes the application on port `8000` by default.

```bash
git clone https://github.com/Lelefe-dc/zenith-digital-insurance.git
cd zenith-digital-insurance
cp .env.example .env
```

Before shared or production-like use, change at least these values in `.env`:

```env
ADMIN_TOKEN=replace-with-a-long-random-token
POSTGRES_PASSWORD=replace-with-a-strong-password
```

Start the complete stack:

```bash
docker compose up -d --build
```

Check container health and logs:

```bash
docker compose ps
docker compose logs -f app
```

Open:

- Customer simulator: `http://localhost:8000/`
- Operations dashboard: `http://localhost:8000/admin`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

Stop the stack without deleting data:

```bash
docker compose down
```

To also delete the PostgreSQL and uploaded-file volumes, use this only when you intentionally want to erase Docker-managed data:

```bash
docker compose down -v
```

Set `APP_PORT` in `.env` if port 8000 is already in use, for example `APP_PORT=8080`.

## Local Python start

For development without Docker:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
bash scripts/start.sh
```

The default local configuration uses SQLite. The default development admin token is `change-me`; change it before any shared deployment.

## Demo policy

Use these values to test **My Policy**:

- Policy number: `ZEN-100001`
- Date of birth: `01/01/1990`

Other seeded policies are `ZEN-100002` and `ZEN-100003`.

## Docker architecture

The Compose stack contains:

- `app` — FastAPI/Uvicorn application built from this repository.
- `db` — PostgreSQL 16 Alpine.
- `zenith_db` — persistent PostgreSQL data volume.
- `zenith_uploads` — persistent claim-attachment volume.
- `zenith` — isolated bridge network for app-to-database traffic.

The application image runs as a non-root user and includes a `/health` container health check. PostgreSQL also has a readiness health check, and the app waits for the database before starting.

Useful Docker commands:

```bash
# Rebuild after code changes
docker compose up -d --build

# Show running services and health
docker compose ps

# Follow all logs
docker compose logs -f

# Restart only the application
docker compose restart app

# Open a shell in the app container
docker compose exec app sh
```

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

When WhatsApp credentials are blank, the browser simulator continues to work and outbound WhatsApp messages are logged rather than sent.

## Production work still requiring Zenith decisions / credentials

This repository is a functional MVP. Production launch still requires integration with Zenith's authoritative systems and approved credentials, including:

1. Replace demo policy lookup with Zenith's real policy/customer API.
2. Connect quote leads to Zenith's CRM or sales queue.
3. Connect claims to the authoritative claims platform and document store.
4. Connect a live-agent/contact-centre platform for real-time handoff.
5. Add OTP/strong identity verification before exposing richer policy data.
6. Add malware scanning/object storage for uploaded documents.
7. Obtain approval for final Sesotho translations, privacy notices, retention policy and customer wording.
8. Put the operations dashboard behind Zenith SSO/RBAC.
9. Add production observability, backups, rate limiting and formal secret management.

## Test

```bash
pytest -q
```

GitHub Actions validates the Python tests, Docker Compose configuration, and application image build on pushes to `main` and pull requests targeting `main`.

## Core project structure

```text
app/
  main.py          API, admin endpoints, upload handling
  engine.py        conversation state machine and business journeys
  models.py        database models
  seed.py          demo policies and FAQ content
  whatsapp.py      Meta WhatsApp webhook + outbound adapter
  static/          branded simulator and operations dashboard
tests/
scripts/start.sh
Dockerfile
docker-compose.yml
.dockerignore
```

## Security note

The demo deliberately returns only a limited policy summary. Policy number + date of birth should not be treated as sufficient authentication for sensitive production servicing. The project is structured so stronger verification can be added before production.

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

## Ports

The Docker stack uses separate frontend and backend ports:

- Frontend: `http://localhost:3201`
- Backend API: `http://localhost:8201`
- API docs: `http://localhost:8201/docs`
- Backend health: `http://localhost:8201/health`

The frontend nginx container proxies browser `/api`, `/webhooks`, `/health`, `/docs`, `/redoc`, and `/openapi.json` requests to the backend over the private Docker network. This keeps the browser application same-origin while still exposing the backend directly on port `8201` for development and integrations.

## Recommended start: Docker

```bash
git clone https://github.com/Lelefe-dc/zenith-digital-insurance.git
cd zenith-digital-insurance
cp .env.example .env
```

Before shared or production-like use, change at least these values in `.env`:

```env
ADMIN_TOKEN=replace-with-a-long-random-token
POSTGRES_PASSWORD=replace-with-a-strong-password
FRONTEND_PORT=3201
BACKEND_PORT=8201
```

Start the complete stack:

```bash
docker compose up -d --build
```

Check container health and logs:

```bash
docker compose ps
docker compose logs -f frontend app db
```

Open:

- Customer simulator: `http://localhost:3201/`
- Operations dashboard: `http://localhost:3201/admin`
- API docs: `http://localhost:8201/docs`
- Backend health: `http://localhost:8201/health`

Stop the stack without deleting data:

```bash
docker compose down
```

To also delete the PostgreSQL and uploaded-file volumes, use this only when you intentionally want to erase Docker-managed data:

```bash
docker compose down -v
```

The default ports can be overridden in `.env` with `FRONTEND_PORT` and `BACKEND_PORT`.

## Local Python start

For development without Docker:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
bash scripts/start.sh
```

The non-Docker Python launcher still runs the combined FastAPI application directly. The Docker Compose setup is the recommended way to run the split frontend/backend deployment.

The default local configuration uses SQLite. The default development admin token is `change-me`; change it before any shared deployment.

## Demo policy

Use these values to test **My Policy**:

- Policy number: `ZEN-100001`
- Date of birth: `01/01/1990`

Other seeded policies are `ZEN-100002` and `ZEN-100003`.

## Docker architecture

The Compose stack contains:

- `frontend` — nginx serving the Zenith web interface on host port `3201` and reverse-proxying browser API requests to the backend.
- `app` — FastAPI/Uvicorn backend exposed on host port `8201` and listening on container port `8000`.
- `db` — PostgreSQL 16 Alpine.
- `zenith_db` — persistent PostgreSQL data volume.
- `zenith_uploads` — persistent claim-attachment volume.
- `zenith` — isolated bridge network for frontend, backend, and database traffic.

The backend image runs as a non-root user and includes a `/health` container health check. PostgreSQL has a readiness health check. The frontend waits for the backend to become healthy, and the backend waits for PostgreSQL before starting.

Useful Docker commands:

```bash
# Rebuild after code changes
docker compose up -d --build

# Show running services and health
docker compose ps

# Follow all logs
docker compose logs -f

# Follow only frontend/backend logs
docker compose logs -f frontend app

# Restart frontend and backend
docker compose restart frontend app

# Open a shell in the backend container
docker compose exec app sh
```

## WhatsApp Cloud API

The backend includes the webhook route:

- `GET /webhooks/whatsapp` — Meta verification
- `POST /webhooks/whatsapp` — inbound messages

Set these in `.env` or your deployment secret store:

```env
WHATSAPP_VERIFY_TOKEN=...
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_APP_SECRET=...
```

For a direct backend deployment, the callback can point to port `8201` during development. In production, expose the backend or reverse proxy over public HTTPS rather than a raw development port.

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

GitHub Actions validates the Python tests, Docker Compose configuration, backend image build, and frontend image build on pull requests targeting `main`.

## Core project structure

```text
app/
  main.py          API, admin endpoints, upload handling
  engine.py        conversation state machine and business journeys
  models.py        database models
  seed.py          demo policies and FAQ content
  whatsapp.py      Meta WhatsApp webhook + outbound adapter
  static/          branded simulator and operations dashboard
deploy/
  nginx.conf       frontend static serving + backend reverse proxy
tests/
scripts/start.sh
Dockerfile             backend image
Dockerfile.frontend    frontend nginx image
docker-compose.yml
.dockerignore
```

## Security note

The demo deliberately returns only a limited policy summary. Policy number + date of birth should not be treated as sufficient authentication for sensitive production servicing. The project is structured so stronger verification can be added before production.

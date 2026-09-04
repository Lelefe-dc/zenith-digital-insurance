# Zenith Digital Insurance Platform

A full-stack insurance management platform for **Zenith Horizon Insurance Company Limited** with a customer self-service assistant and a secure staff management system.

## Current phase

The project is now focused on the **core insurance management system**. WhatsApp integration is intentionally deferred until the management platform is complete and stable.

## What the management system includes

The staff portal at `/admin` now provides:

- Secure staff login with expiring database-backed sessions.
- Role-based access for Administrator, Manager, Underwriter, Claims, Finance, Agent and Viewer roles.
- Customer registration, editing, search and customer-level policy history.
- Insurance product catalogue and product pricing management.
- Policy issuance, servicing, assignment, cover values, payment frequency and payment status.
- Premium and payment capture with paid, pending, overdue, partial and reversed states.
- Sales lead and quotation pipeline management with stages, priorities, assignment and next actions.
- Claims operations with handler assignment, reserving, approved amounts, excess, decisions and workflow status.
- Operational tasks/work queues with priorities, due dates and ownership.
- Staff accounts, departments, branches and role administration.
- General case notes and management document metadata/upload support.
- Company/system settings.
- Management dashboard with portfolio, claims, premium and work-queue metrics.
- Summary reporting across policies, claims, leads, payments and tasks.
- CSV exports for customers, policies, claims, leads, payments and tasks.
- Audit events for material management actions.

The existing customer assistant remains available and continues to support:

- My Policy
- Get a Quote
- Report a Claim
- Speak to an Agent
- FAQ
- English and draft Sesotho journeys
- Claim evidence upload

## Ports

The Docker stack uses separate frontend and backend ports:

- Frontend and management UI: `http://localhost:3201`
- Management portal: `http://localhost:3201/admin`
- Backend API: `http://localhost:8201`
- API docs: `http://localhost:8201/docs`
- Backend health: `http://localhost:8201/health`

The frontend nginx container proxies browser API requests to the backend over the private Docker network.

## Start with Docker

```bash
git clone https://github.com/Lelefe-dc/zenith-digital-insurance.git
cd zenith-digital-insurance
cp .env.example .env
```

Change these values before shared use:

```env
MANAGEMENT_ADMIN_EMAIL=admin@zenith.local
MANAGEMENT_ADMIN_PASSWORD=replace-with-a-strong-password
POSTGRES_PASSWORD=replace-with-a-strong-database-password
FRONTEND_PORT=3201
BACKEND_PORT=8201
```

The management bootstrap credentials are only used to create the initial Administrator account when the database is first seeded. Changing the environment password later does not silently reset an existing staff password.

Start the stack:

```bash
docker compose up -d --build
```

Check services:

```bash
docker compose ps
docker compose logs -f frontend app db
```

Open:

- Customer assistant: `http://localhost:3201/`
- Insurance management system: `http://localhost:3201/admin`
- Swagger API: `http://localhost:8201/docs`
- Health: `http://localhost:8201/health`

Stop without deleting data:

```bash
docker compose down
```

Delete the database and uploaded-file volumes only when intentionally resetting all Docker-managed data:

```bash
docker compose down -v
```

## Management data model

The management layer extends the original assistant data with:

- `customers`
- `insurance_products`
- `branches`
- `staff_users`
- `management_sessions`
- `policy_profiles`
- `premium_payments`
- `lead_profiles`
- `claim_profiles`
- `work_tasks`
- `case_notes`
- `managed_documents`
- `system_settings`

The original `policies`, `leads`, `claims`, `claim_attachments`, conversation, FAQ and audit tables remain in use. This lets the management application operate on the same operational records produced by the customer assistant.

## Seed data

Development seed data includes:

- Administrator account from `MANAGEMENT_ADMIN_EMAIL` / `MANAGEMENT_ADMIN_PASSWORD`.
- Maseru, Teyateyaneng and Mafeteng branches.
- Motor, Property, Funeral and Life products.
- Three demonstration customers and policies.
- Demonstration premium records and work-queue tasks.

Customer assistant policy test:

```text
Policy: ZEN-100001
Date of birth: 01/01/1990
```

## Role model

The current application uses these roles:

- **Administrator** — full system and staff/settings administration.
- **Manager** — broad operational and reporting access.
- **Underwriter** — product and policy management.
- **Claims** — claim assessment and claims workflow.
- **Finance** — premium and payment management.
- **Agent** — customer, sales and task access.
- **Viewer** — read-oriented access.

The backend remains the authority for restricted actions; UI visibility is not treated as an access-control boundary.

## Management API

Core routes use the prefix:

```text
/api/v1/management
```

Major endpoint groups:

```text
/auth
/dashboard
/customers
/products
/branches
/policies
/payments
/leads
/claims
/tasks
/staff
/notes
/documents
/settings
/reports
/exports
```

Management sessions are sent as a Bearer token:

```http
Authorization: Bearer <management-token>
```

## Local Python development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
bash scripts/start.sh
```

Docker Compose is the recommended development path because it uses the same PostgreSQL-backed topology as the intended deployment architecture.

## WhatsApp phase

The existing Meta adapter remains in the repository for compatibility, but it is **not part of the current management-system phase**. No additional WhatsApp work should be treated as complete until the management platform, workflows, roles, reporting and production data integrations are ready.

The final WhatsApp phase will connect the approved customer journeys to this management system so that messages create and update the same customers, leads, claims, policies and service records used by staff.

## Production hardening still required

Before production launch, Zenith should complete or approve:

1. Authoritative policy/customer data migration or integration.
2. Formal database migrations and release procedures.
3. SSO/MFA or enterprise identity integration for staff.
4. Detailed permission matrix and segregation-of-duties review.
5. Strong password policy, account lockout and recovery workflow.
6. Object storage and malware scanning for documents.
7. Encryption, secret management and key rotation.
8. Data retention and privacy policies.
9. Backup, restore and disaster-recovery procedures.
10. Monitoring, alerting, structured logs and performance telemetry.
11. Formal underwriting, claims and finance approval workflows.
12. Production reporting requirements and statutory/regulatory reports.
13. External payment, accounting and banking integrations where required.
14. Final Sesotho wording and customer communication approval.
15. WhatsApp Business integration as the final customer-channel phase.

## Tests and CI

Run locally:

```bash
pytest -q
```

GitHub Actions validates:

- Python tests
- Docker Compose configuration
- Backend image build
- Frontend image build

## Project structure

```text
app/
  main.py                  FastAPI application
  engine.py                customer-assistant conversation engine
  models.py                original assistant operational models
  management.py            authenticated management API
  management_models.py     management data model
  management_schemas.py    management request validation
  security.py              password/session hashing utilities
  seed.py                  development seed data
  whatsapp.py              deferred WhatsApp adapter
  static/
    index.html              customer assistant
    admin.html              insurance management application
    admin.js                management frontend logic
    management.css          management UI styling
    styles.css              customer UI styling
deploy/
  nginx.conf
tests/
Dockerfile
Dockerfile.frontend
docker-compose.yml
```

## Security note

The customer assistant's policy number + date-of-birth verification is still a demonstration mechanism and is not sufficient for sensitive production servicing. Stronger customer identity verification should be completed before production exposure of detailed policy data.

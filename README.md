# LedgerPulse Backend

Flask REST API for LedgerPulse. Firebase Authentication is the identity provider; PostgreSQL is the authoritative business-data store.

## Architecture

`Firebase Auth -> Flask API -> SQLAlchemy/PostgreSQL`

The browser sends a Firebase ID token in `Authorization: Bearer <token>`. The API verifies the token server-side and resolves organization membership and RBAC from PostgreSQL. Client-provided organization IDs, roles, and identity fields are never trusted for authorization.

## Local setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

Create a PostgreSQL database named `ledgerpulse_db`, set `DATABASE_URL`, and configure Firebase Admin credentials.

Apply schema:

```bash
flask --app backend.app db upgrade
```

Optional sample data:

```bash
python -m backend.seed
```

Run the API:

```bash
flask --app backend.app run --host 0.0.0.0 --port 5000
```

Production uses Gunicorn. The Docker setup runs migrations before starting the API. The same image can run the dedicated recurring scheduler with `python -m backend.scheduler`; the provided Compose file runs the scheduler separately so multiple web workers cannot duplicate jobs.

## Authentication

Provide Firebase Admin credentials through `FIREBASE_PROJECT_ID`, `FIREBASE_CLIENT_EMAIL`, and `FIREBASE_PRIVATE_KEY`, or use `GOOGLE_APPLICATION_CREDENTIALS` for a service-account JSON file.

## Email

Invoice email and team invitations use SMTP when configured. The public website contact form also uses SMTP and delivers inquiries to `CONTACT_INBOX_EMAIL` (falling back to `SMTP_FROM_EMAIL`). The API never reports delivery success when SMTP is unavailable.

## API groups

- `/api/auth/*` identity bootstrap and organization discovery
- `/api/organizations/*` organizations, settings, summary, members and invitations
- `/api/customers/*`
- `/api/vendors/*`
- `/api/invoices/*`
- `/api/payments/*`
- `/api/expenses/*`
- `/api/recurring/*`
- `/api/activities/*`
- `/api/contact` public website inquiry delivery
- `/api/health` public liveness
- `/api/health/details` platform-admin diagnostics
- `/api/admin/overview` platform-admin operational overview

## Migrations

Use Flask-Migrate/Alembic. Do not call `db.create_all()` for deployment schema management.

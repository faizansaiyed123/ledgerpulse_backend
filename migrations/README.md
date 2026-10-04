# LedgerPulse database migrations

LedgerPulse uses Flask-Migrate/Alembic for database schema changes.

```bash
flask --app backend.app db upgrade
flask --app backend.app db current
```

Review generated revisions before applying them to production.

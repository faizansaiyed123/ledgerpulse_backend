import hashlib
import logging
import time

from sqlalchemy import text

from backend.app import create_app
from backend.database import db
from backend.models import Organization
from backend.services.recurring import run_for_org

LOG = logging.getLogger("ledgerpulse.scheduler")
LOCK_KEY = int.from_bytes(hashlib.sha256(b"ledgerpulse-recurring-scheduler").digest()[:8], "big", signed=True)
INTERVAL_SECONDS = 300


def _try_lock() -> bool:
    return bool(db.session.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar())


def _unlock() -> None:
    db.session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
    db.session.commit()


def run_cycle() -> int:
    generated = 0
    if not _try_lock():
        db.session.rollback()
        return 0
    try:
        for org in Organization.query.order_by(Organization.created_at.asc()).all():
            try:
                invoices = run_for_org(org.id, "system:scheduler")
                generated += len(invoices)
            except Exception:
                db.session.rollback()
                LOG.exception("Recurring cycle failed for organization %s", org.id)
        return generated
    finally:
        _unlock()


def main() -> None:
    app = create_app()
    with app.app_context():
        while True:
            try:
                count = run_cycle()
                LOG.info("Recurring scheduler cycle generated %s invoice(s)", count)
            except Exception:
                db.session.rollback()
                LOG.exception("Recurring scheduler cycle failed")
            finally:
                db.session.remove()
            time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

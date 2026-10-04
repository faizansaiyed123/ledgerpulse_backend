from datetime import datetime, timezone
import uuid

from flask import has_request_context

from backend.auth import current_user
from backend.database import db
from backend.models import ActivityLog


def record_activity(org_id, action, entity_type="organization", entity_id=None, details="", *, actor_uid=None, actor_email=None, actor_name=None):
    user = None
    if actor_uid is None and has_request_context():
        user = current_user()
    activity = ActivityLog(
        id=f"act_{uuid.uuid4().hex}",
        org_id=org_id,
        user_id=actor_uid or (user.get("uid") if user else None),
        user_email=actor_email or (user.get("email") if user else None),
        user_name=actor_name or (user.get("name") if user else None),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(activity)
    return activity

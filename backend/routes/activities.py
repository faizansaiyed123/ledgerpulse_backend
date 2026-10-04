from flask import Blueprint, jsonify, request

from backend.auth import require_auth, require_org_membership
from backend.models import ActivityLog
from backend.database import db

activity_bp = Blueprint("activities", __name__)


@activity_bp.route("/activities", methods=["GET"])
@require_auth
def get_activities():
    org_id = request.args.get("org_id")
    if not org_id:
        return jsonify({"error": "org_id is required"}), 400
    result, error = require_org_membership(org_id)
    if error:
        return error
    try:
        limit = min(max(int(request.args.get("limit", 100)), 1), 200)
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400
    activities = ActivityLog.query.filter_by(org_id=org_id).order_by(ActivityLog.created_at.desc()).limit(limit).all()
    return jsonify([a.to_dict() for a in activities]), 200


@activity_bp.route("/activities", methods=["POST"])
@require_auth
def create_activity():
    data = request.get_json() or {}
    org_id = data.get("orgId")
    if not org_id or not isinstance(org_id, str):
        return jsonify({"error": "orgId is required"}), 400
    result, error = require_org_membership(org_id)
    if error:
        return error
    from backend.services.audit import record_activity
    action = str(data.get("action") or "Activity").strip()
    entity_type = str(data.get("entityType") or "organization").strip()
    entity_id = str(data.get("entityId") or "").strip()
    details = str(data.get("details") or "").strip()
    if not action or len(action) > 255:
        return jsonify({"error": "action is required and must be at most 255 characters"}), 400
    if len(entity_type) > 50 or len(entity_id) > 100 or len(details) > 5000:
        return jsonify({"error": "Activity fields exceed the allowed length"}), 400
    activity = record_activity(
        org_id,
        action,
        entity_type,
        entity_id or None,
        details,
    )
    db.session.commit()
    return jsonify(activity.to_dict()), 201

import uuid
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify

from backend.auth import require_auth, current_user
from backend.database import db
from backend.models import Organization, OrganizationMember


auth_bp = Blueprint("auth", __name__)


def _ensure_first_organization(user):
    memberships = (
        OrganizationMember.query.filter_by(user_id=user["uid"], status="active")
        .order_by(OrganizationMember.created_at.asc())
        .all()
    )
    if memberships:
        return memberships

    org_id = f"org_{uuid.uuid4().hex[:12]}"
    org = Organization(
        id=org_id,
        name=f"{user['name'] or 'My'} Workspace",
        currency="USD",
        default_payment_terms=30,
        created_by=user["uid"],
        slug=org_id,
    )
    member = OrganizationMember(
        id=f"mem_{uuid.uuid4().hex[:12]}",
        org_id=org_id,
        user_id=user["uid"],
        user_email=user.get("email", ""),
        user_name=user.get("name", ""),
        role="owner",
        status="active",
        joined_at=datetime.now(timezone.utc),
    )
    db.session.add_all([org, member])
    db.session.commit()
    return [member]


def _me_payload():
    user = current_user()
    memberships = (
        OrganizationMember.query.filter_by(user_id=user["uid"], status="active")
        .order_by(OrganizationMember.created_at.asc())
        .all()
    )
    pending_invitations = OrganizationMember.query.filter(
        OrganizationMember.user_id.is_(None),
        OrganizationMember.status == "invited",
        db.func.lower(OrganizationMember.user_email) == (user.get("email", "").lower()),
    ).all()
    if not memberships and not pending_invitations:
        memberships = _ensure_first_organization(user)
    return {
        "user": {
            "uid": user["uid"],
            "email": user.get("email", ""),
            "displayName": user.get("name", "") or user.get("email", "").split("@")[0] or "User",
        },
        "organizations": [m.organization.to_dict() for m in memberships],
        "memberships": [m.to_dict() for m in memberships],
        "isPlatformAdmin": user["uid"] in current_app.config.get("PLATFORM_ADMIN_UIDS", set()),
        "pendingInvitations": [
            {"orgId": m.org_id, "organizationName": m.organization.name, "role": m.role}
            for m in pending_invitations
        ],
    }


@auth_bp.route("/auth/me", methods=["GET"])
@require_auth
def me():
    return jsonify(_me_payload()), 200


@auth_bp.route("/auth/bootstrap", methods=["POST"])
@require_auth
def bootstrap():
    return jsonify(_me_payload()), 200

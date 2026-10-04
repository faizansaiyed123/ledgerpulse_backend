import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from backend.auth import current_user, require_auth, require_org_membership
from backend.database import db
from backend.models import Customer, Expense, Invoice, Organization, OrganizationMember, Payment
from backend.services.audit import record_activity
from backend.services.email import EmailNotConfiguredError, send_email
from backend.utils import ALLOWED_CURRENCIES, MEMBER_ROLES, clean_text


org_bp = Blueprint("organizations", __name__)


def _member_response(member):
    return jsonify(member.to_dict())


@org_bp.route("/organizations", methods=["POST"])
@require_auth
def create_organization():
    data = request.get_json() or {}
    name = clean_text(data.get("name"), "name", required=True, max_length=255)
    currency = clean_text(data.get("currency", "USD"), "currency", required=True, max_length=10).upper()
    if currency not in ALLOWED_CURRENCIES:
        return jsonify({"error": "Unsupported currency"}), 400

    user = current_user()
    org_id = f"org_{secrets.token_hex(8)}"
    org = Organization(
        id=org_id,
        name=name,
        currency=currency,
        default_payment_terms=30,
        created_by=user["uid"],
        slug=re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80] or org_id,
    )
    member = OrganizationMember(
        id=f"mem_{secrets.token_hex(8)}",
        org_id=org_id,
        user_id=user["uid"],
        user_email=user.get("email", ""),
        user_name=user.get("name", ""),
        role="owner",
        status="active",
        joined_at=datetime.now(timezone.utc),
    )
    db.session.add_all([org, member])
    record_activity(org_id, "Created organization", "organization", org_id, f"Created by {user.get('email', '')}")
    db.session.commit()
    return jsonify(org.to_dict()), 201


@org_bp.route("/organizations/<org_id>", methods=["GET"])
@require_auth
def get_organization(org_id):
    result, error = require_org_membership(org_id)
    if error:
        return error
    org, _member = result
    return jsonify(org.to_dict()), 200


@org_bp.route("/organizations/<org_id>", methods=["PUT"])
@require_auth
def update_organization(org_id):
    result, error = require_org_membership(org_id, roles={"owner", "admin"})
    if error:
        return error
    org, _member = result
    data = request.get_json() or {}

    if "name" in data:
        org.name = clean_text(data["name"], "name", required=True, max_length=255)
    if "taxId" in data:
        org.tax_id = clean_text(data["taxId"], "taxId", max_length=100)
    for field, attr, max_len in (
        ("address", "address", 5000),
        ("city", "city", 100),
        ("state", "state", 100),
        ("postalCode", "postal_code", 30),
        ("country", "country", 100),
        ("phone", "phone", 50),
        ("email", "email", 255),
        ("website", "website", 255),
        ("logoUrl", "logo_url", 2000),
        ("fiscalYearStart", "fiscal_year_start", 20),
        ("invoiceNotes", "invoice_notes", 10000),
        ("invoiceTerms", "invoice_terms", 10000),
    ):
        if field in data:
            setattr(org, attr, clean_text(data[field], field, max_length=max_len))
    if "currency" in data:
        currency = clean_text(data["currency"], "currency", required=True, max_length=10).upper()
        if currency not in ALLOWED_CURRENCIES:
            return jsonify({"error": "Unsupported currency"}), 400
        org.currency = currency
    if "paymentTermsDays" in data:
        try:
            terms = int(data["paymentTermsDays"])
        except (TypeError, ValueError):
            return jsonify({"error": "paymentTermsDays must be an integer"}), 400
        if terms < 0 or terms > 3650:
            return jsonify({"error": "paymentTermsDays must be between 0 and 3650"}), 400
        org.default_payment_terms = terms

    record_activity(org_id, "Updated business profile", "organization", org_id, "Organization settings updated")
    db.session.commit()
    return jsonify(org.to_dict()), 200


@org_bp.route("/organizations/<org_id>/summary", methods=["GET"])
@require_auth
def get_org_summary(org_id):
    result, error = require_org_membership(org_id)
    if error:
        return error

    invoices = Invoice.query.filter_by(org_id=org_id).all()
    expenses = Expense.query.filter_by(org_id=org_id).all()
    payments = Payment.query.filter_by(org_id=org_id).all()
    customers = Customer.query.filter_by(org_id=org_id).all()

    total_revenue = sum((inv.total_amount for inv in invoices if inv.status != "cancelled"), start=Decimal("0"))
    total_paid = sum((inv.paid_amount for inv in invoices if inv.status != "cancelled"), start=Decimal("0"))
    outstanding = sum((inv.balance_due for inv in invoices if inv.status not in ("cancelled", "paid")), start=Decimal("0"))
    total_expenses = sum((exp.amount for exp in expenses if exp.status != "rejected"), start=Decimal("0"))

    return jsonify({
        "totalRevenue": float(total_revenue),
        "totalCollected": float(total_paid),
        "outstandingBalance": float(outstanding),
        "totalExpenses": float(total_expenses),
        "netProfit": float(total_paid - total_expenses),
        "invoiceCount": len(invoices),
        "customerCount": len(customers),
        "paymentCount": len(payments),
    }), 200


@org_bp.route("/organizations/<org_id>/members", methods=["GET"])
@require_auth
def get_members(org_id):
    result, error = require_org_membership(org_id)
    if error:
        return error
    members = OrganizationMember.query.filter_by(org_id=org_id).order_by(OrganizationMember.created_at.asc()).all()
    return jsonify([m.to_dict() for m in members]), 200


@org_bp.route("/organizations/<org_id>/members/invitations", methods=["POST"])
@require_auth
def invite_member(org_id):
    result, error = require_org_membership(org_id, roles={"owner", "admin"})
    if error:
        return error
    org, _member = result
    data = request.get_json() or {}
    email = clean_text(data.get("email"), "email", required=True, max_length=255).lower()
    name = clean_text(data.get("name"), "name", max_length=255)
    role = clean_text(data.get("role", "staff"), "role", required=True, max_length=30)
    if role not in {"admin", "accountant", "staff"}:
        return jsonify({"error": "Invalid invitation role"}), 400

    existing = OrganizationMember.query.filter(
        OrganizationMember.org_id == org_id,
        func.lower(OrganizationMember.user_email) == email,
        OrganizationMember.status.in_(["active", "invited"]),
    ).first()
    if existing:
        return jsonify({"error": "A member or pending invitation already exists for this email"}), 409

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    member = OrganizationMember(
        id=f"mem_{secrets.token_hex(8)}",
        org_id=org_id,
        user_email=email,
        user_name=name or email.split("@")[0],
        role=role,
        status="invited",
        invitation_token_hash=token_hash,
        invitation_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.session.add(member)
    record_activity(org_id, "Invited team member", "team", member.id, f"Invitation sent to {email}")
    db.session.commit()

    invitation_url = f"{current_app.config['FRONTEND_URL']}/?invite={raw_token}&org={org_id}"
    sent = False
    email_message = "SMTP is not configured; share the invitation link manually."
    try:
        message_id = send_email(
            to_email=email,
            subject=f"You have been invited to {org.name} on LedgerPulse",
            text_body=(
                f"{current_user()['name'] or 'A teammate'} invited you to {org.name} as {role}.\n\n"
                f"Accept your invitation by signing in through: {invitation_url}\n"
                "This invitation expires in 7 days."
            ),
        )
        sent = True
        email_message = f"Invitation email sent ({message_id})."
    except EmailNotConfiguredError:
        pass
    except Exception:
        current_app.logger.exception("Failed to send invitation email")
        email_message = "Invitation was created, but email delivery failed. Share the invitation link manually."

    return jsonify({"member": member.to_dict(), "invitationUrl": invitation_url, "sent": sent, "message": email_message}), 201


@org_bp.route("/organizations/<org_id>/members/<member_id>", methods=["PUT"])
@require_auth
def update_member(org_id, member_id):
    result, error = require_org_membership(org_id, roles={"owner", "admin"})
    if error:
        return error
    _org, current_member = result
    member = OrganizationMember.query.filter_by(id=member_id, org_id=org_id).first()
    if not member:
        return jsonify({"error": "Member not found"}), 404
    data = request.get_json() or {}
    if "role" in data:
        role = clean_text(data["role"], "role", required=True, max_length=30)
        if role not in MEMBER_ROLES or role == "owner":
            return jsonify({"error": "Invalid member role"}), 400
        if member.role == "owner":
            return jsonify({"error": "The organization owner role cannot be reassigned"}), 400
        member.role = role
    record_activity(org_id, "Updated member role", "team", member.id, f"Role changed to {member.role}")
    db.session.commit()
    return _member_response(member)


@org_bp.route("/organizations/<org_id>/members/<member_id>", methods=["DELETE"])
@require_auth
def remove_member(org_id, member_id):
    result, error = require_org_membership(org_id, roles={"owner", "admin"})
    if error:
        return error
    _org, current_member = result
    member = OrganizationMember.query.filter_by(id=member_id, org_id=org_id).first()
    if not member:
        return jsonify({"error": "Member not found"}), 404
    if member.role == "owner" or member.id == current_member.id:
        return jsonify({"error": "The owner/current administrator cannot remove this membership"}), 400
    record_activity(org_id, "Removed team member", "team", member.id, f"Removed {member.user_email}")
    db.session.delete(member)
    db.session.commit()
    return jsonify({"message": "Member removed successfully"}), 200


@org_bp.route("/organizations/<org_id>/invitations/accept", methods=["POST"])
@require_auth
def accept_invitation(org_id):
    user = current_user()
    data = request.get_json() or {}
    token = clean_text(data.get("token"), "token", required=True, max_length=256)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    member = OrganizationMember.query.filter_by(org_id=org_id, invitation_token_hash=token_hash, status="invited").with_for_update().first()
    if not member:
        return jsonify({"error": "Invitation not found or already accepted"}), 404
    if member.invitation_expires_at and member.invitation_expires_at < datetime.now(timezone.utc):
        return jsonify({"error": "Invitation has expired"}), 410
    if member.user_email.lower() != user.get("email", "").lower():
        return jsonify({"error": "Sign in with the invited email address"}), 403

    active = OrganizationMember.query.filter_by(org_id=org_id, user_id=user["uid"], status="active").first()
    if active:
        return jsonify({"error": "You are already an active member of this organization"}), 409
    member.user_id = user["uid"]
    member.status = "active"
    member.joined_at = datetime.now(timezone.utc)
    member.invitation_token_hash = None
    member.invitation_expires_at = None
    record_activity(org_id, "Accepted team invitation", "team", member.id, f"Accepted by {user.get('email', '')}")
    db.session.commit()
    return jsonify(member.to_dict()), 200


@org_bp.route("/organizations/<org_id>/sample-data", methods=["POST"])
@require_auth
def load_sample_data(org_id):
    result, error = require_org_membership(org_id, roles={"owner", "admin"})
    if error:
        return error
    from backend.seed import seed_sample_for_org
    try:
        counts = seed_sample_for_org(org_id, current_user()["uid"])
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 409
    return jsonify(counts), 201

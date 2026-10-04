import uuid

from flask import Blueprint, jsonify, request

from backend.auth import require_auth, require_org_membership
from backend.database import db
from backend.models import Expense, Vendor
from backend.services.audit import record_activity
from backend.utils import EXPENSE_CATEGORIES, clean_text

vendor_bp = Blueprint("vendors", __name__)


def _authorized_vendor(vendor_id, roles=None):
    vendor = Vendor.query.get(vendor_id)
    if not vendor:
        return None, None, (jsonify({"error": "Vendor not found"}), 404)
    result, error = require_org_membership(vendor.org_id, roles=roles)
    if error:
        return None, None, error
    return vendor, result[0], None


@vendor_bp.route("/vendors", methods=["GET"])
@require_auth
def get_vendors():
    org_id = request.args.get("org_id")
    if not org_id:
        return jsonify({"error": "org_id is required"}), 400
    result, error = require_org_membership(org_id)
    if error:
        return error
    vendors = Vendor.query.filter_by(org_id=org_id).order_by(Vendor.created_at.desc()).all()
    return jsonify([vendor.to_dict() for vendor in vendors]), 200


@vendor_bp.route("/vendors", methods=["POST"])
@require_auth
def create_vendor():
    data = request.get_json() or {}
    org_id = clean_text(data.get("orgId"), "orgId", required=True, max_length=100)
    result, error = require_org_membership(org_id, roles={"owner", "admin", "accountant"})
    if error:
        return error
    try:
        name = clean_text(data.get("name"), "name", required=True, max_length=255)
        category = clean_text(data.get("category", "other"), "category", required=True, max_length=100)
        if category not in EXPENSE_CATEGORIES:
            raise ValueError("Invalid vendor expense category")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    vendor = Vendor(
        id=f"vend_{uuid.uuid4().hex}",
        org_id=org_id,
        name=name,
        email=clean_text(data.get("email"), "email", max_length=255),
        phone=clean_text(data.get("phone"), "phone", max_length=50),
        company=clean_text(data.get("company"), "company", max_length=255),
        tax_id=clean_text(data.get("taxId"), "taxId", max_length=100),
        category=category,
        address=clean_text(data.get("address"), "address", max_length=5000),
        notes=clean_text(data.get("notes"), "notes", max_length=10000),
    )
    db.session.add(vendor)
    record_activity(org_id, "Created vendor", "vendor", vendor.id, vendor.name)
    db.session.commit()
    return jsonify(vendor.to_dict()), 201


@vendor_bp.route("/vendors/<id>", methods=["PUT"])
@require_auth
def update_vendor(id):
    vendor, _org, error = _authorized_vendor(id, roles={"owner", "admin", "accountant"})
    if error:
        return error
    data = request.get_json() or {}
    try:
        for field, attr, max_len in (
            ("name", "name", 255),
            ("email", "email", 255),
            ("phone", "phone", 50),
            ("company", "company", 255),
            ("taxId", "tax_id", 100),
            ("address", "address", 5000),
            ("notes", "notes", 10000),
        ):
            if field in data:
                setattr(vendor, attr, clean_text(data[field], field, required=field == "name", max_length=max_len))
        if "category" in data:
            category = clean_text(data["category"], "category", required=True, max_length=100)
            if category not in EXPENSE_CATEGORIES:
                raise ValueError("Invalid vendor expense category")
            vendor.category = category
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    record_activity(vendor.org_id, "Updated vendor", "vendor", vendor.id, vendor.name)
    db.session.commit()
    return jsonify(vendor.to_dict()), 200


@vendor_bp.route("/vendors/<id>", methods=["DELETE"])
@require_auth
def delete_vendor(id):
    vendor, _org, error = _authorized_vendor(id, roles={"owner", "admin"})
    if error:
        return error
    if Expense.query.filter_by(vendor_id=vendor.id).first():
        return jsonify({"error": "Cannot delete a vendor that has linked expenses"}), 409
    record_activity(vendor.org_id, "Deleted vendor", "vendor", vendor.id, vendor.name)
    db.session.delete(vendor)
    db.session.commit()
    return jsonify({"message": "Vendor deleted successfully"}), 200

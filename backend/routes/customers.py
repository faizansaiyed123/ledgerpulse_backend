import uuid

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from backend.auth import require_auth, require_org_membership
from backend.database import db
from backend.models import Customer, Invoice
from backend.services.audit import record_activity
from backend.utils import ALLOWED_CURRENCIES, clean_text

customer_bp = Blueprint("customers", __name__)


def _authorized_customer(customer_id, roles=None):
    customer = Customer.query.get(customer_id)
    if not customer:
        return None, None, (jsonify({"error": "Customer not found"}), 404)
    result, error = require_org_membership(customer.org_id, roles=roles)
    if error:
        return None, None, error
    return customer, result[0], None


@customer_bp.route("/customers", methods=["GET"])
@require_auth
def get_customers():
    org_id = request.args.get("org_id")
    if not org_id:
        return jsonify({"error": "org_id is required"}), 400
    result, error = require_org_membership(org_id)
    if error:
        return error
    customers = Customer.query.filter_by(org_id=org_id).order_by(Customer.created_at.desc()).all()
    return jsonify([c.to_dict() for c in customers]), 200


@customer_bp.route("/customers/<id>", methods=["GET"])
@require_auth
def get_customer(id):
    customer, _org, error = _authorized_customer(id)
    if error:
        return error
    return jsonify(customer.to_dict()), 200


@customer_bp.route("/customers", methods=["POST"])
@require_auth
def create_customer():
    data = request.get_json() or {}
    name = clean_text(data.get("name"), "name", required=True, max_length=255)
    org_id = clean_text(data.get("orgId"), "orgId", required=True, max_length=100)
    result, error = require_org_membership(org_id, roles={"owner", "admin", "accountant"})
    if error:
        return error
    org, _member = result
    currency = clean_text(data.get("currency", org.currency), "currency", max_length=10).upper()
    if currency not in ALLOWED_CURRENCIES:
        return jsonify({"error": "Unsupported currency"}), 400
    try:
        terms = int(data.get("paymentTermsDays", data.get("paymentTerms", 30)))
    except (TypeError, ValueError):
        return jsonify({"error": "paymentTermsDays must be an integer"}), 400
    if not 0 <= terms <= 3650:
        return jsonify({"error": "paymentTermsDays must be between 0 and 3650"}), 400

    customer_id = f"cust_{uuid.uuid4().hex}"
    customer = Customer(
        id=customer_id,
        org_id=org_id,
        name=name,
        email=clean_text(data.get("email"), "email", max_length=255),
        phone=clean_text(data.get("phone"), "phone", max_length=50),
        company_name=clean_text(data.get("company", data.get("companyName")), "company", max_length=255),
        address=clean_text(data.get("billingAddress", data.get("address")), "billingAddress", max_length=5000),
        city=clean_text(data.get("city"), "city", max_length=100),
        country=clean_text(data.get("country"), "country", max_length=100),
        tax_id=clean_text(data.get("taxId"), "taxId", max_length=100),
        currency=currency,
        payment_terms=terms,
        notes=clean_text(data.get("notes"), "notes", max_length=10000),
    )
    db.session.add(customer)
    record_activity(org_id, "Created customer", "customer", customer.id, customer.name)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Customer ID collision; please retry"}), 409
    return jsonify(customer.to_dict()), 201


@customer_bp.route("/customers/<id>", methods=["PUT"])
@require_auth
def update_customer(id):
    customer, _org, error = _authorized_customer(id, roles={"owner", "admin", "accountant"})
    if error:
        return error
    data = request.get_json() or {}
    if "name" in data:
        customer.name = clean_text(data["name"], "name", required=True, max_length=255)
    for field, attr, max_len in (
        ("email", "email", 255),
        ("phone", "phone", 50),
        ("company", "company_name", 255),
        ("companyName", "company_name", 255),
        ("billingAddress", "address", 5000),
        ("address", "address", 5000),
        ("city", "city", 100),
        ("country", "country", 100),
        ("taxId", "tax_id", 100),
        ("notes", "notes", 10000),
    ):
        if field in data:
            setattr(customer, attr, clean_text(data[field], field, max_length=max_len))
    if "currency" in data:
        currency = clean_text(data["currency"], "currency", required=True, max_length=10).upper()
        if currency not in ALLOWED_CURRENCIES:
            return jsonify({"error": "Unsupported currency"}), 400
        customer.currency = currency
    if "paymentTermsDays" in data or "paymentTerms" in data:
        try:
            terms = int(data.get("paymentTermsDays", data.get("paymentTerms")))
        except (TypeError, ValueError):
            return jsonify({"error": "paymentTermsDays must be an integer"}), 400
        if not 0 <= terms <= 3650:
            return jsonify({"error": "paymentTermsDays must be between 0 and 3650"}), 400
        customer.payment_terms = terms

    record_activity(customer.org_id, "Updated customer", "customer", customer.id, customer.name)
    db.session.commit()
    return jsonify(customer.to_dict()), 200


@customer_bp.route("/customers/<id>", methods=["DELETE"])
@require_auth
def delete_customer(id):
    customer, _org, error = _authorized_customer(id, roles={"owner", "admin"})
    if error:
        return error
    if Invoice.query.filter_by(customer_id=customer.id).first():
        return jsonify({"error": "Cannot delete customer with linked invoices"}), 409
    record_activity(customer.org_id, "Deleted customer", "customer", customer.id, customer.name)
    db.session.delete(customer)
    db.session.commit()
    return jsonify({"message": "Customer deleted successfully"}), 200

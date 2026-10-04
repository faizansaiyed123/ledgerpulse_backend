from datetime import date
from decimal import Decimal
import uuid

from flask import Blueprint, jsonify, request

from backend.auth import current_user, require_auth, require_org_membership
from backend.database import db
from backend.models import Customer, RecurringInvoice
from backend.routes.invoices import _normalize_items
from backend.services.audit import record_activity
from backend.services.recurring import run_for_org
from backend.utils import ALLOWED_CURRENCIES, RECURRING_FREQUENCIES, clean_text, money, parse_date

recurring_bp = Blueprint("recurring", __name__)


def _authorized(rec_id, roles=None):
    rec = RecurringInvoice.query.get(rec_id)
    if not rec:
        return None, None, (jsonify({"error": "Recurring invoice not found"}), 404)
    result, error = require_org_membership(rec.org_id, roles=roles)
    if error:
        return None, None, error
    return rec, result[0], None


@recurring_bp.route("/recurring", methods=["GET"])
@require_auth
def get_recurring():
    org_id = request.args.get("org_id")
    if not org_id:
        return jsonify({"error": "org_id is required"}), 400
    result, error = require_org_membership(org_id)
    if error:
        return error
    records = RecurringInvoice.query.filter_by(org_id=org_id).order_by(RecurringInvoice.next_run_date.asc()).all()
    return jsonify([record.to_dict() for record in records]), 200


@recurring_bp.route("/recurring", methods=["POST"])
@require_auth
def create_recurring():
    data = request.get_json() or {}
    try:
        org_id = clean_text(data.get("orgId"), "orgId", required=True, max_length=100)
        result, error = require_org_membership(org_id, roles={"owner", "admin", "accountant"})
        if error:
            return error
        org = result[0]
        items = _normalize_items(data.get("items"))
        frequency = clean_text(data.get("frequency"), "frequency", required=True, max_length=20)
        if frequency not in RECURRING_FREQUENCIES:
            raise ValueError("Invalid recurring frequency")
        next_run = parse_date(data.get("nextRunDate"), "nextRunDate")
        customer_id = clean_text(data.get("customerId"), "customerId", required=True, max_length=100)
        customer = Customer.query.filter_by(id=customer_id, org_id=org_id).first()
        if not customer:
            return jsonify({"error": "Customer not found in this organization"}), 404
        currency = clean_text(data.get("currency", org.currency), "currency", required=True, max_length=10).upper()
        if currency not in ALLOWED_CURRENCIES:
            raise ValueError("Unsupported currency")
        occurrences = max(0, int(data.get("occurrences", 0) or 0))
        max_occurrences = int(data["maxOccurrences"]) if data.get("maxOccurrences") not in (None, "") else None
        if max_occurrences is not None and max_occurrences < 1:
            raise ValueError("maxOccurrences must be at least 1")
        status = clean_text(data.get("status", "active"), "status", required=True, max_length=20)
        if status not in {"active", "paused", "completed"}:
            raise ValueError("Invalid recurring status")
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    computed_subtotal = sum((item["amount"] for item in items), start=Decimal("0")).quantize(Decimal("0.01"))
    try:
        subtotal = money(data["subtotal"]) if "subtotal" in data else computed_subtotal
        discount_amount = money(data.get("discountAmount", 0))
        tax_amount = money(data.get("taxAmount", 0))
        total_amount = money(data.get("totalAmount", subtotal - discount_amount + tax_amount))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if min(subtotal, discount_amount, tax_amount, total_amount) < 0:
        return jsonify({"error": "Recurring invoice financial amounts cannot be negative"}), 400
    if subtotal != computed_subtotal:
        return jsonify({"error": "Recurring invoice subtotal must equal the normalized line-item total"}), 400
    if total_amount != money(subtotal - discount_amount + tax_amount):
        return jsonify({"error": "Recurring invoice totals must equal subtotal - discount + tax"}), 400

    rec = RecurringInvoice(
        id=f"rec_{uuid.uuid4().hex}",
        org_id=org_id,
        template_invoice_number=clean_text(data.get("templateInvoiceNumber", "Recurring Invoice"), "templateInvoiceNumber", required=True, max_length=50),
        customer_id=customer.id,
        customer_name=customer.name,
        frequency=frequency,
        next_run_date=next_run,
        occurrences=occurrences,
        max_occurrences=max_occurrences,
        status=status,
        currency=currency,
        subtotal=subtotal,
        tax_amount=tax_amount,
        discount_amount=discount_amount,
        total_amount=total_amount,
        items=[{
            **item,
            "quantity": float(item["quantity"]),
            "unitPrice": float(item["unitPrice"]),
            "discountPercent": float(item["discountPercent"]),
            "taxRatePercent": float(item["taxRatePercent"]),
            "amount": float(item["amount"]),
        } for item in items],
        notes=clean_text(data.get("notes"), "notes", max_length=10000),
        terms=clean_text(data.get("terms"), "terms", max_length=10000),
    )
    if rec.max_occurrences is not None and rec.occurrences >= rec.max_occurrences:
        rec.status = "completed"
    db.session.add(rec)
    record_activity(org_id, "Created recurring invoice", "invoice", rec.id, rec.template_invoice_number)
    db.session.commit()
    return jsonify(rec.to_dict()), 201


@recurring_bp.route("/recurring/<id>", methods=["PUT"])
@require_auth
def update_recurring(id):
    rec, _org, error = _authorized(id, roles={"owner", "admin", "accountant"})
    if error:
        return error
    data = request.get_json() or {}
    try:
        normalized_items = _normalize_items(data["items"]) if "items" in data else _normalize_items(rec.items or [])
        if "status" in data:
            status = clean_text(data["status"], "status", required=True, max_length=20)
            if status not in {"active", "paused", "completed"}:
                raise ValueError("Invalid recurring status")
            rec.status = status
        if "templateInvoiceNumber" in data:
            rec.template_invoice_number = clean_text(data["templateInvoiceNumber"], "templateInvoiceNumber", required=True, max_length=50)
        if "notes" in data:
            rec.notes = clean_text(data["notes"], "notes", max_length=10000)
        if "terms" in data:
            rec.terms = clean_text(data["terms"], "terms", max_length=10000)
        if "frequency" in data:
            frequency = clean_text(data["frequency"], "frequency", required=True, max_length=20)
            if frequency not in RECURRING_FREQUENCIES:
                raise ValueError("Invalid recurring frequency")
            rec.frequency = frequency
        if "nextRunDate" in data:
            rec.next_run_date = parse_date(data["nextRunDate"], "nextRunDate")
        if "occurrences" in data:
            rec.occurrences = max(0, int(data["occurrences"]))
        if "maxOccurrences" in data:
            rec.max_occurrences = int(data["maxOccurrences"]) if data["maxOccurrences"] not in (None, "") else None
            if rec.max_occurrences is not None and rec.max_occurrences < 1:
                raise ValueError("maxOccurrences must be at least 1")
        if "currency" in data:
            currency = clean_text(data["currency"], "currency", required=True, max_length=10).upper()
            if currency not in ALLOWED_CURRENCIES:
                raise ValueError("Unsupported currency")
            rec.currency = currency
        computed_subtotal = sum((item["amount"] for item in normalized_items), start=Decimal("0")).quantize(Decimal("0.01"))
        if "subtotal" in data and money(data["subtotal"]) != computed_subtotal:
            raise ValueError("Recurring invoice subtotal must equal the normalized line-item total")
        rec.subtotal = computed_subtotal
        if "taxAmount" in data:
            rec.tax_amount = money(data["taxAmount"])
        if "discountAmount" in data:
            rec.discount_amount = money(data["discountAmount"])
        if "totalAmount" in data:
            rec.total_amount = money(data["totalAmount"])
        elif "items" in data:
            rec.total_amount = money(rec.subtotal - rec.discount_amount + rec.tax_amount)
        if "items" in data:
            rec.items = [{
                **item,
                "quantity": float(item["quantity"]),
                "unitPrice": float(item["unitPrice"]),
                "discountPercent": float(item["discountPercent"]),
                "taxRatePercent": float(item["taxRatePercent"]),
                "amount": float(item["amount"]),
            } for item in normalized_items]
        for amount in (rec.subtotal, rec.tax_amount, rec.discount_amount, rec.total_amount):
            if money(amount) < 0:
                raise ValueError("Recurring invoice financial amounts cannot be negative")
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    if rec.max_occurrences is not None and rec.occurrences >= rec.max_occurrences:
        rec.status = "completed"
    if rec.total_amount != money(rec.subtotal - rec.discount_amount + rec.tax_amount):
        return jsonify({"error": "Recurring invoice totals must equal subtotal - discount + tax"}), 400
    record_activity(rec.org_id, "Updated recurring invoice", "invoice", rec.id, rec.template_invoice_number)
    db.session.commit()
    return jsonify(rec.to_dict()), 200


@recurring_bp.route("/recurring/<id>", methods=["DELETE"])
@require_auth
def delete_recurring(id):
    rec, _org, error = _authorized(id, roles={"owner", "admin"})
    if error:
        return error
    record_activity(rec.org_id, "Deleted recurring invoice", "invoice", rec.id, rec.template_invoice_number)
    db.session.delete(rec)
    db.session.commit()
    return jsonify({"message": "Recurring invoice deleted successfully"}), 200


@recurring_bp.route("/recurring/run", methods=["POST"])
@require_auth
def run_recurring():
    data = request.get_json() or {}
    try:
        org_id = clean_text(data.get("orgId"), "orgId", required=True, max_length=100)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    result, error = require_org_membership(org_id, roles={"owner", "admin", "accountant"})
    if error:
        return error
    try:
        generated = run_for_org(org_id, current_user()["uid"])
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 409
    return jsonify({"count": len(generated), "invoices": [inv.to_dict() for inv in generated]}), 201

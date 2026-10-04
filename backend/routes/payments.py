import uuid
from datetime import date
from decimal import Decimal

from flask import Blueprint, jsonify, request
from sqlalchemy import and_

from backend.auth import current_user, require_auth, require_org_membership
from backend.database import db
from backend.models import Invoice, Payment
from backend.services.audit import record_activity
from backend.utils import PAYMENT_METHODS, clean_text, money, money_float, parse_date

payment_bp = Blueprint("payments", __name__)


def _authorized_invoice(invoice_id, roles=None, for_update=False):
    query = Invoice.query.filter_by(id=invoice_id)
    if for_update:
        query = query.with_for_update()
    invoice = query.first()
    if not invoice:
        return None, None, (jsonify({"error": "Invoice not found"}), 404)
    result, error = require_org_membership(invoice.org_id, roles=roles, for_update=False)
    if error:
        return None, None, error
    return invoice, result[0], None


def _validate_payment_input(entry):
    invoice_id = clean_text(entry.get("invoiceId"), "invoiceId", required=True, max_length=100)
    amount = money(entry.get("amount", 0), positive=True)
    payment_date = parse_date(entry.get("paymentDate", date.today().isoformat()), "paymentDate")
    method = clean_text(entry.get("paymentMethod", "bank_transfer"), "paymentMethod", required=True, max_length=50)
    if method not in PAYMENT_METHODS:
        raise ValueError("Invalid payment method")
    reference = clean_text(entry.get("reference"), "reference", max_length=100)
    notes = clean_text(entry.get("notes"), "notes", max_length=10000)
    return invoice_id, amount, payment_date, method, reference, notes


@payment_bp.route("/payments", methods=["GET"])
@require_auth
def get_payments():
    org_id = request.args.get("org_id")
    if not org_id:
        return jsonify({"error": "org_id is required"}), 400
    result, error = require_org_membership(org_id)
    if error:
        return error
    invoice_id = request.args.get("invoice_id")
    query = Payment.query.filter_by(org_id=org_id)
    if invoice_id:
        query = query.filter_by(invoice_id=invoice_id)
    payments = query.order_by(Payment.created_at.desc()).all()
    return jsonify([p.to_dict() for p in payments]), 200


@payment_bp.route("/payments", methods=["POST"])
@require_auth
def record_payment():
    data = request.get_json() or {}
    try:
        invoice_id, amount, payment_date, method, reference, notes = _validate_payment_input(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    invoice, _org, error = _authorized_invoice(invoice_id, roles={"owner", "admin", "accountant"}, for_update=True)
    if error:
        return error
    if invoice.status == "cancelled":
        return jsonify({"error": "Cannot record payment on a cancelled invoice"}), 409
    remaining = money(invoice.total_amount - invoice.paid_amount)
    if amount > remaining:
        return jsonify({"error": f"Payment exceeds the remaining invoice balance of {money_float(remaining):.2f}"}), 409

    payment = Payment(
        id=f"pay_{uuid.uuid4().hex}",
        org_id=invoice.org_id,
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        customer_id=invoice.customer_id,
        customer_name=invoice.customer_name,
        amount=amount,
        payment_date=payment_date,
        payment_method=method,
        reference=reference,
        notes=notes,
        created_by=current_user()["uid"],
    )
    invoice.paid_amount = money(invoice.paid_amount + amount)
    invoice.balance_due = money(invoice.total_amount - invoice.paid_amount)
    invoice.status = "paid" if invoice.balance_due == 0 else "partially_paid"
    db.session.add(payment)
    record_activity(invoice.org_id, "Recorded payment", "payment", payment.id, f"{invoice.invoice_number}: {amount}")
    db.session.commit()
    return jsonify(payment.to_dict()), 201


@payment_bp.route("/payments/batch", methods=["POST"])
@require_auth
def record_batch_payments():
    data = request.get_json() or {}
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        return jsonify({"error": "No payment entries provided"}), 400
    if len(entries) > 100:
        return jsonify({"error": "A batch may contain at most 100 entries"}), 400

    try:
        normalized = [_validate_payment_input(entry) for entry in entries]
        invoice_ids = [row[0] for row in normalized]
        if len(invoice_ids) != len(set(invoice_ids)):
            return jsonify({"error": "Each invoice can appear only once in a payment batch"}), 409

        invoices = (
            Invoice.query.filter(Invoice.id.in_(invoice_ids))
            .with_for_update()
            .all()
        )
        invoices_by_id = {inv.id: inv for inv in invoices}
        missing = [invoice_id for invoice_id in invoice_ids if invoice_id not in invoices_by_id]
        if missing:
            return jsonify({"error": "One or more invoices were not found"}), 404

        auth_org_ids = {invoices_by_id[row[0]].org_id for row in normalized}
        if len(auth_org_ids) != 1:
            return jsonify({"error": "A payment batch can contain invoices from only one organization"}), 409
        org_id = next(iter(auth_org_ids))
        result, error = require_org_membership(org_id, roles={"owner", "admin", "accountant"})
        if error:
            return error

        created = []
        for invoice_id, amount, payment_date, method, reference, notes in normalized:
            invoice = invoices_by_id[invoice_id]
            if invoice.status == "cancelled":
                raise ValueError(f"Invoice {invoice.invoice_number} is cancelled")
            remaining = money(invoice.total_amount - invoice.paid_amount)
            if amount > remaining:
                raise ValueError(f"Payment for {invoice.invoice_number} exceeds its remaining balance")
            payment = Payment(
                id=f"pay_{uuid.uuid4().hex}",
                org_id=invoice.org_id,
                invoice_id=invoice.id,
                invoice_number=invoice.invoice_number,
                customer_id=invoice.customer_id,
                customer_name=invoice.customer_name,
                amount=amount,
                payment_date=payment_date,
                payment_method=method,
                reference=reference,
                notes=notes,
                created_by=current_user()["uid"],
            )
            invoice.paid_amount = money(invoice.paid_amount + amount)
            invoice.balance_due = money(invoice.total_amount - invoice.paid_amount)
            invoice.status = "paid" if invoice.balance_due == 0 else "partially_paid"
            db.session.add(payment)
            record_activity(org_id, "Recorded batch payment", "payment", payment.id, f"{invoice.invoice_number}: {amount}")
            created.append(payment)

        db.session.commit()
        return jsonify({
            "message": f"Successfully processed {len(created)} batch payments",
            "count": len(created),
            "payments": [p.to_dict() for p in created],
        }), 201
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 409
    except Exception:
        db.session.rollback()
        raise

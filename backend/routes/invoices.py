import base64
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from email.utils import parseaddr

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import IntegrityError

from backend.auth import current_user, require_auth, require_org_membership
from backend.database import db
from backend.models import Customer, Invoice, InvoiceItem, Organization
from backend.services.audit import record_activity
from backend.services.email import EmailNotConfiguredError, send_email
from backend.services.html import invoice_email_html
from backend.utils import (
    ALLOWED_CURRENCIES,
    INVOICE_STATUSES,
    clean_text,
    money,
    money_float,
    percent,
    parse_date,
)

invoice_bp = Blueprint("invoices", __name__)


def _normalize_items(items):
    if not isinstance(items, list) or not items:
        raise ValueError("At least one invoice item is required")
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each invoice item must be an object")
        description = clean_text(item.get("description"), "item.description", required=True, max_length=500)
        try:
            qty = Decimal(str(item.get("quantity", 1)))
        except Exception:
            raise ValueError("Item quantity must be a valid number")
        if not qty.is_finite() or qty <= 0:
            raise ValueError("Item quantity must be greater than zero")
        unit_price = money(item.get("unitPrice", 0))
        item_discount = percent(item.get("discountPercent", 0))
        item_tax = percent(item.get("taxRatePercent", 0))
        gross = (qty * unit_price).quantize(Decimal("0.01"))
        amount = (gross * (Decimal("1") - item_discount / Decimal("100"))).quantize(Decimal("0.01"))
        normalized.append({
            "description": description,
            "quantity": qty,
            "unitPrice": unit_price,
            "discountPercent": item_discount,
            "taxRatePercent": item_tax,
            "amount": amount,
        })
    return normalized


def _calculate_totals(items, tax_rate, discount_rate):
    subtotal = sum((item["amount"] for item in items), start=Decimal("0"))
    subtotal = subtotal.quantize(Decimal("0.01"))
    discount_amount = (subtotal * discount_rate / Decimal("100")).quantize(Decimal("0.01"))
    taxable = subtotal - discount_amount
    tax_amount = (taxable * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
    total_amount = (taxable + tax_amount).quantize(Decimal("0.01"))
    return subtotal, discount_amount, tax_amount, total_amount


def _sync_status(invoice):
    if invoice.status == "cancelled":
        return
    today = date.today().isoformat()
    if invoice.paid_amount >= invoice.total_amount and invoice.total_amount > 0:
        invoice.status = "paid"
    elif invoice.paid_amount > 0:
        invoice.status = "partially_paid"
    elif invoice.due_date < today and invoice.status != "draft":
        invoice.status = "overdue"


def _allocate_invoice_number(org: Organization) -> str:
    year = date.today().year
    if org.invoice_sequence_year != year:
        org.invoice_sequence_year = year
        org.invoice_sequence = 0

    max_suffix = 0
    pattern = re.compile(rf"^INV-{year}-(\d+)$")
    for number, in db.session.query(Invoice.invoice_number).filter_by(org_id=org.id).all():
        match = pattern.match(number or "")
        if match:
            max_suffix = max(max_suffix, int(match.group(1)))
    org.invoice_sequence = max(org.invoice_sequence, max_suffix) + 1
    return f"INV-{year}-{org.invoice_sequence:03d}"


def _load_authorized_invoice(invoice_id, roles=None):
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        return None, None, (jsonify({"error": "Invoice not found"}), 404)
    result, error = require_org_membership(invoice.org_id, roles=roles)
    if error:
        return None, None, error
    return invoice, result[0], None


@invoice_bp.route("/invoices", methods=["GET"])
@require_auth
def get_invoices():
    org_id = request.args.get("org_id")
    if not org_id:
        return jsonify({"error": "org_id is required"}), 400
    result, error = require_org_membership(org_id)
    if error:
        return error
    status = request.args.get("status")
    customer_id = request.args.get("customer_id")
    query = Invoice.query.filter_by(org_id=org_id)
    if status and status != "all":
        query = query.filter_by(status=status)
    if customer_id:
        query = query.filter_by(customer_id=customer_id)
    invoices = query.order_by(Invoice.created_at.desc()).all()
    return jsonify([inv.to_dict() for inv in invoices]), 200


@invoice_bp.route("/invoices/<id>", methods=["GET"])
@require_auth
def get_invoice(id):
    invoice, _org, error = _load_authorized_invoice(id)
    if error:
        return error
    return jsonify(invoice.to_dict()), 200


@invoice_bp.route("/invoices", methods=["POST"])
@require_auth
def create_invoice():
    data = request.get_json() or {}
    org_id = clean_text(data.get("orgId"), "orgId", required=True, max_length=100)
    result, error = require_org_membership(org_id, roles={"owner", "admin", "accountant"})
    if error:
        return error
    org, _member = result

    customer_id = clean_text(data.get("customerId"), "customerId", required=True, max_length=100)
    customer = Customer.query.filter_by(id=customer_id, org_id=org_id).first()
    if not customer:
        return jsonify({"error": "Customer not found in this organization"}), 404

    try:
        issue_date = parse_date(data.get("issueDate"), "issueDate")
        due_date = parse_date(data.get("dueDate"), "dueDate")
        currency = clean_text(data.get("currency", org.currency), "currency", required=True, max_length=10).upper()
        if currency not in ALLOWED_CURRENCIES:
            raise ValueError("Unsupported currency")
        tax_rate = percent(data.get("taxPercent", data.get("taxRate", 0)))
        discount_rate = percent(data.get("discountPercent", data.get("discountRate", 0)))
        items = _normalize_items(data.get("items"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if due_date < issue_date:
        return jsonify({"error": "dueDate cannot be before issueDate"}), 400

    requested_number = data.get("invoiceNumber")
    if requested_number:
        invoice_number = clean_text(requested_number, "invoiceNumber", required=True, max_length=50)
        if Invoice.query.filter_by(org_id=org_id, invoice_number=invoice_number).first():
            return jsonify({"error": "Invoice number already exists in this organization"}), 409
        match = re.match(r"^INV-(\d{4})-(\d+)$", invoice_number)
        if match and int(match.group(1)) == date.today().year:
            org.invoice_sequence_year = date.today().year
            org.invoice_sequence = max(org.invoice_sequence, int(match.group(2)))
    else:
        org = Organization.query.filter_by(id=org_id).with_for_update().one()
        invoice_number = _allocate_invoice_number(org)

    subtotal, discount_amount, tax_amount, total_amount = _calculate_totals(items, tax_rate, discount_rate)
    status = clean_text(data.get("status", "draft"), "status", required=True, max_length=30)
    if status not in {"draft", "sent", "overdue"}:
        status = "draft"

    invoice = Invoice(
        id=f"inv_{uuid.uuid4().hex}",
        org_id=org_id,
        invoice_number=invoice_number,
        customer_id=customer.id,
        customer_name=customer.name,
        customer_email=customer.email,
        issue_date=issue_date,
        due_date=due_date,
        status=status,
        currency=currency,
        subtotal=subtotal,
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        discount_rate=discount_rate,
        discount_amount=discount_amount,
        total_amount=total_amount,
        paid_amount=Decimal("0.00"),
        balance_due=total_amount,
        notes=clean_text(data.get("notes"), "notes", max_length=10000),
        terms=clean_text(data.get("terms"), "terms", max_length=10000),
        recurring_id=clean_text(data.get("recurringId"), "recurringId", max_length=100) if data.get("recurringId") else None,
        created_by=current_user()["uid"],
    )
    db.session.add(invoice)
    for item in items:
        db.session.add(InvoiceItem(
            invoice_id=invoice.id,
            description=item["description"],
            quantity=item["quantity"],
            unit_price=item["unitPrice"],
            discount_percent=item["discountPercent"],
            tax_rate_percent=item["taxRatePercent"],
            amount=item["amount"],
        ))

    record_activity(org_id, "Created invoice", "invoice", invoice.id, invoice.invoice_number)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Invoice number already exists; please retry"}), 409
    return jsonify(invoice.to_dict()), 201


@invoice_bp.route("/invoices/<id>", methods=["PUT"])
@require_auth
def update_invoice(id):
    invoice, _org, error = _load_authorized_invoice(id, roles={"owner", "admin", "accountant"})
    if error:
        return error
    data = request.get_json() or {}

    if "customerId" in data:
        customer_id = clean_text(data["customerId"], "customerId", required=True, max_length=100)
        customer = Customer.query.filter_by(id=customer_id, org_id=invoice.org_id).first()
        if not customer:
            return jsonify({"error": "Customer not found in this organization"}), 404
        invoice.customer_id = customer.id
        invoice.customer_name = customer.name
        invoice.customer_email = customer.email

    for field, attr in (("issueDate", "issue_date"), ("dueDate", "due_date")):
        if field in data:
            try:
                setattr(invoice, attr, parse_date(data[field], field))
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
    if invoice.due_date < invoice.issue_date:
        return jsonify({"error": "dueDate cannot be before issueDate"}), 400

    if "invoiceNumber" in data and data["invoiceNumber"] != invoice.invoice_number:
        new_number = clean_text(data["invoiceNumber"], "invoiceNumber", required=True, max_length=50)
        conflict = Invoice.query.filter_by(org_id=invoice.org_id, invoice_number=new_number).filter(Invoice.id != invoice.id).first()
        if conflict:
            return jsonify({"error": "Invoice number already exists in this organization"}), 409
        invoice.invoice_number = new_number
    if "currency" in data:
        currency = clean_text(data["currency"], "currency", required=True, max_length=10).upper()
        if currency not in ALLOWED_CURRENCIES:
            return jsonify({"error": "Unsupported currency"}), 400
        invoice.currency = currency
    if "notes" in data:
        invoice.notes = clean_text(data["notes"], "notes", max_length=10000)
    if "terms" in data:
        invoice.terms = clean_text(data["terms"], "terms", max_length=10000)
    if "recurringId" in data:
        invoice.recurring_id = clean_text(data["recurringId"], "recurringId", max_length=100) or None

    financial_change = any(key in data for key in ("items", "taxPercent", "taxRate", "discountPercent", "discountRate"))
    if financial_change:
        try:
            items = _normalize_items(data.get("items", [item.to_dict() for item in invoice.items]))
            tax_rate = percent(data.get("taxPercent", data.get("taxRate", invoice.tax_rate)))
            discount_rate = percent(data.get("discountPercent", data.get("discountRate", invoice.discount_rate)))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        subtotal, discount_amount, tax_amount, total_amount = _calculate_totals(items, tax_rate, discount_rate)
        if total_amount < invoice.paid_amount:
            return jsonify({"error": "Invoice total cannot be less than payments already received"}), 409
        InvoiceItem.query.filter_by(invoice_id=invoice.id).delete()
        for item in items:
            db.session.add(InvoiceItem(
                invoice_id=invoice.id,
                description=item["description"],
                quantity=item["quantity"],
                unit_price=item["unitPrice"],
                discount_percent=item["discountPercent"],
                tax_rate_percent=item["taxRatePercent"],
                amount=item["amount"],
            ))
        invoice.subtotal = subtotal
        invoice.tax_rate = tax_rate
        invoice.tax_amount = tax_amount
        invoice.discount_rate = discount_rate
        invoice.discount_amount = discount_amount
        invoice.total_amount = total_amount
        invoice.balance_due = total_amount - invoice.paid_amount

    if "status" in data:
        status = clean_text(data["status"], "status", required=True, max_length=30)
        if status not in INVOICE_STATUSES:
            return jsonify({"error": "Invalid invoice status"}), 400
        invoice.status = status

    _sync_status(invoice)
    record_activity(invoice.org_id, "Updated invoice", "invoice", invoice.id, invoice.invoice_number)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Invoice number already exists"}), 409
    return jsonify(invoice.to_dict()), 200


@invoice_bp.route("/invoices/<id>", methods=["DELETE"])
@require_auth
def delete_invoice(id):
    invoice, _org, error = _load_authorized_invoice(id, roles={"owner", "admin"})
    if error:
        return error
    record_activity(invoice.org_id, "Deleted invoice", "invoice", invoice.id, invoice.invoice_number)
    db.session.delete(invoice)
    db.session.commit()
    return jsonify({"message": "Invoice deleted successfully"}), 200


@invoice_bp.route("/invoices/<id>/duplicate", methods=["POST"])
@require_auth
def duplicate_invoice(id):
    original, _org, error = _load_authorized_invoice(id, roles={"owner", "admin", "accountant"})
    if error:
        return error
    org = Organization.query.filter_by(id=original.org_id).with_for_update().one()
    invoice_number = _allocate_invoice_number(org)
    new_invoice = Invoice(
        id=f"inv_{uuid.uuid4().hex}",
        org_id=original.org_id,
        invoice_number=invoice_number,
        customer_id=original.customer_id,
        customer_name=original.customer_name,
        customer_email=original.customer_email,
        issue_date=date.today().isoformat(),
        due_date=max(original.due_date, date.today().isoformat()),
        status="draft",
        currency=original.currency,
        subtotal=original.subtotal,
        tax_rate=original.tax_rate,
        tax_amount=original.tax_amount,
        discount_rate=original.discount_rate,
        discount_amount=original.discount_amount,
        total_amount=original.total_amount,
        paid_amount=Decimal("0.00"),
        balance_due=original.total_amount,
        notes=original.notes,
        terms=original.terms,
        created_by=current_user()["uid"],
    )
    db.session.add(new_invoice)
    for item in original.items:
        db.session.add(InvoiceItem(
            invoice_id=new_invoice.id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            tax_rate_percent=item.tax_rate_percent,
            amount=item.amount,
        ))
    record_activity(original.org_id, "Duplicated invoice", "invoice", new_invoice.id, f"Copied {original.invoice_number}")
    db.session.commit()
    return jsonify(new_invoice.to_dict()), 201


@invoice_bp.route("/invoices/<id>/email", methods=["POST"])
@require_auth
def email_invoice(id):
    invoice, _org, error = _load_authorized_invoice(id, roles={"owner", "admin", "accountant"})
    if error:
        return error
    data = request.get_json() or {}
    recipient = clean_text(data.get("recipientEmail"), "recipientEmail", required=True, max_length=255).lower()
    if parseaddr(recipient)[1] != recipient:
        return jsonify({"error": "recipientEmail must be a valid email address"}), 400
    subject = clean_text(data.get("subject", f"Invoice {invoice.invoice_number}"), "subject", required=True, max_length=255)
    text_body = clean_text(data.get("bodyText", "Please find your invoice attached."), "bodyText", required=True, max_length=20000)
    custom_note = clean_text(data.get("customNote", ""), "customNote", max_length=5000)
    html_body = invoice_email_html(
        _org.name,
        invoice.invoice_number,
        invoice.issue_date,
        invoice.due_date,
        f"{invoice.total_amount:.2f}",
        f"{invoice.balance_due:.2f}",
        invoice.terms or _org.invoice_terms or "Payment due within 30 days.",
        custom_note,
    )
    filename = clean_text(data.get("attachedFilename", f"{invoice.invoice_number}.pdf"), "attachedFilename", required=True, max_length=255)
    encoded = data.get("pdfBase64")
    if not encoded or not isinstance(encoded, str):
        return jsonify({"error": "pdfBase64 attachment is required"}), 400
    if encoded.startswith("data:"):
        try:
            encoded = encoded.split(",", 1)[1]
        except IndexError:
            return jsonify({"error": "Invalid PDF attachment"}), 400
    try:
        pdf_bytes = base64.b64decode(encoded, validate=True)
    except Exception:
        return jsonify({"error": "Invalid PDF attachment encoding"}), 400
    if len(pdf_bytes) > 10 * 1024 * 1024:
        return jsonify({"error": "PDF attachment must be 10 MB or smaller"}), 413

    try:
        message_id = send_email(
            to_email=recipient,
            subject=subject,
            text_body=text_body,
            html_body=html_body or None,
            attachment_name=filename,
            attachment_bytes=pdf_bytes,
        )
    except EmailNotConfiguredError:
        return jsonify({"error": "Email delivery is not configured", "message": "Configure SMTP_HOST and SMTP_FROM_EMAIL on the backend before sending email."}), 503
    except Exception:
        current_app.logger.exception("Invoice email delivery failed")
        return jsonify({"error": "Email delivery failed", "message": "The message could not be sent. Please try again."}), 502

    record_activity(invoice.org_id, "Emailed invoice", "invoice", invoice.id, f"Delivered to {recipient}")
    db.session.commit()
    return jsonify({
        "success": True,
        "messageId": message_id,
        "recipientEmail": recipient,
        "sentAt": datetime.now(timezone.utc).isoformat(),
        "attachedFilename": filename,
    }), 200

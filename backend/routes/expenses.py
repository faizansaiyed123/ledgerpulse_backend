import uuid
from datetime import date

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from backend.auth import current_user, require_auth, require_org_membership
from backend.database import db
from backend.models import Expense, Organization, Vendor
from backend.services.audit import record_activity
from backend.utils import ALLOWED_CURRENCIES, EXPENSE_CATEGORIES, EXPENSE_STATUSES, PAYMENT_METHODS, clean_text, money, parse_date

expense_bp = Blueprint("expenses", __name__)


def _authorized_expense(expense_id, roles=None):
    expense = Expense.query.get(expense_id)
    if not expense:
        return None, None, (jsonify({"error": "Expense not found"}), 404)
    result, error = require_org_membership(expense.org_id, roles=roles)
    if error:
        return None, None, error
    return expense, result[0], None


def _status_for_member(member_role, requested):
    if member_role in {"owner", "admin", "accountant"}:
        return requested if requested in EXPENSE_STATUSES else "approved"
    if requested == "rejected":
        return "rejected"
    return "pending"


def _bool_field(value, field_name):
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field_name} must be a boolean")


@expense_bp.route("/expenses", methods=["GET"])
@require_auth
def get_expenses():
    org_id = request.args.get("org_id")
    if not org_id:
        return jsonify({"error": "org_id is required"}), 400
    result, error = require_org_membership(org_id)
    if error:
        return error
    category = request.args.get("category")
    query = Expense.query.filter_by(org_id=org_id)
    if category and category != "all":
        query = query.filter_by(category=category)
    expenses = query.order_by(Expense.date.desc(), Expense.created_at.desc()).all()
    return jsonify([expense.to_dict() for expense in expenses]), 200


@expense_bp.route("/expenses/<id>", methods=["GET"])
@require_auth
def get_expense(id):
    expense, _org, error = _authorized_expense(id)
    if error:
        return error
    return jsonify(expense.to_dict()), 200


@expense_bp.route("/expenses", methods=["POST"])
@require_auth
def create_expense():
    data = request.get_json() or {}
    org_id = clean_text(data.get("orgId"), "orgId", required=True, max_length=100)
    result, error = require_org_membership(org_id, roles={"owner", "admin", "accountant", "staff"})
    if error:
        return error
    org, member = result
    try:
        category = clean_text(data.get("category"), "category", required=True, max_length=100)
        if category not in EXPENSE_CATEGORIES:
            raise ValueError("Invalid expense category")
        amount = money(data.get("amount"), positive=True)
        tax_amount = money(data.get("taxAmount", 0))
        vendor_name = clean_text(data.get("vendorName", data.get("vendor")), "vendorName", max_length=255)
        vendor_id = clean_text(data.get("vendorId"), "vendorId", max_length=100) or None
        expense_date = parse_date(data.get("expenseDate", data.get("date", date.today().isoformat())), "expenseDate")
        method = clean_text(data.get("paymentMethod", "credit_card"), "paymentMethod", required=True, max_length=50)
        if method not in PAYMENT_METHODS:
            raise ValueError("Invalid payment method")
        currency = clean_text(data.get("currency", org.currency), "currency", required=True, max_length=10).upper()
        if currency not in ALLOWED_CURRENCIES:
            raise ValueError("Unsupported currency")
        reimbursable = _bool_field(data.get("isReimbursable", False), "isReimbursable")
        tax_deductible = _bool_field(data.get("taxDeductible", True), "taxDeductible") if "taxDeductible" in data else True
        recurring = _bool_field(data.get("isRecurring", False), "isRecurring") if "isRecurring" in data else False
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if vendor_id:
        vendor = Vendor.query.filter_by(id=vendor_id, org_id=org_id).first()
        if not vendor:
            return jsonify({"error": "Vendor not found in this organization"}), 404
        vendor_name = vendor.name

    status = _status_for_member(member.role, clean_text(data.get("status", "pending"), "status", max_length=30))
    expense = Expense(
        id=f"exp_{uuid.uuid4().hex}",
        org_id=org_id,
        vendor_id=vendor_id,
        vendor_name=vendor_name,
        category=category,
        amount=amount,
        tax_amount=tax_amount,
        currency=currency,
        description=clean_text(data.get("description"), "description", max_length=10000),
        date=expense_date,
        payment_method=method,
        reimbursable=reimbursable,
        receipt_url=clean_text(data.get("receiptUrl"), "receiptUrl", max_length=2000000),
        receipt_name=clean_text(data.get("receiptName"), "receiptName", max_length=255),
        notes=clean_text(data.get("notes"), "notes", max_length=10000),
        recurring=recurring,
        recurring_interval=clean_text(data.get("recurringInterval"), "recurringInterval", max_length=20) or None,
        tax_deductible=tax_deductible,
        status=status,
        created_by=current_user()["uid"],
    )
    db.session.add(expense)
    record_activity(org_id, "Created expense", "expense", expense.id, expense.description or expense.vendor_name or "Expense")
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Expense ID collision; please retry"}), 409
    return jsonify(expense.to_dict()), 201


@expense_bp.route("/expenses/<id>", methods=["PUT"])
@require_auth
def update_expense(id):
    expense, _org, error = _authorized_expense(id, roles={"owner", "admin", "accountant"})
    if error:
        return error
    data = request.get_json() or {}
    try:
        if "category" in data:
            category = clean_text(data["category"], "category", required=True, max_length=100)
            if category not in EXPENSE_CATEGORIES:
                raise ValueError("Invalid expense category")
            expense.category = category
        if "amount" in data:
            expense.amount = money(data["amount"], positive=True)
        if "taxAmount" in data:
            expense.tax_amount = money(data["taxAmount"])
        if "currency" in data:
            currency = clean_text(data["currency"], "currency", required=True, max_length=10).upper()
            if currency not in ALLOWED_CURRENCIES:
                raise ValueError("Unsupported currency")
            expense.currency = currency
        if "vendorId" in data:
            vendor_id = clean_text(data["vendorId"], "vendorId", max_length=100) or None
            if vendor_id:
                vendor = Vendor.query.filter_by(id=vendor_id, org_id=expense.org_id).first()
                if not vendor:
                    return jsonify({"error": "Vendor not found in this organization"}), 404
                expense.vendor_id = vendor.id
                expense.vendor_name = vendor.name
            else:
                expense.vendor_id = None
        if "vendorName" in data:
            expense.vendor_name = clean_text(data["vendorName"], "vendorName", max_length=255)
        if "description" in data:
            expense.description = clean_text(data["description"], "description", max_length=10000)
        if "expenseDate" in data or "date" in data:
            expense.date = parse_date(data.get("expenseDate", data.get("date")), "expenseDate")
        if "paymentMethod" in data:
            method = clean_text(data["paymentMethod"], "paymentMethod", required=True, max_length=50)
            if method not in PAYMENT_METHODS:
                raise ValueError("Invalid payment method")
            expense.payment_method = method
        if "isReimbursable" in data:
            expense.reimbursable = _bool_field(data["isReimbursable"], "isReimbursable")
        if "receiptUrl" in data:
            expense.receipt_url = clean_text(data["receiptUrl"], "receiptUrl", max_length=2000000)
        if "receiptName" in data:
            expense.receipt_name = clean_text(data["receiptName"], "receiptName", max_length=255)
        if "notes" in data:
            expense.notes = clean_text(data["notes"], "notes", max_length=10000)
        if "isRecurring" in data:
            expense.recurring = _bool_field(data["isRecurring"], "isRecurring")
        if "recurringInterval" in data:
            expense.recurring_interval = clean_text(data["recurringInterval"], "recurringInterval", max_length=20) or None
        if "taxDeductible" in data:
            expense.tax_deductible = _bool_field(data["taxDeductible"], "taxDeductible")
        if "status" in data:
            status = clean_text(data["status"], "status", required=True, max_length=30)
            if status not in EXPENSE_STATUSES:
                raise ValueError("Invalid expense status")
            expense.status = status
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    record_activity(expense.org_id, "Updated expense", "expense", expense.id, expense.description or "Expense")
    db.session.commit()
    return jsonify(expense.to_dict()), 200


@expense_bp.route("/expenses/<id>", methods=["DELETE"])
@require_auth
def delete_expense(id):
    expense, _org, error = _authorized_expense(id, roles={"owner", "admin"})
    if error:
        return error
    record_activity(expense.org_id, "Deleted expense", "expense", expense.id, expense.description or "Expense")
    db.session.delete(expense)
    db.session.commit()
    return jsonify({"message": "Expense deleted successfully"}), 200


@expense_bp.route("/expenses/<id>/status", methods=["POST"])
@require_auth
def set_expense_status(id):
    expense, _org, error = _authorized_expense(id, roles={"owner", "admin", "accountant"})
    if error:
        return error
    data = request.get_json() or {}
    status = clean_text(data.get("status"), "status", required=True, max_length=30)
    if status not in EXPENSE_STATUSES:
        return jsonify({"error": "Invalid expense status"}), 400
    expense.status = status
    record_activity(expense.org_id, f"Changed expense status to {status}", "expense", expense.id, expense.description or "Expense")
    db.session.commit()
    return jsonify(expense.to_dict()), 200

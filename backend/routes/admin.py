from flask import Blueprint, jsonify
from backend.auth import platform_admin_required
from backend.database import db
from backend.models import Customer, Expense, Invoice, Organization, OrganizationMember, Payment

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin/overview", methods=["GET"])
@platform_admin_required
def get_admin_overview():
    organizations = Organization.query.order_by(Organization.created_at.desc()).all()
    org_rows = []
    for org in organizations:
        member_count = OrganizationMember.query.filter_by(org_id=org.id, status="active").count()
        invoice_count = Invoice.query.filter_by(org_id=org.id).count()
        customer_count = Customer.query.filter_by(org_id=org.id).count()
        payment_count = Payment.query.filter_by(org_id=org.id).count()
        expense_count = Expense.query.filter_by(org_id=org.id).count()
        org_rows.append({
            **org.to_dict(),
            "activeMemberCount": member_count,
            "invoiceCount": invoice_count,
            "customerCount": customer_count,
            "paymentCount": payment_count,
            "expenseCount": expense_count,
        })

    return jsonify({
        "organizations": org_rows,
        "counts": {
            "organizations": len(organizations),
            "activeMembers": OrganizationMember.query.filter_by(status="active").count(),
            "customers": Customer.query.count(),
            "invoices": Invoice.query.count(),
            "payments": Payment.query.count(),
            "expenses": Expense.query.count(),
        },
    }), 200

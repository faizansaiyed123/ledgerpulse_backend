from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from backend.auth import platform_admin_required
from backend.database import db
from backend.models import Customer, Expense, Invoice, Organization, Payment

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health_check():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "healthy", "database": "PostgreSQL", "connected": True}), 200
    except Exception:
        current_app.logger.exception("Health check database failure")
        return jsonify({"status": "unhealthy", "database": "PostgreSQL", "connected": False}), 503


@health_bp.route("/health/details", methods=["GET"])
@platform_admin_required
def health_details():
    try:
        version = db.session.execute(text("SELECT version();")).scalar()
        return jsonify({
            "status": "healthy",
            "database": "PostgreSQL",
            "postgres_version": version,
            "connected": True,
            "stats": {
                "organizations": Organization.query.count(),
                "invoices": Invoice.query.count(),
                "customers": Customer.query.count(),
                "payments": Payment.query.count(),
                "expenses": Expense.query.count(),
            },
        }), 200
    except Exception:
        current_app.logger.exception("Detailed health check failed")
        return jsonify({"status": "unhealthy", "connected": False}), 503

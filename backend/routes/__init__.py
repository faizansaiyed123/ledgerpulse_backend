from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api")

from backend.routes.auth import auth_bp
from backend.routes.health import health_bp
from backend.routes.public import public_bp
from backend.routes.organizations import org_bp
from backend.routes.customers import customer_bp
from backend.routes.invoices import invoice_bp
from backend.routes.payments import payment_bp
from backend.routes.expenses import expense_bp
from backend.routes.vendors import vendor_bp
from backend.routes.recurring import recurring_bp
from backend.routes.activities import activity_bp
from backend.routes.admin import admin_bp

api_bp.register_blueprint(auth_bp)
api_bp.register_blueprint(health_bp)
api_bp.register_blueprint(public_bp)
api_bp.register_blueprint(org_bp)
api_bp.register_blueprint(customer_bp)
api_bp.register_blueprint(invoice_bp)
api_bp.register_blueprint(payment_bp)
api_bp.register_blueprint(expense_bp)
api_bp.register_blueprint(vendor_bp)
api_bp.register_blueprint(recurring_bp)
api_bp.register_blueprint(activity_bp)
api_bp.register_blueprint(admin_bp)

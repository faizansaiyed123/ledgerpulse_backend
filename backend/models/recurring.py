from backend.database import db, TimestampMixin
from backend.utils import money_float


class RecurringInvoice(db.Model, TimestampMixin):
    __tablename__ = "recurring_invoices"

    id = db.Column(db.String(100), primary_key=True)
    org_id = db.Column(db.String(100), db.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    template_invoice_number = db.Column(db.String(50), nullable=False)
    customer_id = db.Column(db.String(100), db.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_name = db.Column(db.String(255), nullable=False)
    frequency = db.Column(db.String(20), nullable=False)
    next_run_date = db.Column(db.String(20), nullable=False)
    last_run_date = db.Column(db.String(20), nullable=True)
    occurrences = db.Column(db.Integer, default=0, nullable=False)
    max_occurrences = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), default="active", nullable=False)
    currency = db.Column(db.String(10), default="USD", nullable=False)
    subtotal = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    tax_amount = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    discount_amount = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    total_amount = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    items = db.Column(db.JSON, nullable=False, default=list)
    notes = db.Column(db.Text, nullable=True)
    terms = db.Column(db.Text, nullable=True)

    organization = db.relationship("Organization", back_populates="recurring_invoices")
    customer = db.relationship("Customer")

    def to_dict(self):
        return {
            "id": self.id,
            "orgId": self.org_id,
            "templateInvoiceNumber": self.template_invoice_number,
            "customerId": self.customer_id,
            "customerName": self.customer_name,
            "frequency": self.frequency,
            "nextRunDate": self.next_run_date,
            "lastRunDate": self.last_run_date,
            "occurrences": self.occurrences,
            "maxOccurrences": self.max_occurrences,
            "status": self.status,
            "currency": self.currency,
            "subtotal": money_float(self.subtotal),
            "taxAmount": money_float(self.tax_amount),
            "discountAmount": money_float(self.discount_amount),
            "totalAmount": money_float(self.total_amount),
            "items": self.items or [],
            "notes": self.notes or "",
            "terms": self.terms or "",
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }

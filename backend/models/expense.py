from backend.database import db, TimestampMixin
from backend.utils import money_float


class Expense(db.Model, TimestampMixin):
    __tablename__ = "expenses"

    id = db.Column(db.String(100), primary_key=True)
    org_id = db.Column(db.String(100), db.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id = db.Column(db.String(100), db.ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True, index=True)
    vendor_name = db.Column(db.String(255), nullable=True)
    category = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    currency = db.Column(db.String(10), default="USD", nullable=False)
    description = db.Column(db.Text, nullable=True)
    date = db.Column(db.String(20), nullable=False)
    payment_method = db.Column(db.String(50), default="credit_card", nullable=False)
    reimbursable = db.Column(db.Boolean, default=False, nullable=False)
    receipt_url = db.Column(db.Text, nullable=True)
    receipt_name = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    recurring = db.Column(db.Boolean, default=False, nullable=False)
    recurring_interval = db.Column(db.String(20), nullable=True)
    tax_deductible = db.Column(db.Boolean, default=True, nullable=False)
    status = db.Column(db.String(30), default="approved", nullable=False)
    created_by = db.Column(db.String(128), nullable=True)

    organization = db.relationship("Organization", back_populates="expenses")
    vendor = db.relationship("Vendor", back_populates="expenses")

    def to_dict(self):
        return {
            "id": self.id,
            "orgId": self.org_id,
            "vendorId": self.vendor_id,
            "vendorName": self.vendor_name or "",
            "category": self.category,
            "description": self.description or "",
            "expenseDate": self.date,
            "amount": money_float(self.amount),
            "taxAmount": money_float(self.tax_amount),
            "currency": self.currency,
            "paymentMethod": self.payment_method,
            "isReimbursable": self.reimbursable,
            "status": self.status,
            "receiptUrl": self.receipt_url or "",
            "receiptName": self.receipt_name or "",
            "notes": self.notes or "",
            "isRecurring": self.recurring,
            "recurringInterval": self.recurring_interval,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "createdBy": self.created_by,
        }

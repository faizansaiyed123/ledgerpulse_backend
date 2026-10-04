from backend.database import db, TimestampMixin
from backend.utils import money_float


class Payment(db.Model, TimestampMixin):
    __tablename__ = "payments"

    id = db.Column(db.String(100), primary_key=True)
    org_id = db.Column(db.String(100), db.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = db.Column(db.String(100), db.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_number = db.Column(db.String(50), nullable=False)
    customer_id = db.Column(db.String(100), db.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_name = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    payment_date = db.Column(db.String(20), nullable=False)
    payment_method = db.Column(db.String(50), default="bank_transfer", nullable=False)
    reference = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.String(128), nullable=True)

    organization = db.relationship("Organization", back_populates="payments")
    invoice = db.relationship("Invoice", back_populates="payments")
    customer = db.relationship("Customer", back_populates="payments")

    def to_dict(self):
        return {
            "id": self.id,
            "orgId": self.org_id,
            "invoiceId": self.invoice_id,
            "invoiceNumber": self.invoice_number,
            "customerId": self.customer_id,
            "customerName": self.customer_name,
            "amount": money_float(self.amount),
            "paymentDate": self.payment_date,
            "paymentMethod": self.payment_method,
            "reference": self.reference or "",
            "notes": self.notes or "",
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }

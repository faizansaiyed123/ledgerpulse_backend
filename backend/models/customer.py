from decimal import Decimal

from backend.database import db, TimestampMixin
from backend.utils import money_float


class Customer(db.Model, TimestampMixin):
    __tablename__ = "customers"

    id = db.Column(db.String(100), primary_key=True)
    org_id = db.Column(db.String(100), db.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    company_name = db.Column(db.String(255), nullable=True)
    address = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    tax_id = db.Column(db.String(100), nullable=True)
    currency = db.Column(db.String(10), default="USD", nullable=False)
    payment_terms = db.Column(db.Integer, default=30, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    organization = db.relationship("Organization", back_populates="customers")
    invoices = db.relationship("Invoice", back_populates="customer")
    payments = db.relationship("Payment", back_populates="customer")

    def to_dict(self):
        total_invoiced = sum((inv.total_amount for inv in self.invoices if inv.status != "cancelled"), start=Decimal("0"))
        total_paid = sum((inv.paid_amount for inv in self.invoices if inv.status != "cancelled"), start=Decimal("0"))
        outstanding = sum((inv.balance_due for inv in self.invoices if inv.status not in ("cancelled", "paid")), start=Decimal("0"))
        return {
            "id": self.id,
            "orgId": self.org_id,
            "name": self.name,
            "email": self.email or "",
            "phone": self.phone or "",
            "company": self.company_name or "",
            "taxId": self.tax_id or "",
            "currency": self.currency,
            "paymentTermsDays": self.payment_terms,
            "billingAddress": self.address or "",
            "city": self.city or "",
            "country": self.country or "",
            "notes": self.notes or "",
            "outstandingBalance": money_float(outstanding),
            "totalInvoiced": money_float(total_invoiced),
            "totalPaid": money_float(total_paid),
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }

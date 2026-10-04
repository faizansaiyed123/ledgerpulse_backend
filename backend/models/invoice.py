from backend.database import db, TimestampMixin
from backend.utils import money_float


class Invoice(db.Model, TimestampMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        db.UniqueConstraint("org_id", "invoice_number", name="uq_invoice_org_number"),
    )

    id = db.Column(db.String(100), primary_key=True)
    org_id = db.Column(db.String(100), db.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_number = db.Column(db.String(50), nullable=False, index=True)
    customer_id = db.Column(db.String(100), db.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_name = db.Column(db.String(255), nullable=False)
    customer_email = db.Column(db.String(255), nullable=True)
    issue_date = db.Column(db.String(20), nullable=False)
    due_date = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(30), default="draft", nullable=False, index=True)
    currency = db.Column(db.String(10), default="USD", nullable=False)
    subtotal = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    tax_rate = db.Column(db.Numeric(7, 2), default=0, nullable=False)
    tax_amount = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    discount_rate = db.Column(db.Numeric(7, 2), default=0, nullable=False)
    discount_amount = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    total_amount = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    paid_amount = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    balance_due = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    terms = db.Column(db.Text, nullable=True)
    recurring_id = db.Column(db.String(100), nullable=True)
    created_by = db.Column(db.String(128), nullable=True)

    organization = db.relationship("Organization", back_populates="invoices")
    customer = db.relationship("Customer", back_populates="invoices")
    items = db.relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan", lazy="selectin")
    payments = db.relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "orgId": self.org_id,
            "invoiceNumber": self.invoice_number,
            "customerId": self.customer_id,
            "customerName": self.customer_name,
            "customerEmail": self.customer_email or "",
            "issueDate": self.issue_date,
            "dueDate": self.due_date,
            "status": self.status,
            "currency": self.currency,
            "subtotal": money_float(self.subtotal),
            "discountPercent": money_float(self.discount_rate),
            "discountAmount": money_float(self.discount_amount),
            "taxPercent": money_float(self.tax_rate),
            "taxAmount": money_float(self.tax_amount),
            "totalAmount": money_float(self.total_amount),
            "paidAmount": money_float(self.paid_amount),
            "balanceDue": money_float(self.balance_due),
            "notes": self.notes or "",
            "terms": self.terms or "",
            "recurringId": self.recurring_id,
            "items": [item.to_dict() for item in self.items],
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class InvoiceItem(db.Model):
    __tablename__ = "invoice_items"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    invoice_id = db.Column(db.String(100), db.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    description = db.Column(db.String(500), nullable=False)
    quantity = db.Column(db.Numeric(12, 3), default=1, nullable=False)
    unit_price = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    discount_percent = db.Column(db.Numeric(7, 2), default=0, nullable=False)
    tax_rate_percent = db.Column(db.Numeric(7, 2), default=0, nullable=False)
    amount = db.Column(db.Numeric(14, 2), default=0, nullable=False)

    invoice = db.relationship("Invoice", back_populates="items")

    def to_dict(self):
        return {
            "id": str(self.id),
            "description": self.description,
            "quantity": float(self.quantity),
            "unitPrice": money_float(self.unit_price),
            "discountPercent": money_float(self.discount_percent),
            "taxRatePercent": money_float(self.tax_rate_percent),
            "amount": money_float(self.amount),
        }

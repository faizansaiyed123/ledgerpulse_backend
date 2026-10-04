from backend.database import db, TimestampMixin


class Organization(db.Model, TimestampMixin):
    __tablename__ = "organizations"

    id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), nullable=True)
    tax_id = db.Column(db.String(100), nullable=True)
    address = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    postal_code = db.Column(db.String(30), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    website = db.Column(db.String(255), nullable=True)
    currency = db.Column(db.String(10), default="USD", nullable=False)
    logo_url = db.Column(db.Text, nullable=True)
    fiscal_year_start = db.Column(db.String(20), default="January", nullable=True)
    default_payment_terms = db.Column(db.Integer, default=30, nullable=False)
    invoice_notes = db.Column(db.Text, nullable=True)
    invoice_terms = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.String(128), nullable=False, index=True)
    invoice_sequence = db.Column(db.Integer, default=0, nullable=False)
    invoice_sequence_year = db.Column(db.Integer, nullable=True)

    members = db.relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")
    customers = db.relationship("Customer", back_populates="organization", cascade="all, delete-orphan")
    invoices = db.relationship("Invoice", back_populates="organization", cascade="all, delete-orphan")
    payments = db.relationship("Payment", back_populates="organization", cascade="all, delete-orphan")
    expenses = db.relationship("Expense", back_populates="organization", cascade="all, delete-orphan")
    vendors = db.relationship("Vendor", back_populates="organization", cascade="all, delete-orphan")
    recurring_invoices = db.relationship("RecurringInvoice", back_populates="organization", cascade="all, delete-orphan")
    activities = db.relationship("ActivityLog", back_populates="organization", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "taxId": self.tax_id or "",
            "address": self.address or "",
            "city": self.city or "",
            "state": self.state or "",
            "postalCode": self.postal_code or "",
            "country": self.country or "",
            "phone": self.phone or "",
            "email": self.email or "",
            "website": self.website or "",
            "currency": self.currency,
            "logoUrl": self.logo_url or "",
            "fiscalYearStart": self.fiscal_year_start or "January",
            "paymentTermsDays": self.default_payment_terms,
            "invoiceNotes": self.invoice_notes or "",
            "invoiceTerms": self.invoice_terms or "",
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }

from decimal import Decimal

from backend.database import db, TimestampMixin
from backend.utils import money_float


class Vendor(db.Model, TimestampMixin):
    __tablename__ = "vendors"

    id = db.Column(db.String(100), primary_key=True)
    org_id = db.Column(db.String(100), db.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    company = db.Column(db.String(255), nullable=True)
    tax_id = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(100), nullable=False, default="other")
    address = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    organization = db.relationship("Organization", back_populates="vendors")
    expenses = db.relationship("Expense", back_populates="vendor")

    def to_dict(self):
        total = sum((expense.amount for expense in self.expenses if expense.status != "rejected"), start=Decimal("0"))
        return {
            "id": self.id,
            "orgId": self.org_id,
            "name": self.name,
            "email": self.email or "",
            "phone": self.phone or "",
            "company": self.company or "",
            "taxId": self.tax_id or "",
            "category": self.category,
            "address": self.address or "",
            "notes": self.notes or "",
            "totalExpenses": money_float(total),
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }

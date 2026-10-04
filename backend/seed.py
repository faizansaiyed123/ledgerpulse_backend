from datetime import date, timedelta, datetime, timezone
from decimal import Decimal

from backend.app import create_app
from backend.database import db
from backend.models import Customer, Expense, Invoice, InvoiceItem, Organization, OrganizationMember, Payment, Vendor
from backend.services.audit import record_activity
from backend.utils import money


def seed_sample_for_org(org_id: str, user_id: str):
    org = Organization.query.filter_by(id=org_id).with_for_update().first()
    if not org:
        raise ValueError("Organization not found")

    existing = {
        "customers": Customer.query.filter_by(org_id=org_id).count(),
        "invoices": Invoice.query.filter_by(org_id=org_id).count(),
        "expenses": Expense.query.filter_by(org_id=org_id).count(),
        "vendors": Vendor.query.filter_by(org_id=org_id).count(),
    }
    if any(existing.values()):
        raise ValueError("Sample data can only be loaded into an organization without business data")

    org.name = org.name or "LedgerPulse Workspace"
    org.currency = org.currency or "USD"
    org.default_payment_terms = org.default_payment_terms or 30
    today = date.today()

    members = OrganizationMember.query.filter_by(org_id=org_id).all()
    current_member = next((m for m in members if m.user_id == user_id), None)
    if current_member:
        current_member.user_name = current_member.user_name or "Owner"

    customers = [
        Customer(id=f"cust_{org_id[:8]}_1", org_id=org_id, name="Starlight Media Group", company_name="Starlight Media Inc.", email="accounts@starlightmedia.com", phone="+1 415 890 1234", currency=org.currency, payment_terms=30, address="742 Evergreen Terrace", country="USA", notes="Strategic enterprise client."),
        Customer(id=f"cust_{org_id[:8]}_2", org_id=org_id, name="Nexus Dynamics", company_name="Nexus Dynamics LLC", email="billing@nexusdynamics.io", currency=org.currency, payment_terms=15, address="450 Mission St", country="USA", notes="B2B SaaS integration client."),
        Customer(id=f"cust_{org_id[:8]}_3", org_id=org_id, name="Horizon Health Systems", company_name="Horizon Health Corp.", email="finance@horizonhealth.org", currency=org.currency, payment_terms=45, address="1200 4th Ave", country="USA", notes="Healthcare compliance audit client."),
        Customer(id=f"cust_{org_id[:8]}_4", org_id=org_id, name="Velocita Labs", company_name="Velocita AI Labs", email="pay@velocitalabs.ai", currency=org.currency, payment_terms=30, address="500 Technology Square", country="USA", notes="AI development partnership."),
    ]
    db.session.add_all(customers)
    db.session.flush()

    vendors = [
        Vendor(id=f"vend_{org_id[:8]}_1", org_id=org_id, name="AWS Cloud Services", company="Amazon Web Services", category="software", notes="Primary cloud infrastructure."),
        Vendor(id=f"vend_{org_id[:8]}_2", org_id=org_id, name="GitHub Enterprise", company="GitHub Inc.", category="software", notes="Code hosting and CI/CD."),
        Vendor(id=f"vend_{org_id[:8]}_3", org_id=org_id, name="WeWork Labs", company="WeWork", category="office", notes="Office and meeting rooms."),
        Vendor(id=f"vend_{org_id[:8]}_4", org_id=org_id, name="Delta Air Lines", company="Delta Air Lines Inc.", category="travel", notes="Client travel."),
    ]
    db.session.add_all(vendors)

    def add_invoice(number: str, customer: Customer, issue_offset: int, due_offset: int, status: str, items, tax_rate: Decimal, discount_rate: Decimal, paid: Decimal):
        subtotal = sum((Decimal(str(q)) * Decimal(str(p)) for _, q, p in items), start=Decimal("0"))
        discount = (subtotal * discount_rate / 100).quantize(Decimal("0.01"))
        tax = ((subtotal - discount) * tax_rate / 100).quantize(Decimal("0.01"))
        total = (subtotal - discount + tax).quantize(Decimal("0.01"))
        inv = Invoice(
            id=f"inv_{org_id[:8]}_{number[-3:]}", org_id=org_id, invoice_number=number,
            customer_id=customer.id, customer_name=customer.name, customer_email=customer.email,
            issue_date=(today + timedelta(days=issue_offset)).isoformat(),
            due_date=(today + timedelta(days=due_offset)).isoformat(), status=status,
            currency=org.currency, subtotal=subtotal, tax_rate=tax_rate, tax_amount=tax,
            discount_rate=discount_rate, discount_amount=discount, total_amount=total,
            paid_amount=paid, balance_due=total - paid, created_by=user_id,
        )
        db.session.add(inv)
        db.session.flush()
        for description, qty, unit_price in items:
            amount = (Decimal(str(qty)) * Decimal(str(unit_price))).quantize(Decimal("0.01"))
            db.session.add(InvoiceItem(invoice_id=inv.id, description=description, quantity=qty, unit_price=unit_price, amount=amount, tax_rate_percent=tax_rate, discount_percent=discount_rate))
        return inv

    inv1 = add_invoice(f"INV-{today.year}-001", customers[0], -60, -30, "paid", [("Cloud architecture implementation", 1, 12000)], Decimal("5"), Decimal("0"), Decimal("12600"))
    inv2 = add_invoice(f"INV-{today.year}-002", customers[1], -45, -10, "partially_paid", [("API gateway integration", 1, 9000)], Decimal("5.5"), Decimal("0"), Decimal("2000"))
    inv3 = add_invoice(f"INV-{today.year}-003", customers[2], -35, -5, "overdue", [("Security compliance audit", 1, 6500)], Decimal("5"), Decimal("0"), Decimal("0"))
    inv4 = add_invoice(f"INV-{today.year}-004", customers[3], -5, 25, "sent", [("Model training pipeline", 1, 4500)], Decimal("0"), Decimal("0"), Decimal("0"))
    org.invoice_sequence_year = today.year
    org.invoice_sequence = max(org.invoice_sequence, 4)

    db.session.add_all([
        Payment(id=f"pay_{org_id[:8]}_1", org_id=org_id, invoice_id=inv1.id, invoice_number=inv1.invoice_number, customer_id=customers[0].id, customer_name=customers[0].name, amount=Decimal("12600"), payment_date=(today - timedelta(days=30)).isoformat(), payment_method="bank_transfer", reference="WIRE-001", created_by=user_id),
        Payment(id=f"pay_{org_id[:8]}_2", org_id=org_id, invoice_id=inv2.id, invoice_number=inv2.invoice_number, customer_id=customers[1].id, customer_name=customers[1].name, amount=Decimal("2000"), payment_date=(today - timedelta(days=5)).isoformat(), payment_method="credit_card", reference="CARD-002", created_by=user_id),
    ])

    db.session.add_all([
        Expense(id=f"exp_{org_id[:8]}_1", org_id=org_id, vendor_id=vendors[0].id, vendor_name=vendors[0].name, category="software", amount=Decimal("1450"), tax_amount=Decimal("0"), currency=org.currency, date=(today - timedelta(days=10)).isoformat(), description="Monthly cloud infrastructure", payment_method="credit_card", reimbursable=False, tax_deductible=True, status="approved", created_by=user_id),
        Expense(id=f"exp_{org_id[:8]}_2", org_id=org_id, vendor_id=vendors[1].id, vendor_name=vendors[1].name, category="software", amount=Decimal("320"), tax_amount=Decimal("0"), currency=org.currency, date=(today - timedelta(days=15)).isoformat(), description="CI/CD and repository licensing", payment_method="credit_card", reimbursable=False, tax_deductible=True, status="approved", created_by=user_id),
        Expense(id=f"exp_{org_id[:8]}_3", org_id=org_id, vendor_id=vendors[2].id, vendor_name=vendors[2].name, category="office", amount=Decimal("800"), tax_amount=Decimal("0"), currency=org.currency, date=(today - timedelta(days=20)).isoformat(), description="Workspace subscription", payment_method="bank_transfer", reimbursable=False, tax_deductible=True, status="approved", created_by=user_id),
        Expense(id=f"exp_{org_id[:8]}_4", org_id=org_id, vendor_id=vendors[3].id, vendor_name=vendors[3].name, category="travel", amount=Decimal("620"), tax_amount=Decimal("0"), currency=org.currency, date=(today - timedelta(days=25)).isoformat(), description="Client onsite travel", payment_method="credit_card", reimbursable=True, tax_deductible=True, status="approved", created_by=user_id),
    ])

    record_activity(org_id, "Loaded sample enterprise data", "organization", org_id, "Added sample customers, vendors, invoices, payments and expenses")
    db.session.commit()
    return {"customers": 4, "vendors": 4, "invoices": 4, "payments": 2, "expenses": 4}


def seed_database():
    app = create_app()
    with app.app_context():
        org = Organization.query.filter_by(id="apex_cloud_corp").first()
        if org:
            print("Seed organization already exists; skipping.")
            return
        org = Organization(id="apex_cloud_corp", name="Apex Cloud Solutions Inc.", currency="USD", default_payment_terms=30, created_by="local-seed", invoice_sequence_year=date.today().year, invoice_sequence=0)
        member = OrganizationMember(id="mem_local_seed", org_id=org.id, user_id="local-seed", user_email="owner@apexcloud.local", user_name="Local Seed Owner", role="owner", status="active", joined_at=datetime.now(timezone.utc))
        db.session.add_all([org, member])
        db.session.commit()
        seed_sample_for_org(org.id, "local-seed")
        print("LedgerPulse sample data seeded.")


if __name__ == "__main__":
    seed_database()

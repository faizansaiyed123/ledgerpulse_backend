from datetime import date, timedelta
from decimal import Decimal
import uuid

from backend.database import db
from backend.models import Customer, Invoice, InvoiceItem, Organization, RecurringInvoice
from backend.routes.invoices import _allocate_invoice_number, _normalize_items
from backend.services.audit import record_activity
from backend.utils import money


def advance_run_date(current: str, frequency: str) -> str:
    import calendar

    d = date.fromisoformat(current)
    if frequency == "weekly":
        return (d + timedelta(days=7)).isoformat()
    if frequency == "biweekly":
        return (d + timedelta(days=14)).isoformat()
    if frequency in {"monthly", "quarterly"}:
        month_delta = 1 if frequency == "monthly" else 3
        index = d.year * 12 + d.month - 1 + month_delta
        year, month = divmod(index, 12)
        month += 1
        day = min(d.day, calendar.monthrange(year, month)[1])
        return date(year, month, day).isoformat()
    return date(d.year + 1, d.month, min(d.day, calendar.monthrange(d.year + 1, d.month)[1])).isoformat()


def generate_due_invoices(org_id: str, actor_uid: str, *, today: date | None = None) -> list[Invoice]:
    today = today or date.today()
    today_str = today.isoformat()
    org = Organization.query.filter_by(id=org_id).with_for_update().one()
    due = (
        RecurringInvoice.query.filter(
            RecurringInvoice.org_id == org_id,
            RecurringInvoice.status == "active",
            RecurringInvoice.next_run_date <= today_str,
        )
        .order_by(RecurringInvoice.next_run_date.asc())
        .with_for_update()
        .all()
    )

    generated: list[Invoice] = []
    for rec in due:
        if rec.max_occurrences is not None and rec.occurrences >= rec.max_occurrences:
            rec.status = "completed"
            continue

        invoice_number = _allocate_invoice_number(org)
        normalized = _normalize_items(rec.items or [])
        subtotal = money(rec.subtotal)
        discount_amount = money(rec.discount_amount)
        tax_amount = money(rec.tax_amount)
        total_amount = money(rec.total_amount)
        if total_amount < 0 or subtotal < 0 or discount_amount < 0 or tax_amount < 0:
            raise ValueError("Recurring invoice contains invalid financial amounts")
        if total_amount != money(subtotal - discount_amount + tax_amount):
            raise ValueError("Recurring invoice totals are inconsistent")

        customer = Customer.query.filter_by(id=rec.customer_id, org_id=org_id).first()
        if not customer:
            raise ValueError("Recurring invoice references a missing customer")

        inv = Invoice(
            id=f"inv_{uuid.uuid4().hex}",
            org_id=org_id,
            invoice_number=invoice_number,
            customer_id=rec.customer_id,
            customer_name=customer.name,
            customer_email=customer.email,
            status="sent",
            currency=rec.currency,
            issue_date=today_str,
            due_date=(today + timedelta(days=org.default_payment_terms)).isoformat(),
            subtotal=subtotal,
            tax_rate=(tax_amount / (subtotal - discount_amount) * Decimal("100")).quantize(Decimal("0.01")) if subtotal > discount_amount and tax_amount else Decimal("0"),
            tax_amount=tax_amount,
            discount_rate=(discount_amount / subtotal * Decimal("100")).quantize(Decimal("0.01")) if subtotal else Decimal("0"),
            discount_amount=discount_amount,
            total_amount=total_amount,
            paid_amount=Decimal("0.00"),
            balance_due=total_amount,
            notes=rec.notes,
            terms=rec.terms,
            recurring_id=rec.id,
            created_by=actor_uid,
        )
        db.session.add(inv)
        for item in normalized:
            db.session.add(
                InvoiceItem(
                    invoice_id=inv.id,
                    description=item["description"],
                    quantity=item["quantity"],
                    unit_price=item["unitPrice"],
                    discount_percent=item["discountPercent"],
                    tax_rate_percent=item["taxRatePercent"],
                    amount=item["amount"],
                )
            )

        rec.occurrences += 1
        rec.last_run_date = today_str
        if rec.max_occurrences is not None and rec.occurrences >= rec.max_occurrences:
            rec.status = "completed"
        else:
            rec.next_run_date = advance_run_date(rec.next_run_date, rec.frequency)
        record_activity(org_id, "Generated recurring invoice", "invoice", inv.id, invoice_number, actor_uid=actor_uid)
        generated.append(inv)

    return generated


def refresh_overdue_statuses(org_id: str, *, today: date | None = None) -> int:
    today_str = (today or date.today()).isoformat()
    invoices = Invoice.query.filter(
        Invoice.org_id == org_id,
        Invoice.status.in_(["sent", "partially_paid", "overdue"]),
        Invoice.balance_due > 0,
        Invoice.due_date < today_str,
    ).with_for_update().all()
    changed = 0
    for invoice in invoices:
        if invoice.status != "overdue":
            invoice.status = "overdue"
            changed += 1
    return changed


def run_for_org(org_id: str, actor_uid: str, *, today: date | None = None) -> list[Invoice]:
    generated = generate_due_invoices(org_id, actor_uid, today=today)
    refresh_overdue_statuses(org_id, today=today)
    db.session.commit()
    return generated

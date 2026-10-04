import re
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


MONEY_QUANT = Decimal("0.01")
ALLOWED_CURRENCIES = {"USD", "EUR", "GBP", "INR", "AUD", "CAD", "JPY", "SGD"}
MEMBER_ROLES = {"owner", "admin", "accountant", "staff"}
INVOICE_STATUSES = {"draft", "sent", "partially_paid", "paid", "overdue", "cancelled"}
EXPENSE_STATUSES = {"pending", "approved", "rejected"}
PAYMENT_METHODS = {"credit_card", "bank_transfer", "paypal", "cash", "check", "stripe_test"}
EXPENSE_CATEGORIES = {
    "travel",
    "meals",
    "software",
    "office",
    "advertising",
    "utilities",
    "consulting",
    "equipment",
    "other",
}
RECURRING_FREQUENCIES = {"weekly", "biweekly", "monthly", "quarterly", "yearly"}


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def money(value, *, positive: bool = False, non_negative: bool = True) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Amount must be a valid number")
    if not result.is_finite():
        raise ValueError("Amount must be finite")
    if positive and result <= 0:
        raise ValueError("Amount must be greater than zero")
    if non_negative and result < 0:
        raise ValueError("Amount cannot be negative")
    return result.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def percent(value, *, max_value: Decimal = Decimal("100")) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Percentage must be a valid number")
    if not result.is_finite() or result < 0 or result > max_value:
        raise ValueError(f"Percentage must be between 0 and {max_value}")
    return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parse_date(value, field_name: str):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} is required")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError(f"{field_name} must be an ISO date (YYYY-MM-DD)")


def clean_text(value, field_name: str, *, required: bool = False, max_length: int = 5000) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{field_name} is required")
    if len(value) > max_length:
        raise ValueError(f"{field_name} is too long")
    return value


def validate_identifier(value, field_name: str = "id") -> str:
    value = clean_text(value, field_name, required=True, max_length=128)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(f"{field_name} contains invalid characters")
    return value


def money_float(value: Decimal) -> float:
    return float(value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))

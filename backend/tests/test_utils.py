from decimal import Decimal

import pytest

from backend.utils import money, percent, parse_date


def test_money_rounds_decimal_values():
    assert money("10.005") == Decimal("10.01")
    assert money("0") == Decimal("0.00")


def test_money_rejects_negative_and_non_finite_values():
    with pytest.raises(ValueError):
        money("-1")
    with pytest.raises(ValueError):
        money("NaN")


def test_percent_range_and_date_validation():
    assert percent("5.5") == Decimal("5.50")
    with pytest.raises(ValueError):
        percent("101")
    assert parse_date("2026-10-04", "issueDate") == "2026-10-04"
    with pytest.raises(ValueError):
        parse_date("10/04/2026", "issueDate")

from decimal import Decimal

from educonnect_engine.pedagogy.presentation.formatting import (
    format_amount,
    format_chf,
    format_rate_percent,
)


def test_format_amount_uses_apostrophe_thousands_separator_and_two_decimals():
    assert format_amount(Decimal("12500.000")) == "12'500.00"
    assert format_amount(Decimal("9000.00")) == "9'000.00"
    assert format_amount(Decimal("100000")) == "100'000.00"


def test_format_chf_appends_the_chf_suffix():
    assert format_chf(Decimal("12500.000")) == "12'500.00 CHF"
    assert format_chf(Decimal("9000.00")) == "9'000.00 CHF"
    assert format_chf(Decimal("100000")) == "100'000.00 CHF"


def test_format_rate_percent_strips_unnecessary_trailing_zeros():
    assert format_rate_percent(Decimal("0.125")) == "12.5 %"
    assert format_rate_percent(Decimal("0.20")) == "20 %"
    assert format_rate_percent(Decimal("0.25")) == "25 %"


def test_format_helpers_never_mutate_the_input_decimal():
    original = Decimal("12500.000")
    format_amount(original)
    format_chf(original)

    assert original == Decimal("12500.000")

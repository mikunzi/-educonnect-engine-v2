"""Presentation-only display formatting for AMO-001 pages.

These are pure functions that format already-computed `Decimal` values for
human reading (Swiss apostrophe thousands separator, fixed 2 decimals,
trimmed percentages). They never round or otherwise change the caller's
stored value — they only decide how it looks on the page.

This module belongs to the presentation layer, not to `pedagogy.domain`:
the domain produces semantic values (amounts, rates, accounts); deciding
how those are typeset for a learner is a presentation concern. Registered
as Jinja filters (`amount`, `chf`, `rate_percent`) in `web.py`.
"""

from decimal import ROUND_HALF_UP, Decimal


def format_amount(value: Decimal) -> str:
    """Format a Decimal as a Swiss-readable amount: apostrophe thousands, 2 decimals.

    Display-only: never mutates or rounds the caller's stored Decimal value.
    """
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{quantized:,.2f}".replace(",", "'")


def format_chf(value: Decimal) -> str:
    """Format a Decimal as a Swiss-readable CHF amount, e.g. `12'500.00 CHF`."""
    return f"{format_amount(value)} CHF"


def format_rate_percent(rate: Decimal) -> str:
    """Format a Decimal rate as a percentage without unnecessary trailing zeros."""
    percent = rate * Decimal(100)
    text = f"{percent:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text} %"

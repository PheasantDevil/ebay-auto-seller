"""Pure logic helpers for market-stats-refresh worker."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def summarize_prices(values: list[Decimal]) -> tuple[Decimal, int]:
    """Return average price and count for non-empty decimal list."""
    if not values:
        return Decimal("0.00"), 0
    total = sum(values, start=Decimal("0"))
    avg = (total / Decimal(len(values))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return avg, len(values)

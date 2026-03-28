from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def minimum_list_price_for_target_profit(
    *,
    item_price_usd: Decimal,
    estimated_shipping_usd: Decimal,
    ebay_fee_rate: Decimal,
    sales_tax_rate_assumed: Decimal,
    target_profit_usd: Decimal,
) -> Decimal:
    """Minimum list price so net profit meets target (same fee/tax model as API pricing)."""
    denom = Decimal("1") - ebay_fee_rate - sales_tax_rate_assumed
    if denom <= Decimal("0"):
        raise ValueError("ebay_fee_rate + sales_tax_rate_assumed must be < 1")
    num = item_price_usd + estimated_shipping_usd + target_profit_usd
    if num < 0:
        raise ValueError("Cost + target profit must be non-negative")
    return (num / denom).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def apply_market_cap(
    *,
    floor_price_usd: Decimal,
    market_avg_usd: Decimal | None,
    cap_to_market: bool,
) -> Decimal:
    """Optionally cap list price at latest market average."""
    if not cap_to_market or market_avg_usd is None:
        return floor_price_usd
    cap = market_avg_usd.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return min(floor_price_usd, cap)


def price_needs_update(*, current_usd: Decimal, desired_usd: Decimal) -> bool:
    return current_usd.quantize(Decimal("0.01")) != desired_usd.quantize(Decimal("0.01"))

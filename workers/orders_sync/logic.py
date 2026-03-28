from __future__ import annotations

from decimal import Decimal


def compute_net_profit_usd_baseline(
    *,
    sale_price_usd: Decimal,
    ebay_fees_usd: Decimal | None,
    cogs_usd: Decimal | None,
    tax_paid_usd: Decimal | None,
) -> Decimal:
    """Rough net profit when API does not supply net_profit_usd.

    sale - fees - COGS - tax (tax treated as pass-through cost here).
    """
    fees = Decimal("0") if ebay_fees_usd is None else ebay_fees_usd
    cogs = Decimal("0") if cogs_usd is None else cogs_usd
    tax = Decimal("0") if tax_paid_usd is None else tax_paid_usd
    return (sale_price_usd - fees - cogs - tax).quantize(Decimal("0.01"))

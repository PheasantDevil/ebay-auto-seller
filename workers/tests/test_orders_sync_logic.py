from decimal import Decimal

from orders_sync.logic import compute_net_profit_usd_baseline


def test_compute_net_profit_baseline():
    assert compute_net_profit_usd_baseline(
        sale_price_usd=Decimal("100"),
        ebay_fees_usd=Decimal("12"),
        cogs_usd=Decimal("50"),
        tax_paid_usd=Decimal("8"),
    ) == Decimal("30.00")


def test_compute_net_profit_baseline_missing_components():
    assert compute_net_profit_usd_baseline(
        sale_price_usd=Decimal("40"),
        ebay_fees_usd=None,
        cogs_usd=None,
        tax_paid_usd=None,
    ) == Decimal("40.00")

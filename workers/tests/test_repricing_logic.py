from decimal import Decimal

from repricing.logic import (
    apply_market_cap,
    minimum_list_price_for_target_profit,
    price_needs_update,
)


def test_minimum_list_price_matches_fee_tax_model():
    # item 40 + ship 10 + target 10 = 60; fee 12% + tax 10% => denom 0.78 => 60/0.78
    p = minimum_list_price_for_target_profit(
        item_price_usd=Decimal("40"),
        estimated_shipping_usd=Decimal("10"),
        ebay_fee_rate=Decimal("0.12"),
        sales_tax_rate_assumed=Decimal("0.10"),
        target_profit_usd=Decimal("10"),
    )
    assert p == Decimal("76.92")


def test_apply_market_cap_reduces_floor():
    floor = Decimal("100.00")
    cap = apply_market_cap(
        floor_price_usd=floor,
        market_avg_usd=Decimal("80"),
        cap_to_market=True,
    )
    assert cap == Decimal("80.00")


def test_apply_market_cap_disabled():
    assert apply_market_cap(
        floor_price_usd=Decimal("100"),
        market_avg_usd=Decimal("80"),
        cap_to_market=False,
    ) == Decimal("100")


def test_price_needs_update_false_when_equal_cents():
    assert price_needs_update(current_usd=Decimal("10.001"), desired_usd=Decimal("10.00")) is False

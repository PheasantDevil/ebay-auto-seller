from decimal import Decimal

from market_stats_refresh.logic import summarize_prices


def test_summarize_prices_with_values() -> None:
    """Average and count should be computed for non-empty values."""
    avg, count = summarize_prices([Decimal("10.00"), Decimal("20.00"), Decimal("30.00")])
    assert avg == Decimal("20.00")
    assert count == 3


def test_summarize_prices_empty() -> None:
    """Empty values should return zero metrics."""
    avg, count = summarize_prices([])
    assert avg == Decimal("0.00")
    assert count == 0

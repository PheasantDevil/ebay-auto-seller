from decimal import Decimal

from fastapi.testclient import TestClient

from app.domain.pricing import calculate_profit_usd
from app.main import app
from app.repositories.research_repo import ResearchRow
from app.routes.research import get_research_repository


class FakeResearchRepository:
    """In-memory repository replacement for research candidates tests."""

    def __init__(self, rows: list[ResearchRow]) -> None:
        """Create fake repository with a predefined dataset."""
        self._rows = rows

    def fetch_research_rows(
        self, *, tenant_id: str, limit_variants: int | None = None
    ) -> list[ResearchRow]:
        """Return predefined rows regardless of tenant."""
        return self._rows


def _make_row(
    *,
    variant_id: str,
    variant_name: str,
    product_title: str,
    avg_sold_price_usd: str,
    item_price_usd: str,
    estimated_shipping_usd: str,
    ebay_fee_rate: str,
    sales_tax_rate_assumed: str,
) -> ResearchRow:
    """Create a ResearchRow from stringified decimals."""

    return ResearchRow(
        variant_id=variant_id,
        variant_name=variant_name,
        product_title=product_title,
        avg_sold_price_usd=Decimal(avg_sold_price_usd),
        item_price_usd=Decimal(item_price_usd),
        estimated_shipping_usd=Decimal(estimated_shipping_usd),
        ebay_fee_rate=Decimal(ebay_fee_rate),
        sales_tax_rate_assumed=Decimal(sales_tax_rate_assumed),
    )


def test_get_research_candidates_selects_best_positive_profit():
    """Ensure candidates return best row per variant and only positive profits."""

    # Variant A has two supplier states; choose the one with higher net profit.
    row_a1 = _make_row(
        variant_id="11111111-1111-1111-1111-111111111111",
        variant_name="Red / 1-Pack",
        product_title="Test Product A",
        avg_sold_price_usd="100",
        item_price_usd="40",
        estimated_shipping_usd="10",
        ebay_fee_rate="0.12",
        sales_tax_rate_assumed="0.10",
    )
    row_a2 = _make_row(
        variant_id="11111111-1111-1111-1111-111111111111",
        variant_name="Red / 1-Pack",
        product_title="Test Product A",
        avg_sold_price_usd="100",
        item_price_usd="50",
        estimated_shipping_usd="5",
        ebay_fee_rate="0.12",
        sales_tax_rate_assumed="0.10",
    )

    # Variant B is unprofitable and must be excluded by rule A.
    row_b1 = _make_row(
        variant_id="22222222-2222-2222-2222-222222222222",
        variant_name="Blue / 2-Pack",
        product_title="Test Product B",
        avg_sold_price_usd="60",
        item_price_usd="50",
        estimated_shipping_usd="8",
        ebay_fee_rate="0.12",
        sales_tax_rate_assumed="0.10",
    )

    def _override_repo():
        """Override FastAPI dependency with fake in-memory repo."""
        return FakeResearchRepository(rows=[row_a1, row_a2, row_b1])

    app.dependency_overrides[get_research_repository] = _override_repo
    try:
        client = TestClient(app)
        resp = client.get(
            "/research/candidates",
            params={"tenant_id": "00000000-0000-0000-0000-000000000000", "limit": 10},
        )
        assert resp.status_code == 200

        payload = resp.json()
        assert "candidates" in payload
        assert len(payload["candidates"]) == 1  # only variant A should remain

        candidate = payload["candidates"][0]
        assert candidate["variant_id"] == row_a1.variant_id
        assert candidate["variant_name"] == row_a1.variant_name
        assert candidate["product_title"] == row_a1.product_title

        # Validate computed net profit for chosen row.
        expected = calculate_profit_usd(
            avg_sold_price_usd=row_a1.avg_sold_price_usd,
            item_price_usd=row_a1.item_price_usd,
            estimated_shipping_usd=row_a1.estimated_shipping_usd,
            ebay_fee_rate=row_a1.ebay_fee_rate,
            sales_tax_rate_assumed=row_a1.sales_tax_rate_assumed,
        )
        assert candidate["net_profit_usd"] == float(expected["net_profit_usd"])
    finally:
        app.dependency_overrides.clear()

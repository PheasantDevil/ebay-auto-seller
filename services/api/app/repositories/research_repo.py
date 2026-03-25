from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import psycopg


@dataclass(frozen=True)
class ResearchRow:
    """Single candidate row derived from one variant + one supplier state."""

    variant_id: str
    variant_name: str
    product_title: str
    avg_sold_price_usd: Decimal
    item_price_usd: Decimal
    estimated_shipping_usd: Decimal
    ebay_fee_rate: Decimal
    sales_tax_rate_assumed: Decimal


class ResearchRepository:
    """Repository for fetching candidate inputs needed for profit calculation."""

    def __init__(self, database_url: str) -> None:
        """Create repository with a PostgreSQL database connection string."""
        self._database_url = database_url

    def fetch_research_rows(
        self, *, tenant_id: str, limit_variants: int | None = None
    ) -> list[ResearchRow]:
        """Fetch candidate rows for a tenant.

        This query:
        - selects latest market_stats per variant
        - requires active pricing_assumptions
        - requires current sourcing state with source_stock_qty > 0
        - requires inventory_current with on_hand_qty > 0

        Missing required data is excluded by using inner joins (aligned with rule A).
        """

        limit_clause = ""
        if limit_variants is not None:
            # We limit by number of variants after grouping in the service layer,
            # so keep this as a soft limit to reduce row explosion early.
            limit_clause = "LIMIT %(limit)s"

        sql = f"""
        WITH latest_market_stats AS (
          SELECT DISTINCT ON (tenant_id, variant_id)
            tenant_id,
            variant_id,
            avg_sold_price_usd
          FROM market_stats
          WHERE tenant_id = %(tenant_id)s
          ORDER BY tenant_id, variant_id, retrieved_at DESC
        )
        SELECT
          pv.id::text AS variant_id,
          pv.variant_name,
          p.title AS product_title,
          lm.avg_sold_price_usd,
          ss.item_price_usd,
          ss.estimated_shipping_usd,
          pa.ebay_fee_rate,
          pa.sales_tax_rate_assumed
        FROM product_variants pv
        JOIN products p
          ON p.id = pv.product_id AND p.tenant_id = pv.tenant_id
        JOIN inventory_current ic
          ON ic.variant_id = pv.id AND ic.tenant_id = pv.tenant_id AND ic.on_hand_qty > 0
        JOIN latest_market_stats lm
          ON lm.variant_id = pv.id AND lm.tenant_id = pv.tenant_id
        JOIN pricing_assumptions pa
          ON pa.variant_id = pv.id AND pa.tenant_id = pv.tenant_id AND pa.active = TRUE
        JOIN sourcing_item_state_current ss
          ON ss.variant_id = pv.id AND ss.tenant_id = pv.tenant_id AND ss.source_stock_qty > 0
        WHERE pv.tenant_id = %(tenant_id)s
        {limit_clause}
        """

        params: dict[str, object] = {"tenant_id": tenant_id}
        if limit_variants is not None:
            params["limit"] = int(limit_variants)

        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        result: list[ResearchRow] = []
        for row in rows:
            (
                variant_id,
                variant_name,
                product_title,
                avg_sold_price_usd,
                item_price_usd,
                estimated_shipping_usd,
                ebay_fee_rate,
                sales_tax_rate_assumed,
            ) = row
            result.append(
                ResearchRow(
                    variant_id=variant_id,
                    variant_name=variant_name,
                    product_title=product_title,
                    avg_sold_price_usd=avg_sold_price_usd,
                    item_price_usd=item_price_usd,
                    estimated_shipping_usd=estimated_shipping_usd,
                    ebay_fee_rate=ebay_fee_rate,
                    sales_tax_rate_assumed=sales_tax_rate_assumed,
                )
            )

        return result

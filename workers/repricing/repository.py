from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal

import psycopg


@dataclass(frozen=True)
class RepricingListingRow:
    ebay_listing_id: str
    ebay_item_id: str
    variant_id: str
    fixed_price_usd: Decimal
    ebay_fee_rate: Decimal
    sales_tax_rate_assumed: Decimal
    target_profit_usd: Decimal
    market_avg_usd: Decimal | None
    item_price_usd: Decimal | None
    estimated_shipping_usd: Decimal | None


class RepricingRepository:
    def create_job_run(
        self,
        conn: psycopg.Connection,
        *,
        tenant_id: str,
        job_type: str,
        idempotency_key: str | None,
    ) -> str:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO job_runs (tenant_id, job_type, idempotency_key, status, started_at)
                VALUES (%(tenant_id)s, %(job_type)s, %(idempotency_key)s, 'running', now())
                RETURNING id::text
                """,
                {
                    "tenant_id": tenant_id,
                    "job_type": job_type,
                    "idempotency_key": idempotency_key,
                },
            )
            return cur.fetchone()[0]

    def finish_job_run(
        self,
        conn: psycopg.Connection,
        *,
        job_run_id: str,
        status: str,
        error_message: str | None,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE job_runs
                SET status=%(status)s, finished_at=now(), error_message=%(error_message)s
                WHERE id=%(job_run_id)s
                """,
                {"job_run_id": job_run_id, "status": status, "error_message": error_message},
            )

    def fetch_listings_for_repricing(
        self, conn: psycopg.Connection, *, tenant_id: str
    ) -> list[RepricingListingRow]:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH latest_ms AS (
                  SELECT DISTINCT ON (variant_id)
                    variant_id,
                    avg_sold_price_usd
                  FROM market_stats
                  WHERE tenant_id = %(tenant_id)s
                  ORDER BY variant_id, retrieved_at DESC
                ),
                best_sourcing AS (
                  SELECT DISTINCT ON (variant_id)
                    variant_id,
                    item_price_usd,
                    estimated_shipping_usd
                  FROM sourcing_item_state_current
                  WHERE tenant_id = %(tenant_id)s AND source_stock_qty > 0
                  ORDER BY variant_id, (item_price_usd + estimated_shipping_usd) ASC
                )
                SELECT
                  el.id::text,
                  el.ebay_item_id,
                  el.variant_id::text,
                  el.fixed_price_usd,
                  pa.ebay_fee_rate,
                  pa.sales_tax_rate_assumed,
                  pa.target_profit_usd,
                  lm.avg_sold_price_usd,
                  bs.item_price_usd,
                  bs.estimated_shipping_usd
                FROM ebay_listings el
                JOIN pricing_assumptions pa
                  ON pa.tenant_id = el.tenant_id
                 AND pa.variant_id = el.variant_id
                 AND pa.active = TRUE
                LEFT JOIN latest_ms lm ON lm.variant_id = el.variant_id
                LEFT JOIN best_sourcing bs ON bs.variant_id = el.variant_id
                WHERE el.tenant_id = %(tenant_id)s
                  AND el.listing_status = 'active'
                ORDER BY el.updated_at DESC
                """,
                {"tenant_id": tenant_id},
            )
            rows = cur.fetchall()

        out: list[RepricingListingRow] = []
        for row in rows:
            market_avg = row[7]
            item_p = row[8]
            ship = row[9]
            out.append(
                RepricingListingRow(
                    ebay_listing_id=row[0],
                    ebay_item_id=row[1],
                    variant_id=row[2],
                    fixed_price_usd=Decimal(str(row[3])),
                    ebay_fee_rate=Decimal(str(row[4])),
                    sales_tax_rate_assumed=Decimal(str(row[5])),
                    target_profit_usd=Decimal(str(row[6])),
                    market_avg_usd=None if market_avg is None else Decimal(str(market_avg)),
                    item_price_usd=None if item_p is None else Decimal(str(item_p)),
                    estimated_shipping_usd=None if ship is None else Decimal(str(ship)),
                )
            )
        return out

    def update_listing_price(
        self,
        conn: psycopg.Connection,
        *,
        tenant_id: str,
        listing: RepricingListingRow,
        new_price_usd: Decimal,
        idempotency_key: str,
        reason: str,
        context: dict[str, object],
    ) -> None:
        old = listing.fixed_price_usd.quantize(Decimal("0.01"))
        new_p = new_price_usd.quantize(Decimal("0.01"))
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ebay_listing_updates (
                  tenant_id, ebay_listing_id, ebay_item_id, update_type, idempotency_key,
                  old_price_usd, new_price_usd, reason, context
                )
                VALUES (
                  %(tenant_id)s, %(ebay_listing_id)s, %(ebay_item_id)s, 'repricing',
                  %(idempotency_key)s,
                  %(old_price_usd)s, %(new_price_usd)s, %(reason)s, %(context)s::jsonb
                )
                ON CONFLICT (tenant_id, idempotency_key)
                DO NOTHING
                """,
                {
                    "tenant_id": tenant_id,
                    "ebay_listing_id": listing.ebay_listing_id,
                    "ebay_item_id": listing.ebay_item_id,
                    "idempotency_key": idempotency_key,
                    "old_price_usd": old,
                    "new_price_usd": new_p,
                    "reason": reason,
                    "context": json.dumps(context),
                },
            )

            cur.execute(
                """
                UPDATE ebay_listings
                SET fixed_price_usd=%(new_price)s, last_synced_at=now(), updated_at=now()
                WHERE tenant_id=%(tenant_id)s AND id=%(ebay_listing_id)s
                """,
                {
                    "tenant_id": tenant_id,
                    "ebay_listing_id": listing.ebay_listing_id,
                    "new_price": new_p,
                },
            )

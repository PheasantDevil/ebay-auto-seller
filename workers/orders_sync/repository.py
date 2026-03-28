from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import psycopg


@dataclass(frozen=True)
class OrderUpsertRow:
    ebay_order_id: str
    ebay_transaction_id: str | None
    ebay_listing_id: str | None
    ebay_item_id: str | None
    variant_id: str | None
    sold_at: datetime
    sale_price_usd: Decimal
    shipping_paid_usd: Decimal | None
    tax_paid_usd: Decimal | None
    ebay_fees_usd: Decimal | None
    cogs_usd: Decimal | None
    net_profit_usd: Decimal
    currency: str
    return_status: str | None
    raw_payload: dict[str, object]


class OrdersSyncRepository:
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

    def upsert_order(
        self,
        conn: psycopg.Connection,
        *,
        tenant_id: str,
        row: OrderUpsertRow,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orders (
                  tenant_id, ebay_order_id, ebay_transaction_id,
                  ebay_listing_id, ebay_item_id, variant_id,
                  sold_at, sale_price_usd, shipping_paid_usd, tax_paid_usd,
                  ebay_fees_usd, cogs_usd, net_profit_usd,
                  currency, return_status, raw_payload
                )
                VALUES (
                  %(tenant_id)s, %(ebay_order_id)s, %(ebay_transaction_id)s,
                  %(ebay_listing_id)s, %(ebay_item_id)s, %(variant_id)s,
                  %(sold_at)s, %(sale_price_usd)s, %(shipping_paid_usd)s, %(tax_paid_usd)s,
                  %(ebay_fees_usd)s, %(cogs_usd)s, %(net_profit_usd)s,
                  %(currency)s, %(return_status)s, %(raw_payload)s::jsonb
                )
                ON CONFLICT (tenant_id, ebay_order_id)
                DO UPDATE SET
                  ebay_transaction_id = EXCLUDED.ebay_transaction_id,
                  ebay_listing_id = EXCLUDED.ebay_listing_id,
                  ebay_item_id = EXCLUDED.ebay_item_id,
                  variant_id = EXCLUDED.variant_id,
                  sold_at = EXCLUDED.sold_at,
                  sale_price_usd = EXCLUDED.sale_price_usd,
                  shipping_paid_usd = EXCLUDED.shipping_paid_usd,
                  tax_paid_usd = EXCLUDED.tax_paid_usd,
                  ebay_fees_usd = EXCLUDED.ebay_fees_usd,
                  cogs_usd = EXCLUDED.cogs_usd,
                  net_profit_usd = EXCLUDED.net_profit_usd,
                  currency = EXCLUDED.currency,
                  return_status = EXCLUDED.return_status,
                  raw_payload = EXCLUDED.raw_payload
                """,
                {
                    "tenant_id": tenant_id,
                    "ebay_order_id": row.ebay_order_id,
                    "ebay_transaction_id": row.ebay_transaction_id,
                    "ebay_listing_id": row.ebay_listing_id,
                    "ebay_item_id": row.ebay_item_id,
                    "variant_id": row.variant_id,
                    "sold_at": row.sold_at,
                    "sale_price_usd": row.sale_price_usd,
                    "shipping_paid_usd": row.shipping_paid_usd,
                    "tax_paid_usd": row.tax_paid_usd,
                    "ebay_fees_usd": row.ebay_fees_usd,
                    "cogs_usd": row.cogs_usd,
                    "net_profit_usd": row.net_profit_usd,
                    "currency": row.currency,
                    "return_status": row.return_status,
                    "raw_payload": json.dumps(row.raw_payload),
                },
            )

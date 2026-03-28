from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal

import psycopg

from sourcing_scan.adapters.base import SupplierState


@dataclass(frozen=True)
class SourcingDbItem:
    """One active sourcing_source_item joined with its sourcing_sources row."""

    sourcing_source_item_id: str
    variant_id: str
    source_type: str
    source_url: str


class SourcingScanRepository:
    def ensure_default_warehouse(self, conn: psycopg.Connection, *, tenant_id: str) -> str:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text
                FROM warehouses
                WHERE tenant_id=%(tenant_id)s
                ORDER BY created_at ASC
                LIMIT 1
                """,
                {"tenant_id": tenant_id},
            )
            row = cur.fetchone()
            if row:
                return row[0]

            cur.execute(
                """
                INSERT INTO warehouses (tenant_id, name, address_json)
                VALUES (%(tenant_id)s, 'default', NULL)
                RETURNING id::text
                """,
                {"tenant_id": tenant_id},
            )
            return cur.fetchone()[0]

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

    def fetch_active_sourcing_items(
        self,
        conn: psycopg.Connection,
        *,
        tenant_id: str,
        limit: int,
    ) -> list[SourcingDbItem]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  ssi.id::text,
                  ssi.variant_id::text,
                  lower(ss.source_type) AS source_type,
                  ssi.source_url
                FROM sourcing_source_items ssi
                JOIN sourcing_sources ss
                  ON ss.id = ssi.sourcing_source_id
                 AND ss.tenant_id = ssi.tenant_id
                WHERE ssi.tenant_id = %(tenant_id)s
                  AND ssi.active = TRUE
                ORDER BY ssi.updated_at DESC NULLS LAST, ssi.created_at DESC
                LIMIT %(limit)s
                """,
                {"tenant_id": tenant_id, "limit": int(limit)},
            )
            rows = cur.fetchall()
        return [
            SourcingDbItem(
                sourcing_source_item_id=row[0],
                variant_id=row[1],
                source_type=str(row[2]),
                source_url=str(row[3]),
            )
            for row in rows
        ]

    def upsert_supplier_state_current(
        self,
        conn: psycopg.Connection,
        *,
        tenant_id: str,
        job_run_id: str,
        state: SupplierState,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sourcing_item_state_current (
                  tenant_id, sourcing_source_item_id, variant_id,
                  item_price_usd, estimated_shipping_usd, estimated_sales_tax_rate_assumed,
                  source_stock_qty, last_job_run_id
                )
                VALUES (
                  %(tenant_id)s, %(sourcing_source_item_id)s, %(variant_id)s,
                  %(item_price_usd)s, %(estimated_shipping_usd)s,
                  %(estimated_sales_tax_rate_assumed)s,
                  %(source_stock_qty)s, %(job_run_id)s
                )
                ON CONFLICT (tenant_id, sourcing_source_item_id)
                DO UPDATE SET
                  variant_id = EXCLUDED.variant_id,
                  item_price_usd = EXCLUDED.item_price_usd,
                  estimated_shipping_usd = EXCLUDED.estimated_shipping_usd,
                  estimated_sales_tax_rate_assumed = EXCLUDED.estimated_sales_tax_rate_assumed,
                  source_stock_qty = EXCLUDED.source_stock_qty,
                  last_job_run_id = EXCLUDED.last_job_run_id,
                  updated_at = now()
                """,
                {
                    "tenant_id": tenant_id,
                    "sourcing_source_item_id": state.sourcing_source_item_id,
                    "variant_id": state.variant_id,
                    "item_price_usd": _to_money(state.item_price_usd),
                    "estimated_shipping_usd": _to_money(state.estimated_shipping_usd),
                    "estimated_sales_tax_rate_assumed": state.estimated_sales_tax_rate_assumed,
                    "source_stock_qty": int(state.source_stock_qty),
                    "job_run_id": job_run_id,
                },
            )

    def insert_supplier_state_history(
        self,
        conn: psycopg.Connection,
        *,
        tenant_id: str,
        job_run_id: str,
        state: SupplierState,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sourcing_item_state_history (
                  tenant_id, sourcing_source_item_id, variant_id,
                  item_price_usd, estimated_shipping_usd, estimated_sales_tax_rate_assumed,
                  source_stock_qty, captured_by_job_run_id, raw_payload
                )
                VALUES (
                  %(tenant_id)s, %(sourcing_source_item_id)s, %(variant_id)s,
                  %(item_price_usd)s, %(estimated_shipping_usd)s,
                  %(estimated_sales_tax_rate_assumed)s,
                  %(source_stock_qty)s, %(job_run_id)s, %(raw_payload)s::jsonb
                )
                ON CONFLICT (tenant_id, sourcing_source_item_id, captured_by_job_run_id)
                DO NOTHING
                """,
                {
                    "tenant_id": tenant_id,
                    "sourcing_source_item_id": state.sourcing_source_item_id,
                    "variant_id": state.variant_id,
                    "item_price_usd": _to_money(state.item_price_usd),
                    "estimated_shipping_usd": _to_money(state.estimated_shipping_usd),
                    "estimated_sales_tax_rate_assumed": state.estimated_sales_tax_rate_assumed,
                    "source_stock_qty": int(state.source_stock_qty),
                    "job_run_id": job_run_id,
                    "raw_payload": json.dumps(state.raw_payload),
                },
            )

    def upsert_inventory_current(
        self,
        conn: psycopg.Connection,
        *,
        tenant_id: str,
        warehouse_id: str,
        variant_id: str,
        on_hand_qty: int,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO inventory_current (
                  tenant_id, variant_id, warehouse_id, on_hand_qty, safety_stock_threshold
                )
                VALUES (%(tenant_id)s, %(variant_id)s, %(warehouse_id)s, %(on_hand_qty)s, 0)
                ON CONFLICT (tenant_id, variant_id, warehouse_id)
                DO UPDATE SET
                  on_hand_qty = EXCLUDED.on_hand_qty,
                  updated_at = now()
                """,
                {
                    "tenant_id": tenant_id,
                    "variant_id": variant_id,
                    "warehouse_id": warehouse_id,
                    "on_hand_qty": int(on_hand_qty),
                },
            )

    def fetch_safety_stock_thresholds(
        self, conn: psycopg.Connection, *, tenant_id: str, warehouse_id: str
    ) -> dict[str, int]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT variant_id::text, safety_stock_threshold
                FROM inventory_current
                WHERE tenant_id=%(tenant_id)s AND warehouse_id=%(warehouse_id)s
                """,
                {"tenant_id": tenant_id, "warehouse_id": warehouse_id},
            )
            rows = cur.fetchall()
        return {row[0]: int(row[1]) for row in rows}


def _to_money(v: Decimal) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"))

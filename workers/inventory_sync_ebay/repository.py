from __future__ import annotations

import json
from dataclasses import dataclass

import psycopg


@dataclass(frozen=True)
class ListingRow:
    ebay_listing_id: str
    ebay_item_id: str
    variant_id: str
    current_qty: int
    listing_status: str


class InventorySyncEbayRepository:
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

    def fetch_active_listings(
        self, conn: psycopg.Connection, *, tenant_id: str
    ) -> list[ListingRow]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  id::text,
                  ebay_item_id,
                  variant_id::text,
                  quantity,
                  listing_status
                FROM ebay_listings
                WHERE tenant_id=%(tenant_id)s
                  AND listing_status='active'
                ORDER BY updated_at DESC
                """,
                {"tenant_id": tenant_id},
            )
            rows = cur.fetchall()

        return [
            ListingRow(
                ebay_listing_id=row[0],
                ebay_item_id=row[1],
                variant_id=row[2],
                current_qty=int(row[3]),
                listing_status=row[4],
            )
            for row in rows
        ]

    def fetch_variant_available_qty(
        self, conn: psycopg.Connection, *, tenant_id: str
    ) -> dict[str, int]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT variant_id::text, MAX(on_hand_qty) as available_qty
                FROM inventory_current
                WHERE tenant_id=%(tenant_id)s
                GROUP BY variant_id
                """,
                {"tenant_id": tenant_id},
            )
            rows = cur.fetchall()
        return {row[0]: int(row[1]) for row in rows}

    def update_listing_quantity(
        self,
        conn: psycopg.Connection,
        *,
        tenant_id: str,
        listing: ListingRow,
        desired_qty: int,
        idempotency_key: str,
        reason: str,
        context: dict[str, object],
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ebay_listing_updates (
                  tenant_id, ebay_listing_id, ebay_item_id, update_type, idempotency_key,
                  old_qty, new_qty, reason, context
                )
                VALUES (
                  %(tenant_id)s, %(ebay_listing_id)s, %(ebay_item_id)s, 'quantity',
                  %(idempotency_key)s,
                  %(old_qty)s, %(new_qty)s, %(reason)s, %(context)s::jsonb
                )
                ON CONFLICT (tenant_id, idempotency_key)
                DO NOTHING
                """,
                {
                    "tenant_id": tenant_id,
                    "ebay_listing_id": listing.ebay_listing_id,
                    "ebay_item_id": listing.ebay_item_id,
                    "idempotency_key": idempotency_key,
                    "old_qty": int(listing.current_qty),
                    "new_qty": int(desired_qty),
                    "reason": reason,
                    "context": json.dumps(context),
                },
            )

            cur.execute(
                """
                UPDATE ebay_listings
                SET quantity=%(new_qty)s, last_synced_at=now(), updated_at=now()
                WHERE tenant_id=%(tenant_id)s AND id=%(ebay_listing_id)s
                """,
                {
                    "tenant_id": tenant_id,
                    "ebay_listing_id": listing.ebay_listing_id,
                    "new_qty": int(desired_qty),
                },
            )

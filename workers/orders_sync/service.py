from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import psycopg

from common.db import connect
from common.ebay_oauth import get_user_access_token
from orders_sync.fulfillment_client import iter_get_orders
from orders_sync.fulfillment_map import last_modified_filter_since, map_fulfillment_order
from orders_sync.logic import compute_net_profit_usd_baseline
from orders_sync.repository import OrdersSyncRepository, OrderUpsertRow

SOURCE_EBAY_FULFILLMENT = "ebay_fulfillment"


class OrdersSyncService:
    def __init__(self) -> None:
        self._repo = OrdersSyncRepository()

    def run(
        self,
        *,
        tenant_id: str,
        event: dict[str, object],
        idempotency_key: str | None,
        max_items: int = 500,
    ) -> dict[str, object]:
        with connect() as conn:
            job_run_id = self._repo.create_job_run(
                conn,
                tenant_id=tenant_id,
                job_type="orders-sync",
                idempotency_key=idempotency_key,
            )
            try:
                raw_source = event.get("source")
                use_ebay = str(raw_source or "").strip().lower() == SOURCE_EBAY_FULFILLMENT

                if use_ebay:
                    payload = self._sync_from_ebay_fulfillment(
                        conn, tenant_id=tenant_id, event=event, max_orders=max_items
                    )
                else:
                    payload = self._sync_from_event_items(
                        event=event, conn=conn, tenant_id=tenant_id, max_items=max_items
                    )

                self._repo.finish_job_run(
                    conn,
                    job_run_id=job_run_id,
                    status="succeeded",
                    error_message=None,
                )
                conn.commit()
                return {
                    "ok": True,
                    "job_type": "orders-sync",
                    "job_run_id": job_run_id,
                    **payload,
                }
            except Exception as exc:  # noqa: BLE001
                self._repo.finish_job_run(
                    conn,
                    job_run_id=job_run_id,
                    status="failed",
                    error_message=str(exc),
                )
                conn.commit()
                raise

    def _sync_from_event_items(
        self,
        *,
        event: dict[str, object],
        conn: psycopg.Connection,
        tenant_id: str,
        max_items: int,
    ) -> dict[str, object]:
        raw_items = event.get("items")
        items = raw_items if isinstance(raw_items, list) else []
        imported = 0
        skipped = 0
        for item in items[:max_items]:
            if not isinstance(item, dict):
                skipped += 1
                continue
            parsed = _parse_order_item(dict(item))
            if parsed is None:
                skipped += 1
                continue
            self._repo.upsert_order(conn, tenant_id=tenant_id, row=parsed)
            imported += 1
        return {
            "imported_orders": imported,
            "skipped_items": skipped,
            "from_event_items": True,
            "ebay_fulfillment_sync": False,
        }

    def _sync_from_ebay_fulfillment(
        self,
        conn: psycopg.Connection,
        *,
        tenant_id: str,
        event: dict[str, object],
        max_orders: int,
    ) -> dict[str, object]:
        token = get_user_access_token(conn, tenant_id=tenant_id)
        hours_raw = event.get("hours_back")
        if hours_raw is not None:
            hours_back = int(hours_raw)
        else:
            hours_back = int(os.environ.get("ORDERS_EBAY_SYNC_HOURS_BACK", "720"))
        page_limit_raw = event.get("page_limit")
        if page_limit_raw is not None:
            page_limit = int(page_limit_raw)
        else:
            page_limit = int(os.environ.get("ORDERS_EBAY_PAGE_LIMIT", "50"))

        if hours_back <= 0:
            filter_expr = None
        else:
            filter_expr = last_modified_filter_since(hours_back=hours_back)
        orders = iter_get_orders(
            token,
            filter_expr=filter_expr,
            page_limit=page_limit,
            max_orders=max_orders,
        )
        imported = 0
        skipped = 0
        for order in orders:
            if not isinstance(order, dict):
                skipped += 1
                continue
            row = map_fulfillment_order(order)
            if row is None:
                skipped += 1
                continue
            self._repo.upsert_order(conn, tenant_id=tenant_id, row=row)
            imported += 1

        return {
            "imported_orders": imported,
            "skipped_items": skipped,
            "from_event_items": False,
            "ebay_fulfillment_sync": True,
            "fetched_orders": len(orders),
            "hours_back": hours_back,
        }


def _parse_order_item(item: dict[str, Any]) -> OrderUpsertRow | None:
    ebay_order_id = item.get("ebay_order_id")
    sold_at_raw = item.get("sold_at")
    sale_raw = item.get("sale_price_usd")
    if not ebay_order_id or not sold_at_raw or sale_raw is None:
        return None

    sold_at = _parse_sold_at(str(sold_at_raw))
    if sold_at.tzinfo is None:
        sold_at = sold_at.replace(tzinfo=UTC)

    sale_price = Decimal(str(sale_raw))
    ship = _optional_decimal(item.get("shipping_paid_usd"))
    tax = _optional_decimal(item.get("tax_paid_usd"))
    fees = _optional_decimal(item.get("ebay_fees_usd"))
    cogs = _optional_decimal(item.get("cogs_usd"))
    net_raw = item.get("net_profit_usd")
    if net_raw is None:
        net_profit = compute_net_profit_usd_baseline(
            sale_price_usd=sale_price,
            ebay_fees_usd=fees,
            cogs_usd=cogs,
            tax_paid_usd=tax,
        )
    else:
        net_profit = Decimal(str(net_raw)).quantize(Decimal("0.01"))

    currency = str(item.get("currency") or "USD")[:3]
    if len(currency) < 3:
        currency = "USD"

    return OrderUpsertRow(
        ebay_order_id=str(ebay_order_id),
        ebay_transaction_id=_optional_str(item.get("ebay_transaction_id")),
        ebay_listing_id=_optional_str(item.get("ebay_listing_id")),
        ebay_item_id=_optional_str(item.get("ebay_item_id")),
        variant_id=_optional_str(item.get("variant_id")),
        sold_at=sold_at,
        sale_price_usd=sale_price.quantize(Decimal("0.01")),
        shipping_paid_usd=None if ship is None else ship.quantize(Decimal("0.01")),
        tax_paid_usd=None if tax is None else tax.quantize(Decimal("0.01")),
        ebay_fees_usd=None if fees is None else fees.quantize(Decimal("0.01")),
        cogs_usd=None if cogs is None else cogs.quantize(Decimal("0.01")),
        net_profit_usd=net_profit,
        currency=currency,
        return_status=_optional_str(item.get("return_status")),
        raw_payload=item,
    )


def _parse_sold_at(value: str) -> datetime:
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    return datetime.fromisoformat(v)


def _optional_decimal(v: object) -> Decimal | None:
    if v is None or v == "":
        return None
    return Decimal(str(v))


def _optional_str(v: object) -> str | None:
    if v is None or v == "":
        return None
    return str(v)

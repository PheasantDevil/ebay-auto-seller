"""Fetch supplier snapshot JSON from sourcing_source_items.source_url."""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

import httpx

from sourcing_scan.adapters.base import SupplierState
from sourcing_scan.repository import SourcingDbItem


def supplier_state_from_http_json(
    *,
    sourcing_source_item_id: str,
    variant_id: str,
    payload: dict[str, Any],
) -> SupplierState | None:
    """Map a JSON object to SupplierState (shared contract for tests and HTTP)."""
    try:
        price = payload.get("item_price_usd")
        stock = payload.get("source_stock_qty")
        if price is None or stock is None:
            return None
        ship = payload.get("estimated_shipping_usd", "0")
        tax = payload.get("estimated_sales_tax_rate_assumed", "0.10")
        return SupplierState(
            sourcing_source_item_id=sourcing_source_item_id,
            variant_id=variant_id,
            item_price_usd=Decimal(str(price)),
            estimated_shipping_usd=Decimal(str(ship)),
            estimated_sales_tax_rate_assumed=Decimal(str(tax)),
            source_stock_qty=int(stock),
            raw_payload=dict(payload),
        )
    except Exception:  # noqa: BLE001
        return None


class HttpJsonSourcingFetcher:
    """GET source_url and parse JSON body into SupplierState."""

    def fetch(self, *, tenant_id: str, row: SourcingDbItem) -> SupplierState | None:
        _ = tenant_id
        if not row.source_url or not row.source_url.startswith(("http://", "https://")):
            return None

        timeout = float(os.environ.get("SOURCING_HTTP_TIMEOUT_SEC", "15"))
        ua = os.environ.get(
            "SOURCING_HTTP_USER_AGENT",
            "ebay-auto-seller-sourcing-scan/1.0",
        )
        with httpx.Client(timeout=timeout) as client:
            res = client.get(row.source_url, headers={"User-Agent": ua})
            res.raise_for_status()
            body = res.json()

        if not isinstance(body, dict):
            return None
        return supplier_state_from_http_json(
            sourcing_source_item_id=row.sourcing_source_item_id,
            variant_id=row.variant_id,
            payload=body,
        )

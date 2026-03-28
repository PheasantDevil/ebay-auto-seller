"""eBay Sell Fulfillment API: paginated getOrders."""

from __future__ import annotations

import os
from typing import Any

import httpx


def fulfillment_orders_base_url() -> str:
    return os.environ.get(
        "EBAY_FULFILLMENT_API_BASE",
        "https://api.ebay.com/sell/fulfillment/v1",
    ).rstrip("/")


def marketplace_id_header() -> str:
    return os.environ.get("EBAY_MARKETPLACE_ID", "EBAY_US")


def iter_get_orders(
    access_token: str,
    *,
    filter_expr: str | None = None,
    page_limit: int = 50,
    max_orders: int = 500,
    timeout_sec: float = 30.0,
) -> list[dict[str, Any]]:
    """Fetch orders until empty page or max_orders reached."""
    base = fulfillment_orders_base_url()
    url = f"{base}/order"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": marketplace_id_header(),
    }
    out: list[dict[str, Any]] = []
    offset = 0
    page_limit = max(1, min(page_limit, 200))

    with httpx.Client(timeout=timeout_sec) as client:
        while len(out) < max_orders:
            take = min(page_limit, max_orders - len(out))
            params: dict[str, str] = {
                "limit": str(take),
                "offset": str(offset),
            }
            if filter_expr:
                params["filter"] = filter_expr
            res = client.get(url, headers=headers, params=params)
            res.raise_for_status()
            body = res.json()
            batch = body.get("orders")
            if not isinstance(batch, list) or not batch:
                break
            out.extend(batch)
            if len(batch) < take:
                break
            offset += len(batch)

    return out[:max_orders]

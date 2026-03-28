"""eBay Sell Inventory API client (quantity updates)."""

from __future__ import annotations

import os
from typing import Any

import httpx


def bulk_update_price_quantity(
    access_token: str,
    *,
    sku: str,
    quantity: int,
    offer_id: str | None = None,
) -> dict[str, Any]:
    """POST /sell/inventory/v1/bulk_update_price_quantity.

    Either updates ship-to-home quantity for *sku*, or *offer_id* availableQuantity
    (offer path requires matching *sku* per eBay docs).
    """
    base = os.environ.get(
        "EBAY_INVENTORY_API_BASE",
        "https://api.ebay.com/sell/inventory/v1",
    ).rstrip("/")
    url = f"{base}/bulk_update_price_quantity"
    marketplace = os.environ.get("EBAY_MARKETPLACE_ID", "EBAY_US")

    if offer_id:
        body: dict[str, Any] = {
            "requests": [
                {
                    "sku": sku,
                    "offers": [
                        {
                            "offerId": offer_id,
                            "availableQuantity": int(quantity),
                        }
                    ],
                }
            ]
        }
    else:
        body = {
            "requests": [
                {
                    "sku": sku,
                    "shipToLocationAvailability": {"quantity": int(quantity)},
                }
            ]
        }

    with httpx.Client(timeout=30.0) as client:
        res = client.post(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-EBAY-C-MARKETPLACE-ID": marketplace,
            },
        )
        res.raise_for_status()
        data = res.json()

    responses = data.get("responses") or []
    if not responses:
        raise RuntimeError("bulk_update_price_quantity: empty responses")

    first = responses[0]
    status = int(first.get("statusCode", 0))
    if status != 200:
        errs = first.get("errors") or []
        msg = errs[0].get("message", str(errs)) if errs else str(first)
        raise RuntimeError(f"eBay inventory update failed ({status}): {msg}")

    return data

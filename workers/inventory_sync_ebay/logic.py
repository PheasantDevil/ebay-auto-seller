from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ListingInventoryInput:
    ebay_listing_id: str
    ebay_item_id: str
    current_qty: int
    desired_qty: int


def needs_update(inp: ListingInventoryInput) -> bool:
    return int(inp.current_qty) != int(inp.desired_qty)


def parse_inventory_policy(policy: dict[str, Any] | None) -> tuple[str | None, str | None]:
    """Read SKU and optional offer id from `ebay_listings.policy` JSON.

    Supported keys: `inventory_item_sku` or `sku`, `offer_id` or `offerId`.
    """
    if not policy:
        return None, None
    raw_sku = policy.get("inventory_item_sku") or policy.get("sku")
    raw_offer = policy.get("offer_id") or policy.get("offerId")

    sku = str(raw_sku).strip() if raw_sku not in (None, "") else None
    offer_id = str(raw_offer).strip() if raw_offer not in (None, "") else None
    return sku, offer_id

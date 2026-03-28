from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ListingInventoryInput:
    ebay_listing_id: str
    ebay_item_id: str
    current_qty: int
    desired_qty: int


def needs_update(inp: ListingInventoryInput) -> bool:
    return int(inp.current_qty) != int(inp.desired_qty)

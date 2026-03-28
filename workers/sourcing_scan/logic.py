from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VariantInventoryInput:
    variant_id: str
    safety_stock_threshold: int
    supplier_stock_qty: int


def compute_on_hand_qty(inp: VariantInventoryInput) -> int:
    """Compute desired on-hand inventory from supplier stock and safety buffer."""
    return max(0, int(inp.supplier_stock_qty) - int(inp.safety_stock_threshold))

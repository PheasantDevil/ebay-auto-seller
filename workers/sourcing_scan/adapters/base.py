from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SupplierState:
    """Normalized supplier snapshot for one sourcing_source_item."""

    sourcing_source_item_id: str
    variant_id: str
    item_price_usd: Decimal
    estimated_shipping_usd: Decimal
    estimated_sales_tax_rate_assumed: Decimal
    source_stock_qty: int
    raw_payload: dict[str, object]


class SourcingAdapter:
    """Adapter interface for supplier snapshot fetching."""

    source_type: str

    def fetch_states(self, *, tenant_id: str, limit: int) -> list[SupplierState]:
        raise NotImplementedError

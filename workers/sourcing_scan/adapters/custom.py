from __future__ import annotations

from decimal import Decimal

from sourcing_scan.adapters.base import SourcingAdapter, SupplierState


class CustomEventAdapter(SourcingAdapter):
    """Adapter that reads supplier snapshots from the Lambda event.

    This baseline adapter enables end-to-end DB persistence without implementing
    site-specific scraping yet.
    """

    source_type = "custom"

    def __init__(self, event: dict[str, object]) -> None:
        self._event = event

    def fetch_states(self, *, tenant_id: str, limit: int) -> list[SupplierState]:
        raw_items = self._event.get("items")
        if not isinstance(raw_items, list):
            return []

        states: list[SupplierState] = []
        for item in raw_items[:limit]:
            if not isinstance(item, dict):
                continue
            try:
                states.append(
                    SupplierState(
                        sourcing_source_item_id=str(item["sourcing_source_item_id"]),
                        variant_id=str(item["variant_id"]),
                        item_price_usd=Decimal(str(item["item_price_usd"])),
                        estimated_shipping_usd=Decimal(str(item["estimated_shipping_usd"])),
                        estimated_sales_tax_rate_assumed=Decimal(
                            str(item.get("estimated_sales_tax_rate_assumed", "0.10"))
                        ),
                        source_stock_qty=int(item["source_stock_qty"]),
                        raw_payload=dict(item),
                    )
                )
            except Exception:  # noqa: BLE001
                continue

        return states

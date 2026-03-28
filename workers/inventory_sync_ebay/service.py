from __future__ import annotations

import os

from common.db import connect
from inventory_sync_ebay.logic import ListingInventoryInput, needs_update
from inventory_sync_ebay.repository import InventorySyncEbayRepository, ListingRow


class InventorySyncEbayService:
    def __init__(self) -> None:
        self._repo = InventorySyncEbayRepository()
        self._max_qty = int(os.environ.get("EBAY_MAX_QTY", "5"))
        self._enabled = os.environ.get("EBAY_INVENTORY_SYNC_ENABLED", "false").lower() == "true"

    def run(
        self,
        *,
        tenant_id: str,
        idempotency_key: str | None,
        dry_run: bool = False,
    ) -> dict[str, object]:
        with connect() as conn:
            job_run_id = self._repo.create_job_run(
                conn,
                tenant_id=tenant_id,
                job_type="inventory-sync-ebay",
                idempotency_key=idempotency_key,
            )
            try:
                listings = self._repo.fetch_active_listings(conn, tenant_id=tenant_id)
                available_by_variant = self._repo.fetch_variant_available_qty(
                    conn, tenant_id=tenant_id
                )

                updated = 0
                for listing in listings:
                    available = int(available_by_variant.get(listing.variant_id, 0))
                    desired_qty = min(self._max_qty, max(0, available))
                    if needs_update(
                        ListingInventoryInput(
                            ebay_listing_id=listing.ebay_listing_id,
                            ebay_item_id=listing.ebay_item_id,
                            current_qty=listing.current_qty,
                            desired_qty=desired_qty,
                        )
                    ):
                        if not dry_run:
                            self._repo.update_listing_quantity(
                                conn,
                                tenant_id=tenant_id,
                                listing=listing,
                                desired_qty=desired_qty,
                                idempotency_key=_build_update_key(
                                    base_key=idempotency_key,
                                    listing=listing,
                                    desired_qty=desired_qty,
                                ),
                                reason="sync_to_inventory_current",
                                context={
                                    "available_qty": available,
                                    "max_qty": self._max_qty,
                                    "enabled": self._enabled,
                                },
                            )
                        updated += 1

                self._repo.finish_job_run(
                    conn,
                    job_run_id=job_run_id,
                    status="succeeded",
                    error_message=None,
                )
                conn.commit()
                return {
                    "ok": True,
                    "job_type": "inventory-sync-ebay",
                    "job_run_id": job_run_id,
                    "dry_run": dry_run,
                    "updated_listings": updated,
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


def _build_update_key(*, base_key: str | None, listing: ListingRow, desired_qty: int) -> str:
    prefix = base_key or "auto"
    return f"{prefix}:qty:{listing.ebay_item_id}:{int(desired_qty)}"

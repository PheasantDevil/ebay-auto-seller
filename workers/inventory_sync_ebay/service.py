from __future__ import annotations

import os

from common.db import connect
from common.ebay_oauth import get_user_access_token
from inventory_sync_ebay.inventory_api import bulk_update_price_quantity
from inventory_sync_ebay.logic import ListingInventoryInput, needs_update, parse_inventory_policy
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

                api_token: str | None = None

                updated = 0
                skipped_no_sku = 0
                api_errors = 0

                for listing in listings:
                    available = int(available_by_variant.get(listing.variant_id, 0))
                    desired_qty = min(self._max_qty, max(0, available))
                    if not needs_update(
                        ListingInventoryInput(
                            ebay_listing_id=listing.ebay_listing_id,
                            ebay_item_id=listing.ebay_item_id,
                            current_qty=listing.current_qty,
                            desired_qty=desired_qty,
                        )
                    ):
                        continue

                    if dry_run:
                        updated += 1
                        continue

                    sku, offer_id = parse_inventory_policy(listing.policy)
                    context: dict[str, object] = {
                        "available_qty": available,
                        "max_qty": self._max_qty,
                        "enabled": self._enabled,
                        "inventory_item_sku": sku,
                        "offer_id": offer_id,
                    }

                    if self._enabled:
                        if not sku:
                            skipped_no_sku += 1
                            continue
                        if api_token is None:
                            api_token = get_user_access_token(conn, tenant_id=tenant_id)
                        try:
                            bulk_update_price_quantity(
                                api_token,
                                sku=sku,
                                quantity=desired_qty,
                                offer_id=offer_id,
                            )
                        except Exception:  # noqa: BLE001
                            api_errors += 1
                            continue

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
                        context=context,
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
                    "skipped_no_inventory_sku": skipped_no_sku,
                    "api_errors": api_errors,
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

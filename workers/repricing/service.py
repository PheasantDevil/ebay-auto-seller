from __future__ import annotations

import os
from decimal import Decimal

from common.db import connect
from repricing.logic import (
    apply_market_cap,
    minimum_list_price_for_target_profit,
    price_needs_update,
)
from repricing.repository import RepricingListingRow, RepricingRepository


class RepricingService:
    def __init__(self) -> None:
        self._repo = RepricingRepository()
        self._cap_to_market = os.environ.get("EBAY_REPRICE_CAP_TO_MARKET", "true").lower() == "true"
        self._min_price = Decimal(os.environ.get("EBAY_REPRICE_MIN_PRICE_USD", "0.01"))

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
                job_type="repricing",
                idempotency_key=idempotency_key,
            )
            try:
                listings = self._repo.fetch_listings_for_repricing(conn, tenant_id=tenant_id)
                updated = 0
                skipped_no_sourcing = 0

                for listing in listings:
                    if listing.item_price_usd is None or listing.estimated_shipping_usd is None:
                        skipped_no_sourcing += 1
                        continue

                    floor_price = minimum_list_price_for_target_profit(
                        item_price_usd=listing.item_price_usd,
                        estimated_shipping_usd=listing.estimated_shipping_usd,
                        ebay_fee_rate=listing.ebay_fee_rate,
                        sales_tax_rate_assumed=listing.sales_tax_rate_assumed,
                        target_profit_usd=listing.target_profit_usd,
                    )
                    if floor_price < self._min_price:
                        floor_price = self._min_price

                    desired = apply_market_cap(
                        floor_price_usd=floor_price,
                        market_avg_usd=listing.market_avg_usd,
                        cap_to_market=self._cap_to_market,
                    )

                    if price_needs_update(current_usd=listing.fixed_price_usd, desired_usd=desired):
                        if not dry_run:
                            self._repo.update_listing_price(
                                conn,
                                tenant_id=tenant_id,
                                listing=listing,
                                new_price_usd=desired,
                                idempotency_key=_build_price_key(
                                    base_key=idempotency_key,
                                    listing=listing,
                                    new_price_usd=desired,
                                ),
                                reason="target_profit_repricing",
                                context={
                                    "floor_price_usd": str(floor_price),
                                    "market_avg_usd": (
                                        str(listing.market_avg_usd)
                                        if listing.market_avg_usd is not None
                                        else None
                                    ),
                                    "cap_to_market": self._cap_to_market,
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
                    "job_type": "repricing",
                    "job_run_id": job_run_id,
                    "dry_run": dry_run,
                    "updated_listings": updated,
                    "skipped_no_sourcing": skipped_no_sourcing,
                    "candidates": len(listings),
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


def _build_price_key(
    *, base_key: str | None, listing: RepricingListingRow, new_price_usd: Decimal
) -> str:
    prefix = base_key or "auto"
    q = new_price_usd.quantize(Decimal("0.01"))
    return f"{prefix}:repricing:{listing.ebay_item_id}:{q}"

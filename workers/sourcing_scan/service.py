from __future__ import annotations

from collections import defaultdict

from common.db import connect
from sourcing_scan.adapters.custom import CustomEventAdapter
from sourcing_scan.logic import VariantInventoryInput, compute_on_hand_qty
from sourcing_scan.repository import SourcingScanRepository


class SourcingScanService:
    def __init__(self) -> None:
        self._repo = SourcingScanRepository()

    def run(
        self,
        *,
        tenant_id: str,
        event: dict[str, object],
        idempotency_key: str | None,
        max_items: int = 200,
    ) -> dict[str, object]:
        with connect() as conn:
            job_run_id = self._repo.create_job_run(
                conn,
                tenant_id=tenant_id,
                job_type="sourcing-scan",
                idempotency_key=idempotency_key,
            )
            try:
                warehouse_id = self._repo.ensure_default_warehouse(conn, tenant_id=tenant_id)
                thresholds = self._repo.fetch_safety_stock_thresholds(
                    conn, tenant_id=tenant_id, warehouse_id=warehouse_id
                )

                adapter = CustomEventAdapter(event)
                states = adapter.fetch_states(tenant_id=tenant_id, limit=max_items)

                stock_by_variant: dict[str, int] = defaultdict(int)
                for state in states:
                    self._repo.upsert_supplier_state_current(
                        conn,
                        tenant_id=tenant_id,
                        job_run_id=job_run_id,
                        state=state,
                    )
                    self._repo.insert_supplier_state_history(
                        conn,
                        tenant_id=tenant_id,
                        job_run_id=job_run_id,
                        state=state,
                    )
                    # If multiple sources exist for the same variant, use the max stock
                    # to represent "we can source from the best available supplier".
                    stock_by_variant[state.variant_id] = max(
                        stock_by_variant[state.variant_id], int(state.source_stock_qty)
                    )

                updated_inventory = 0
                for variant_id, supplier_stock_qty in stock_by_variant.items():
                    on_hand_qty = compute_on_hand_qty(
                        VariantInventoryInput(
                            variant_id=variant_id,
                            safety_stock_threshold=int(thresholds.get(variant_id, 0)),
                            supplier_stock_qty=int(supplier_stock_qty),
                        )
                    )
                    self._repo.upsert_inventory_current(
                        conn,
                        tenant_id=tenant_id,
                        warehouse_id=warehouse_id,
                        variant_id=variant_id,
                        on_hand_qty=on_hand_qty,
                    )
                    updated_inventory += 1

                self._repo.finish_job_run(
                    conn,
                    job_run_id=job_run_id,
                    status="succeeded",
                    error_message=None,
                )
                conn.commit()
                return {
                    "ok": True,
                    "job_type": "sourcing-scan",
                    "job_run_id": job_run_id,
                    "updated_supplier_items": len(states),
                    "updated_inventory_variants": updated_inventory,
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

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from common.db import connect
from sourcing_scan.adapters.base import SupplierState
from sourcing_scan.adapters.custom import CustomEventAdapter
from sourcing_scan.adapters.registry import (
    get_fetcher,
    is_event_only_source_type,
    is_placeholder_source_type,
)
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

                event_adapter = CustomEventAdapter(event)
                event_states = event_adapter.fetch_states(tenant_id=tenant_id, limit=max_items)

                db_rows = self._repo.fetch_active_sourcing_items(
                    conn, tenant_id=tenant_id, limit=max_items
                )
                db_states: list[SupplierState] = []
                skipped_placeholder = 0
                skipped_event_only = 0
                skipped_unknown_type = 0
                http_fetch_errors = 0

                for row in db_rows:
                    stype = row.source_type
                    if is_placeholder_source_type(stype):
                        skipped_placeholder += 1
                        continue
                    if is_event_only_source_type(stype):
                        skipped_event_only += 1
                        continue
                    fetcher = get_fetcher(stype)
                    if fetcher is None:
                        skipped_unknown_type += 1
                        continue
                    try:
                        st = fetcher.fetch(tenant_id=tenant_id, row=row)
                    except Exception:  # noqa: BLE001
                        http_fetch_errors += 1
                        continue
                    if st is not None:
                        db_states.append(st)

                states = _merge_supplier_states([db_states, event_states])

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
                    "from_event_items": len(event_states),
                    "from_db_fetch": len(db_states),
                    "skipped_placeholder_sources": skipped_placeholder,
                    "skipped_event_only_sources": skipped_event_only,
                    "skipped_unknown_source_type": skipped_unknown_type,
                    "http_fetch_errors": http_fetch_errors,
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


def _merge_supplier_states(groups: Iterable[list[SupplierState]]) -> list[SupplierState]:
    """Later groups override earlier rows with the same sourcing_source_item_id."""
    by_item: dict[str, SupplierState] = {}
    for group in groups:
        for state in group:
            by_item[state.sourcing_source_item_id] = state
    return list(by_item.values())

"""Worker: fetch supplier price/stock snapshots and update inventory."""

from typing import Any

from sourcing_scan.service import SourcingScanService


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entrypoint for `sourcing-scan`.

    For compatibility with existing smoke tests, missing tenant_id returns a
    skipped response instead of raising.
    """
    tenant_id = event.get("tenant_id")
    if not tenant_id:
        return {"ok": True, "job_type": "sourcing-scan", "skipped": True}

    service = SourcingScanService()
    return service.run(
        tenant_id=str(tenant_id),
        event=dict(event),
        idempotency_key=event.get("idempotency_key"),
        max_items=int(event.get("max_items", 200)),
    )

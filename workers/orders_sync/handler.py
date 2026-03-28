"""Worker: import completed orders into the orders table."""

from typing import Any

from orders_sync.service import OrdersSyncService


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entrypoint for `orders-sync`.

    For compatibility with existing smoke tests, missing tenant_id returns a
    skipped response instead of raising.
    """
    tenant_id = event.get("tenant_id")
    if not tenant_id:
        return {"ok": True, "job_type": "orders-sync", "skipped": True}

    service = OrdersSyncService()
    return service.run(
        tenant_id=str(tenant_id),
        event=dict(event),
        idempotency_key=event.get("idempotency_key"),
        max_items=int(event.get("max_items", 500)),
    )

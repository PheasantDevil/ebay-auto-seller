"""Worker: import completed orders into the orders table."""

from typing import Any

from orders_sync.service import OrdersSyncService


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entrypoint for `orders-sync`.

    For compatibility with existing smoke tests, missing tenant_id returns a
    skipped response instead of raising.

    Event payload:
    - Default: ``items`` list (manual / bridge) as before.
    - ``source``: ``\"ebay_fulfillment\"`` — fetch via Sell Fulfillment getOrders
      (needs OAuth scope ``sell.fulfillment.readonly`` and tenant tokens).
      Optional: ``hours_back`` (default from env ``ORDERS_EBAY_SYNC_HOURS_BACK``,
      use ``0`` for eBay default window / no lastmodified filter), ``page_limit``.
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

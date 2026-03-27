"""Worker: sync eBay inventory quantity based on inventory_current."""

from typing import Any

from inventory_sync_ebay.service import InventorySyncEbayService


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entrypoint for `inventory-sync-ebay`.

    For compatibility with existing smoke tests, missing tenant_id returns a
    skipped response instead of raising.
    """
    tenant_id = event.get("tenant_id")
    if not tenant_id:
        return {"ok": True, "job_type": "inventory-sync-ebay", "skipped": True}

    service = InventorySyncEbayService()
    return service.run(
        tenant_id=str(tenant_id),
        idempotency_key=event.get("idempotency_key"),
        dry_run=bool(event.get("dry_run", False)),
    )

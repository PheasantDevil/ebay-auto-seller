from typing import Any


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    # Stub worker entrypoint.
    # Next step will sync supplier-out-of-stock states to eBay listing quantity=0.
    return {"ok": True, "job_type": "inventory-sync-ebay"}

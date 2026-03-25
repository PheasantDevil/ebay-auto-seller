"""Worker: sync eBay inventory quantity based on supplier stock (stub)."""

from typing import Any


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entrypoint for `inventory-sync-ebay` (stub)."""
    return {"ok": True, "job_type": "inventory-sync-ebay"}

"""Worker: import completed orders and finalize profit reporting (stub)."""

from typing import Any


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entrypoint for `orders-sync` (stub)."""
    return {"ok": True, "job_type": "orders-sync"}

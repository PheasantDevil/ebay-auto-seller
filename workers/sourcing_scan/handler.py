"""Worker: fetch supplier price/stock snapshots (stub)."""

from typing import Any


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entrypoint for `sourcing-scan` (stub)."""
    return {"ok": True, "job_type": "sourcing-scan"}

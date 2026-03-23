"""Worker: refresh eBay market statistics (stub)."""

from typing import Any


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entrypoint for `market-stats-refresh` (stub)."""
    return {"ok": True, "job_type": "market-stats-refresh"}

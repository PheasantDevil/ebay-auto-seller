"""Worker: compute and apply eBay repricing rules (stub)."""

from typing import Any


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entrypoint for `repricing` (stub)."""
    return {"ok": True, "job_type": "repricing"}

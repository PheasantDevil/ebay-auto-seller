"""Worker: compute and apply eBay repricing rules."""

from typing import Any

from repricing.service import RepricingService


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entrypoint for `repricing`.

    For compatibility with existing smoke tests, missing tenant_id returns a
    skipped response instead of raising.
    """
    tenant_id = event.get("tenant_id")
    if not tenant_id:
        return {"ok": True, "job_type": "repricing", "skipped": True}

    service = RepricingService()
    return service.run(
        tenant_id=str(tenant_id),
        idempotency_key=event.get("idempotency_key"),
        dry_run=bool(event.get("dry_run", False)),
    )

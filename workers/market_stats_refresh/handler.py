"""Worker: refresh eBay market statistics."""

from typing import Any

from market_stats_refresh.service import MarketStatsRefreshService


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entrypoint for `market-stats-refresh`.

    For compatibility with existing smoke tests, missing tenant_id returns a
    skipped response instead of raising.
    """
    tenant_id = event.get("tenant_id")
    if not tenant_id:
        return {"ok": True, "job_type": "market-stats-refresh", "skipped": True}

    service = MarketStatsRefreshService()
    result = service.refresh_market_stats(
        tenant_id=tenant_id,
        variant_limit=int(event.get("variant_limit", 20)),
        idempotency_key=event.get("idempotency_key"),
    )
    return result

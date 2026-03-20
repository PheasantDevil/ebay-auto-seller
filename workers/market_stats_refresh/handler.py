from typing import Any


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    # Stub worker entrypoint.
    # Next step will connect to eBay Browse/Analytics APIs and persist results to Aurora.
    return {"ok": True, "job_type": "market-stats-refresh"}

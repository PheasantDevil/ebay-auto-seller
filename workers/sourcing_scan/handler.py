from typing import Any


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    # Stub worker entrypoint.
    # Next step will fetch supplier price/stock snapshots and write to Aurora.
    return {"ok": True, "job_type": "sourcing-scan"}

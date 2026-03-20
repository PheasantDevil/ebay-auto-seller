from typing import Any


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    # Stub worker entrypoint.
    # Next step will import completed orders and finalize profit reporting.
    return {"ok": True, "job_type": "orders-sync"}

from typing import Any

from inventory_sync_ebay.handler import handler as inventory_sync_ebay
from market_stats_refresh.handler import handler as market_stats_refresh
from orders_sync.handler import handler as orders_sync
from repricing.handler import handler as repricing
from sourcing_scan.handler import handler as sourcing_scan


def _ctx() -> Any:
    """Mocked Lambda context placeholder (stub)."""
    return None


def _event() -> dict[str, Any]:
    """Mocked Lambda event placeholder (stub)."""
    return {}


def test_worker_stubs_smoke():
    """Smoke test that all worker stubs return a success payload."""
    handlers = [
        market_stats_refresh,
        sourcing_scan,
        inventory_sync_ebay,
        repricing,
        orders_sync,
    ]
    for worker_handler in handlers:
        assert worker_handler(_event(), _ctx())["ok"] is True

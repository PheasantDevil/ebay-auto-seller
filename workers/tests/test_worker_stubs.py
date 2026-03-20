from typing import Any

from inventory_sync_ebay.handler import handler as inventory_sync_ebay
from market_stats_refresh.handler import handler as market_stats_refresh
from orders_sync.handler import handler as orders_sync
from repricing.handler import handler as repricing
from sourcing_scan.handler import handler as sourcing_scan


def _ctx() -> Any:
    return None


def _event() -> dict[str, Any]:
    return {}


def test_worker_stubs_smoke():
    assert market_stats_refresh(_event(), _ctx())["ok"] is True
    assert sourcing_scan(_event(), _ctx())["ok"] is True
    assert inventory_sync_ebay(_event(), _ctx())["ok"] is True
    assert repricing(_event(), _ctx())["ok"] is True
    assert orders_sync(_event(), _ctx())["ok"] is True

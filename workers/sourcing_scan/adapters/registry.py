"""Map sourcing_sources.source_type to fetcher implementations."""

from __future__ import annotations

from typing import Protocol

from sourcing_scan.adapters.base import SupplierState
from sourcing_scan.adapters.http_json import HttpJsonSourcingFetcher
from sourcing_scan.adapters.marketplace_fetchers import (
    AmazonSourcingFetcher,
    TargetSourcingFetcher,
    WalmartSourcingFetcher,
)
from sourcing_scan.repository import SourcingDbItem


class SourcingRowFetcher(Protocol):
    def fetch(self, *, tenant_id: str, row: SourcingDbItem) -> SupplierState | None: ...


_PLACEHOLDER_TYPES: frozenset[str] = frozenset()
_EVENT_ONLY_TYPES = frozenset({"custom"})

_FETCHERS: dict[str, SourcingRowFetcher] = {
    "http_json": HttpJsonSourcingFetcher(),
    "amazon": AmazonSourcingFetcher(),
    "walmart": WalmartSourcingFetcher(),
    "target": TargetSourcingFetcher(),
}


def is_placeholder_source_type(source_type: str) -> bool:
    return source_type.lower() in _PLACEHOLDER_TYPES


def is_event_only_source_type(source_type: str) -> bool:
    return source_type.lower() in _EVENT_ONLY_TYPES


def get_fetcher(source_type: str) -> SourcingRowFetcher | None:
    return _FETCHERS.get(source_type.lower())

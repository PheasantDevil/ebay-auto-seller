"""Amazon / Walmart / Target: fetch standard supplier JSON via tenant-configured URLs.

These marketplaces do not expose a single unauthenticated price API suitable for
direct integration here. Adapters call an **HTTPS URL** that returns the same
JSON shape as ``http_json`` (see ``supplier_state_from_http_json``), typically
implemented by the tenant (proxy, internal service, or integration partner).

Configure either ``sourcing_source_items.source_url`` (absolute https) or env
``*_SOURCING_JSON_URL_TEMPLATE`` plus ``external_product_id`` on the row.
"""

from __future__ import annotations

from sourcing_scan.adapters.base import SupplierState
from sourcing_scan.adapters.http_json import fetch_supplier_state_from_get_url
from sourcing_scan.adapters.marketplace_resolve import resolve_marketplace_json_url
from sourcing_scan.repository import SourcingDbItem


class AmazonSourcingFetcher:
    _TEMPLATE_ENV = "AMAZON_SOURCING_JSON_URL_TEMPLATE"

    def fetch(self, *, tenant_id: str, row: SourcingDbItem) -> SupplierState | None:
        _ = tenant_id
        url = resolve_marketplace_json_url(row, template_env=self._TEMPLATE_ENV)
        if not url:
            return None
        return fetch_supplier_state_from_get_url(
            url=url,
            sourcing_source_item_id=row.sourcing_source_item_id,
            variant_id=row.variant_id,
        )


class WalmartSourcingFetcher:
    _TEMPLATE_ENV = "WALMART_SOURCING_JSON_URL_TEMPLATE"

    def fetch(self, *, tenant_id: str, row: SourcingDbItem) -> SupplierState | None:
        _ = tenant_id
        url = resolve_marketplace_json_url(row, template_env=self._TEMPLATE_ENV)
        if not url:
            return None
        return fetch_supplier_state_from_get_url(
            url=url,
            sourcing_source_item_id=row.sourcing_source_item_id,
            variant_id=row.variant_id,
        )


class TargetSourcingFetcher:
    _TEMPLATE_ENV = "TARGET_SOURCING_JSON_URL_TEMPLATE"

    def fetch(self, *, tenant_id: str, row: SourcingDbItem) -> SupplierState | None:
        _ = tenant_id
        url = resolve_marketplace_json_url(row, template_env=self._TEMPLATE_ENV)
        if not url:
            return None
        return fetch_supplier_state_from_get_url(
            url=url,
            sourcing_source_item_id=row.sourcing_source_item_id,
            variant_id=row.variant_id,
        )

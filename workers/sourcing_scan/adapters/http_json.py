"""Fetch supplier snapshot JSON from sourcing_source_items.source_url."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

import httpx

from sourcing_scan.adapters.base import SupplierState
from sourcing_scan.repository import SourcingDbItem


def supplier_state_from_http_json(
    *,
    sourcing_source_item_id: str,
    variant_id: str,
    payload: dict[str, Any],
) -> SupplierState | None:
    """Map a JSON object to SupplierState (shared contract for tests and HTTP)."""
    try:
        price = payload.get("item_price_usd")
        stock = payload.get("source_stock_qty")
        if price is None or stock is None:
            return None
        ship = payload.get("estimated_shipping_usd", "0")
        tax = payload.get("estimated_sales_tax_rate_assumed", "0.10")
        return SupplierState(
            sourcing_source_item_id=sourcing_source_item_id,
            variant_id=variant_id,
            item_price_usd=Decimal(str(price)),
            estimated_shipping_usd=Decimal(str(ship)),
            estimated_sales_tax_rate_assumed=Decimal(str(tax)),
            source_stock_qty=int(stock),
            raw_payload=dict(payload),
        )
    except Exception:  # noqa: BLE001
        return None


def _allowed_hosts_from_env() -> frozenset[str] | None:
    raw = os.environ.get("SOURCING_HTTP_ALLOWED_HOSTS", "").strip()
    if not raw:
        return None
    parts = {h.strip().lower() for h in raw.split(",") if h.strip()}
    return frozenset(parts) if parts else None


def _resolved_endpoint_ips(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        addr = ipaddress.ip_address(hostname)
        return [addr]
    except ValueError:
        pass
    infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    out: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        ip_str = info[4][0]
        out.append(ipaddress.ip_address(ip_str))
    return out


def is_safe_sourcing_http_url(url: str) -> bool:
    """Reject SSRF-prone targets (non-public IPs) unless allowlisted by host name."""
    if not url.startswith(("http://", "https://")):
        return False
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return False

    allow = _allowed_hosts_from_env()
    host_l = host.lower()
    if allow is not None and host_l not in allow:
        return False

    try:
        ips = _resolved_endpoint_ips(host)
    except OSError:
        return False
    if not ips:
        return False
    return all(ip.is_global for ip in ips)


def _extra_headers_from_env() -> dict[str, str]:
    """Optional JSON object of string header names to values (e.g. ``Authorization``)."""
    raw = os.environ.get("SOURCING_HTTP_EXTRA_HEADERS_JSON", "").strip()
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(obj, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in obj.items():
        if isinstance(k, str) and isinstance(v, str):
            out[k] = v
    return out


def _request_headers_for_sourcing_get() -> dict[str, str]:
    ua = os.environ.get(
        "SOURCING_HTTP_USER_AGENT",
        "ebay-auto-seller-sourcing-scan/1.0",
    )
    merged: dict[str, str] = {"User-Agent": ua}
    merged.update(_extra_headers_from_env())
    return merged


def fetch_supplier_state_from_get_url(
    *,
    url: str,
    sourcing_source_item_id: str,
    variant_id: str,
) -> SupplierState | None:
    """GET JSON from url (after SSRF checks); same body contract as ``http_json``."""
    if not url or not is_safe_sourcing_http_url(url):
        return None

    timeout = float(os.environ.get("SOURCING_HTTP_TIMEOUT_SEC", "15"))
    headers = _request_headers_for_sourcing_get()
    with httpx.Client(timeout=timeout) as client:
        res = client.get(url, headers=headers)
        res.raise_for_status()
        body = res.json()

    if not isinstance(body, dict):
        return None
    return supplier_state_from_http_json(
        sourcing_source_item_id=sourcing_source_item_id,
        variant_id=variant_id,
        payload=body,
    )


class HttpJsonSourcingFetcher:
    """GET source_url and parse JSON body into SupplierState."""

    def fetch(self, *, tenant_id: str, row: SourcingDbItem) -> SupplierState | None:
        _ = tenant_id
        return fetch_supplier_state_from_get_url(
            url=row.source_url,
            sourcing_source_item_id=row.sourcing_source_item_id,
            variant_id=row.variant_id,
        )

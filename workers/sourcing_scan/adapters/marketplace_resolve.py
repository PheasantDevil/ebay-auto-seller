"""Resolve effective HTTP URL for marketplace sourcing rows (tenant proxy pattern)."""

from __future__ import annotations

import os

from sourcing_scan.repository import SourcingDbItem


def resolve_marketplace_json_url(row: SourcingDbItem, *, template_env: str) -> str | None:
    """Prefer ``source_url`` when it is absolute http(s); else optional env URL template.

    Template may use ``{product_id}`` or ``{external_product_id}`` placeholders.
    """
    raw = (row.source_url or "").strip()
    if raw.startswith(("http://", "https://")):
        return raw

    tmpl = os.environ.get(template_env, "").strip()
    ext = (row.external_product_id or "").strip()
    if not tmpl or not ext:
        return None
    return tmpl.format(product_id=ext, external_product_id=ext)

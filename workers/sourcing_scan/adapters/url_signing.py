"""Optional HMAC-SHA256 query signing for sourcing GET URLs (proxy authentication)."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_TS = "sourcing_ts"
_SIG = "sourcing_sig"


def is_sourcing_url_signing_enabled() -> bool:
    return os.environ.get("SOURCING_HTTP_SIGNING_ENABLED", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def apply_sourcing_url_hmac(url: str, *, now_ts: int | None = None) -> str:
    """Append ``sourcing_ts`` (unix seconds) and ``sourcing_sig`` (hex HMAC-SHA256).

    Message: ``{canonical_url_without_sig_params}\\n{ts}`` where canonical URL is
    ``scheme://netloc/path`` plus sorted query (excluding ``sourcing_ts`` /
    ``sourcing_sig``). Proxy must use the same canonicalization and secret.
    """
    secret = os.environ.get("SOURCING_HTTP_SIGNING_SECRET", "").strip()
    if not secret or not is_sourcing_url_signing_enabled():
        return url

    parsed = urlparse(url)
    t = int(time.time() if now_ts is None else now_ts)
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    filtered = [(k, v) for k, v in pairs if k not in (_TS, _SIG)]
    filtered.sort(key=lambda x: (x[0], x[1]))
    q_clean = urlencode(filtered)
    path = parsed.path or "/"
    base = f"{parsed.scheme}://{parsed.netloc}{path}"
    signee = f"{base}?{q_clean}" if q_clean else base
    msg = f"{signee}\n{t}".encode()
    digest = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    final_pairs = sorted(
        filtered + [(_SIG, digest), (_TS, str(t))],
        key=lambda x: (x[0], x[1]),
    )
    new_query = urlencode(final_pairs)
    return urlunparse(
        (parsed.scheme, parsed.netloc, path, parsed.params, new_query, parsed.fragment)
    )

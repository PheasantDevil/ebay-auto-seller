"""Decrypt / refresh eBay user OAuth tokens stored in ebay_oauth_tokens."""

from __future__ import annotations

import base64
import os
from datetime import UTC, datetime, timedelta

import httpx
import psycopg


def get_user_access_token(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    oauth_scope: str | None = None,
) -> str:
    """Return a valid access token for the tenant, refreshing when near expiry."""
    enc_key = _require_env("EBAY_TOKEN_ENCRYPTION_KEY")
    client_id = _require_env("EBAY_CLIENT_ID")
    client_secret = _require_env("EBAY_CLIENT_SECRET")
    scope = oauth_scope or os.environ.get(
        "EBAY_SCOPE",
        (
            "https://api.ebay.com/oauth/api_scope "
            "https://api.ebay.com/oauth/api_scope/buy.marketplace.insights "
            "https://api.ebay.com/oauth/api_scope/sell.inventory"
        ),
    )
    token_url = os.environ.get(
        "EBAY_OAUTH_TOKEN_URL",
        "https://api.ebay.com/identity/v1/oauth2/token",
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              pgp_sym_decrypt(access_token_enc, %(enc_key)s)::text AS access_token,
              pgp_sym_decrypt(refresh_token_enc, %(enc_key)s)::text AS refresh_token,
              expires_at
            FROM ebay_oauth_tokens
            WHERE tenant_id = %(tenant_id)s
            """,
            {"tenant_id": tenant_id, "enc_key": enc_key},
        )
        row = cur.fetchone()
    if not row:
        raise RuntimeError("No eBay OAuth token found for tenant.")
    access_token, refresh_token, expires_at = row
    if expires_at and expires_at > datetime.now(UTC) + timedelta(seconds=60):
        return access_token
    if not refresh_token:
        raise RuntimeError("Refresh token is missing.")

    refreshed = _refresh_token(
        token_url=token_url,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        scope=scope,
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ebay_oauth_tokens
            SET
              access_token_enc = pgp_sym_encrypt(%(access_token)s, %(enc_key)s),
              refresh_token_enc = pgp_sym_encrypt(%(refresh_token)s, %(enc_key)s),
              expires_at = %(expires_at)s,
              token_type = %(token_type)s,
              scope = %(scope)s,
              updated_at = now()
            WHERE tenant_id = %(tenant_id)s
            """,
            {
                "tenant_id": tenant_id,
                "enc_key": enc_key,
                "access_token": refreshed["access_token"],
                "refresh_token": refreshed["refresh_token"],
                "expires_at": refreshed["expires_at"],
                "token_type": refreshed["token_type"],
                "scope": refreshed["scope"],
            },
        )
    return refreshed["access_token"]


def _refresh_token(
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    scope: str,
) -> dict[str, object]:
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode("ascii")
    with httpx.Client(timeout=30.0) as client:
        res = client.post(
            token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": scope,
            },
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        res.raise_for_status()
        body = res.json()

    expires_in = int(body.get("expires_in", 7200))
    return {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token", refresh_token),
        "token_type": body.get("token_type", "Bearer"),
        "scope": body.get("scope", ""),
        "expires_at": datetime.now(UTC) + timedelta(seconds=expires_in),
    }


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set.")
    return value

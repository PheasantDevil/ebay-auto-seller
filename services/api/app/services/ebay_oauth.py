"""Utilities for eBay OAuth flow and token persistence."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
import psycopg


@dataclass(frozen=True)
class EbayTokenPayload:
    """Normalized token payload returned from eBay OAuth token API."""

    access_token: str
    refresh_token: str
    token_type: str
    scope: str
    expires_at: datetime


def build_ebay_auth_url(*, tenant_id: str, state: str | None = None) -> str:
    """Build eBay OAuth authorization URL for user consent flow."""
    client_id = _require_env("EBAY_CLIENT_ID")
    redirect_uri = _require_env("EBAY_REDIRECT_URI")
    scope = os.environ.get(
        "EBAY_SCOPE",
        "https://api.ebay.com/oauth/api_scope https://api.ebay.com/oauth/api_scope/buy.marketplace.insights",
    )
    oauth_base = os.environ.get("EBAY_OAUTH_BASE_URL", "https://auth.ebay.com/oauth2/authorize")

    query_state = state or tenant_id
    query = urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": query_state,
            "prompt": "login",
        }
    )
    return f"{oauth_base}?{query}"


def exchange_code_for_tokens(*, code: str) -> EbayTokenPayload:
    """Exchange authorization code for OAuth tokens via eBay Identity API."""
    client_id = _require_env("EBAY_CLIENT_ID")
    client_secret = _require_env("EBAY_CLIENT_SECRET")
    redirect_uri = _require_env("EBAY_REDIRECT_URI")
    token_url = os.environ.get(
        "EBAY_OAUTH_TOKEN_URL", "https://api.ebay.com/identity/v1/oauth2/token"
    )

    auth_raw = f"{client_id}:{client_secret}".encode()
    basic_auth = base64.b64encode(auth_raw).decode("ascii")

    with httpx.Client(timeout=30.0) as client:
        res = client.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={
                "Authorization": f"Basic {basic_auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        res.raise_for_status()
        body = res.json()

    expires_in = int(body.get("expires_in", 7200))
    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    return EbayTokenPayload(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token", ""),
        token_type=body.get("token_type", "Bearer"),
        scope=body.get("scope", ""),
        expires_at=expires_at,
    )


def save_tokens_for_tenant(*, tenant_id: str, token: EbayTokenPayload) -> None:
    """Encrypt and persist eBay OAuth tokens for a tenant."""
    database_url = _require_env("DATABASE_URL")
    enc_key = _require_env("EBAY_TOKEN_ENCRYPTION_KEY")

    sql = """
    INSERT INTO ebay_oauth_tokens (
      tenant_id,
      access_token_enc,
      refresh_token_enc,
      token_type,
      scope,
      expires_at
    )
    VALUES (
      %(tenant_id)s,
      pgp_sym_encrypt(%(access_token)s, %(enc_key)s),
      pgp_sym_encrypt(%(refresh_token)s, %(enc_key)s),
      %(token_type)s,
      %(scope)s,
      %(expires_at)s
    )
    ON CONFLICT (tenant_id)
    DO UPDATE SET
      access_token_enc = EXCLUDED.access_token_enc,
      refresh_token_enc = EXCLUDED.refresh_token_enc,
      token_type = EXCLUDED.token_type,
      scope = EXCLUDED.scope,
      expires_at = EXCLUDED.expires_at,
      updated_at = now()
    """

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "tenant_id": tenant_id,
                    "access_token": token.access_token,
                    "refresh_token": token.refresh_token,
                    "token_type": token.token_type,
                    "scope": token.scope,
                    "expires_at": token.expires_at,
                    "enc_key": enc_key,
                },
            )
        conn.commit()


def _require_env(name: str) -> str:
    """Read required environment variable and raise descriptive error when missing."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set.")
    return value

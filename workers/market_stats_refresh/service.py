"""Service layer for market stats refresh worker."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import psycopg

from market_stats_refresh.logic import summarize_prices


@dataclass(frozen=True)
class VariantSeed:
    """Minimal variant data required to query eBay market listings."""

    variant_id: str
    product_title: str
    condition: str


class MarketStatsRefreshService:
    """Orchestrates token handling, eBay query, and market_stats persistence."""

    def __init__(self) -> None:
        self.database_url = _require_env("DATABASE_URL")
        self.enc_key = _require_env("EBAY_TOKEN_ENCRYPTION_KEY")
        self.client_id = _require_env("EBAY_CLIENT_ID")
        self.client_secret = _require_env("EBAY_CLIENT_SECRET")
        self.token_url = os.environ.get(
            "EBAY_OAUTH_TOKEN_URL",
            "https://api.ebay.com/identity/v1/oauth2/token",
        )
        self.browse_search_url = os.environ.get(
            "EBAY_BROWSE_SEARCH_URL",
            "https://api.ebay.com/buy/browse/v1/item_summary/search",
        )

    def refresh_market_stats(
        self,
        *,
        tenant_id: str,
        variant_limit: int = 20,
        idempotency_key: str | None = None,
    ) -> dict[str, object]:
        """Refresh market stats for a tenant and store results."""
        with psycopg.connect(self.database_url) as conn:
            job_run_id = self._create_job_run(
                conn,
                tenant_id=tenant_id,
                job_type="market-stats-refresh",
                idempotency_key=idempotency_key,
            )
            try:
                access_token = self._get_or_refresh_access_token(conn, tenant_id=tenant_id)
                variants = self._fetch_variant_seeds(
                    conn,
                    tenant_id=tenant_id,
                    limit=variant_limit,
                )
                inserted = 0
                for variant in variants:
                    stats = self._query_market_stats(
                        access_token=access_token,
                        query=variant.product_title,
                    )
                    self._insert_market_stat(
                        conn,
                        tenant_id=tenant_id,
                        variant_id=variant.variant_id,
                        condition=variant.condition,
                        avg_sold_price_usd=stats["avg_price_usd"],
                        sold_count=stats["count"],
                        confidence=stats["confidence"],
                        raw_payload=stats["raw_payload"],
                    )
                    inserted += 1
                self._finish_job_run(
                    conn,
                    job_run_id=job_run_id,
                    status="succeeded",
                    error_message=None,
                )
                conn.commit()
                return {
                    "ok": True,
                    "job_type": "market-stats-refresh",
                    "updated_variants": inserted,
                }
            except Exception as exc:  # noqa: BLE001
                self._finish_job_run(
                    conn,
                    job_run_id=job_run_id,
                    status="failed",
                    error_message=str(exc),
                )
                conn.commit()
                raise

    def _create_job_run(
        self,
        conn: psycopg.Connection,
        *,
        tenant_id: str,
        job_type: str,
        idempotency_key: str | None,
    ) -> str:
        """Insert running job row and return id."""
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO job_runs (tenant_id, job_type, idempotency_key, status, started_at)
                VALUES (%(tenant_id)s, %(job_type)s, %(idempotency_key)s, 'running', now())
                RETURNING id::text
                """,
                {
                    "tenant_id": tenant_id,
                    "job_type": job_type,
                    "idempotency_key": idempotency_key,
                },
            )
            return cur.fetchone()[0]

    def _finish_job_run(
        self,
        conn: psycopg.Connection,
        *,
        job_run_id: str,
        status: str,
        error_message: str | None,
    ) -> None:
        """Finalize job run state."""
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE job_runs
                SET status = %(status)s, finished_at = now(), error_message = %(error_message)s
                WHERE id = %(job_run_id)s
                """,
                {
                    "status": status,
                    "error_message": error_message,
                    "job_run_id": job_run_id,
                },
            )

    def _fetch_variant_seeds(
        self,
        conn: psycopg.Connection,
        *,
        tenant_id: str,
        limit: int,
    ) -> list[VariantSeed]:
        """Fetch variant seeds for market queries."""
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  pv.id::text AS variant_id,
                  p.title AS product_title,
                  'unknown'::text AS condition
                FROM product_variants pv
                JOIN products p ON p.id = pv.product_id AND p.tenant_id = pv.tenant_id
                WHERE pv.tenant_id = %(tenant_id)s
                ORDER BY pv.created_at DESC
                LIMIT %(limit)s
                """,
                {"tenant_id": tenant_id, "limit": limit},
            )
            rows = cur.fetchall()
        return [
            VariantSeed(variant_id=row[0], product_title=row[1], condition=row[2]) for row in rows
        ]

    def _get_or_refresh_access_token(self, conn: psycopg.Connection, *, tenant_id: str) -> str:
        """Fetch decrypted access token, refreshing if expired."""
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
                {"tenant_id": tenant_id, "enc_key": self.enc_key},
            )
            row = cur.fetchone()
        if not row:
            raise RuntimeError("No eBay OAuth token found for tenant.")
        access_token, refresh_token, expires_at = row
        if expires_at and expires_at > datetime.now(UTC) + timedelta(seconds=60):
            return access_token
        if not refresh_token:
            raise RuntimeError("Refresh token is missing.")

        refreshed = self._refresh_token(refresh_token=refresh_token)
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
                    "enc_key": self.enc_key,
                    "access_token": refreshed["access_token"],
                    "refresh_token": refreshed["refresh_token"],
                    "expires_at": refreshed["expires_at"],
                    "token_type": refreshed["token_type"],
                    "scope": refreshed["scope"],
                },
            )
        return refreshed["access_token"]

    def _refresh_token(self, *, refresh_token: str) -> dict[str, object]:
        """Call eBay token endpoint for refresh flow."""
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode("ascii")
        with httpx.Client(timeout=30.0) as client:
            res = client.post(
                self.token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "scope": os.environ.get(
                        "EBAY_SCOPE",
                        "https://api.ebay.com/oauth/api_scope https://api.ebay.com/oauth/api_scope/buy.marketplace.insights",
                    ),
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

    def _query_market_stats(self, *, access_token: str, query: str) -> dict[str, object]:
        """Query eBay Browse API and summarize listing prices.

        Note: Browse API does not expose sold history directly in this baseline.
        We use current listing prices as a market proxy for now.
        """
        with httpx.Client(timeout=30.0) as client:
            res = client.get(
                self.browse_search_url,
                params={"q": query, "limit": 20},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            res.raise_for_status()
            body = res.json()

        prices: list[Decimal] = []
        for item in body.get("itemSummaries", []):
            value = item.get("price", {}).get("value")
            if value is None:
                continue
            prices.append(Decimal(str(value)))

        avg_price, count = summarize_prices(prices)
        return {
            "avg_price_usd": avg_price,
            "count": count,
            "confidence": Decimal("0.5000"),
            "raw_payload": body,
        }

    def _insert_market_stat(
        self,
        conn: psycopg.Connection,
        *,
        tenant_id: str,
        variant_id: str,
        condition: str,
        avg_sold_price_usd: Decimal,
        sold_count: int,
        confidence: Decimal,
        raw_payload: dict[str, object],
    ) -> None:
        """Insert a market_stats history row."""
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO market_stats (
                  tenant_id, variant_id, condition, category_match_confidence,
                  avg_sold_price_usd, sold_count, retrieved_at, raw_payload
                )
                VALUES (
                  %(tenant_id)s, %(variant_id)s, %(condition)s, %(confidence)s,
                  %(avg_price)s, %(sold_count)s, now(), %(raw_payload)s::jsonb
                )
                """,
                {
                    "tenant_id": tenant_id,
                    "variant_id": variant_id,
                    "condition": condition,
                    "confidence": confidence,
                    "avg_price": avg_sold_price_usd,
                    "sold_count": sold_count,
                    "raw_payload": json.dumps(raw_payload),
                },
            )


def _require_env(name: str) -> str:
    """Read required environment variable and raise descriptive error when missing."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set.")
    return value

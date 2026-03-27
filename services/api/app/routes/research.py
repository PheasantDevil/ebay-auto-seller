from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from app.domain.pricing import calculate_profit_usd
from app.repositories.research_repo import ResearchRepository, ResearchRow


class ResearchCandidate(BaseModel):
    """API response model for one best candidate per variant."""

    variant_id: str
    variant_name: str
    product_title: str
    avg_sold_price_usd: float
    item_price_usd: float
    estimated_shipping_usd: float
    ebay_fee_usd: float
    sales_tax_usd: float
    net_profit_usd: float


class ResearchCandidatesResponse(BaseModel):
    """API response model for research candidates."""

    candidates: list[ResearchCandidate]


@dataclass(frozen=True)
class CandidateInput:
    """Internal representation for candidate profit calculation."""

    row: ResearchRow


def select_best_candidate(rows: list[ResearchRow]) -> list[ResearchRow]:
    """Select the best (max net profit) row per variant."""

    best_by_variant: dict[str, ResearchRow] = {}
    best_profit_by_variant: dict[str, Decimal] = {}

    for row in rows:
        components = calculate_profit_usd(
            avg_sold_price_usd=row.avg_sold_price_usd,
            item_price_usd=row.item_price_usd,
            estimated_shipping_usd=row.estimated_shipping_usd,
            ebay_fee_rate=row.ebay_fee_rate,
            sales_tax_rate_assumed=row.sales_tax_rate_assumed,
        )
        net_profit = components["net_profit_usd"]

        if (
            row.variant_id not in best_profit_by_variant
            or net_profit > best_profit_by_variant[row.variant_id]
        ):
            best_by_variant[row.variant_id] = row
            best_profit_by_variant[row.variant_id] = net_profit

    # Apply rule A: if profit cannot be positive, exclude from the list.
    # (We already exclude rows without required data by inner joins in SQL.)
    selected: list[ResearchRow] = []
    for row in best_by_variant.values():
        components = calculate_profit_usd(
            avg_sold_price_usd=row.avg_sold_price_usd,
            item_price_usd=row.item_price_usd,
            estimated_shipping_usd=row.estimated_shipping_usd,
            ebay_fee_rate=row.ebay_fee_rate,
            sales_tax_rate_assumed=row.sales_tax_rate_assumed,
        )
        if components["net_profit_usd"] > Decimal("0"):
            selected.append(row)

    selected.sort(key=lambda r: r.variant_id)
    return selected


def get_research_repository() -> ResearchRepository:
    """Create repository using environment configuration.

    This repository is used in production. In tests, override this dependency
    to avoid requiring a live database.
    """

    import os

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set.")
    return ResearchRepository(database_url=database_url)


RESEARCH_REPOSITORY_DEP = Depends(get_research_repository)


router = APIRouter(prefix="/research", tags=["research"])


@router.get("/candidates", response_model=ResearchCandidatesResponse)
def get_research_candidates(
    tenant_id: str = Query(..., description="Tenant id (UUID)."),
    limit: int = Query(50, ge=1, le=500, description="Max number of candidates to return."),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    repo: ResearchRepository = RESEARCH_REPOSITORY_DEP,
) -> ResearchCandidatesResponse:
    """Return best profit-positive candidates for the given tenant."""

    if x_tenant_id is not None and x_tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="tenant_id mismatch.")

    # Cap DB rows returned to avoid unbounded fetch.
    fetch_limit = min(2000, max(100, limit * 20))
    rows = repo.fetch_research_rows(tenant_id=tenant_id, limit_variants=fetch_limit)
    selected_rows = select_best_candidate(rows)

    candidates: list[ResearchCandidate] = []
    for row in selected_rows:
        components = calculate_profit_usd(
            avg_sold_price_usd=row.avg_sold_price_usd,
            item_price_usd=row.item_price_usd,
            estimated_shipping_usd=row.estimated_shipping_usd,
            ebay_fee_rate=row.ebay_fee_rate,
            sales_tax_rate_assumed=row.sales_tax_rate_assumed,
        )

        candidates.append(
            ResearchCandidate(
                variant_id=row.variant_id,
                variant_name=row.variant_name,
                product_title=row.product_title,
                avg_sold_price_usd=float(row.avg_sold_price_usd),
                item_price_usd=float(row.item_price_usd),
                estimated_shipping_usd=float(row.estimated_shipping_usd),
                ebay_fee_usd=float(components["ebay_fee_usd"]),
                sales_tax_usd=float(components["sales_tax_usd"]),
                net_profit_usd=float(components["net_profit_usd"]),
            )
        )

    # Sort by net_profit desc and apply pagination.
    candidates.sort(key=lambda c: c.net_profit_usd, reverse=True)
    return ResearchCandidatesResponse(candidates=candidates[:limit])

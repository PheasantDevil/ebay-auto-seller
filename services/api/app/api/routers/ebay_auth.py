"""Routes for eBay OAuth consent and callback."""

from fastapi import APIRouter, HTTPException, Query

from app.services.ebay_oauth import (
    build_ebay_auth_url,
    exchange_code_for_tokens,
    save_tokens_for_tenant,
)

router = APIRouter(prefix="/auth/ebay", tags=["auth"])


@router.get("/start")
def start_ebay_auth(
    tenant_id: str = Query(..., description="Tenant id (UUID)."),
) -> dict[str, str]:
    """Return eBay consent URL to start OAuth flow."""
    try:
        url = build_ebay_auth_url(tenant_id=tenant_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"authorization_url": url}


@router.get("/callback")
def ebay_auth_callback(
    tenant_id: str = Query(..., description="Tenant id (UUID)."),
    code: str = Query(..., description="OAuth authorization code."),
) -> dict[str, str]:
    """Handle eBay OAuth callback and persist encrypted tokens."""
    try:
        token = exchange_code_for_tokens(code=code)
        save_tokens_for_tenant(tenant_id=tenant_id, token=token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"OAuth callback failed: {exc}") from exc
    return {"status": "ok"}

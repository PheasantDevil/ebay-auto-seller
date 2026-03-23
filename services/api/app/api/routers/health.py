"""Health check router for the eBay Auto Seller API."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Return a simple liveness response for monitoring."""
    return {"status": "ok"}

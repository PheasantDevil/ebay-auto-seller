from fastapi import FastAPI

from app.api.routers.ebay_auth import router as ebay_auth_router
from app.api.routers.health import router as health_router

app = FastAPI(title="eBay Auto Seller API")
app.include_router(health_router)
app.include_router(ebay_auth_router)

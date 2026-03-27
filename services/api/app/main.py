from fastapi import FastAPI

from app.api.routers.health import router as health_router
from app.routes.research import router as research_router

app = FastAPI(title="eBay Auto Seller API")
app.include_router(health_router)
app.include_router(research_router)

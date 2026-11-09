from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import (
    conversations,
    customers,
    dashboard,
    health,
    inventory,
    operations,
    products,
    sales,
    voice,
)
from app.core.config import settings
from app.core.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
)


app.include_router(health.router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")
app.include_router(sales.router, prefix="/api/v1")
app.include_router(customers.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(voice.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(operations.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "message": "VyaparOS API is running.",
    }
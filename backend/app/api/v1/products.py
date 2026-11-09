from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_demo_store_id
from app.core.database import get_db
from app.schemas.product import ProductCreate, ProductDetail, ProductRead
from app.services.product_service import (
    create_store_product,
    get_store_product,
    list_store_products,
)

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=list[ProductRead])
async def get_products(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    active_only: bool = True,
    store_id: UUID = Depends(get_demo_store_id),
    db: AsyncSession = Depends(get_db),
):
    return await list_store_products(
        db, store_id, limit, offset, active_only
    )


@router.get("/{product_id}", response_model=ProductDetail)
async def get_product_by_id(
    product_id: UUID,
    store_id: UUID = Depends(get_demo_store_id),
    db: AsyncSession = Depends(get_db),
):
    return await get_store_product(
        db, store_id, product_id
    )


@router.post(
    "",
    response_model=ProductDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    payload: ProductCreate,
    store_id: UUID = Depends(get_demo_store_id),
    db: AsyncSession = Depends(get_db),
):
    return await create_store_product(
        db, store_id, payload
    )
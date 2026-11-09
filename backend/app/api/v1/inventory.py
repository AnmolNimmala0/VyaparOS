from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_demo_store_id
from app.core.database import get_db
from app.schemas.inventory import (
    InventoryAdjustmentCreate,
    InventoryAdjustmentRead,
    InventoryItemRead,
)
from app.services.inventory_service import (
    adjust_inventory,
    get_store_inventory,
)

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("", response_model=list[InventoryItemRead])
async def get_inventory(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    store_id: UUID = Depends(get_demo_store_id),
    db: AsyncSession = Depends(get_db),
):
    return await get_store_inventory(
        db=db,
        store_id=store_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/low-stock",
    response_model=list[InventoryItemRead],
)
async def get_low_stock(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    store_id: UUID = Depends(get_demo_store_id),
    db: AsyncSession = Depends(get_db),
):
    return await get_store_inventory(
        db=db,
        store_id=store_id,
        limit=limit,
        offset=offset,
        low_stock_only=True,
    )


@router.post(
    "/adjustments",
    response_model=InventoryAdjustmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_inventory_adjustment(
    payload: InventoryAdjustmentCreate,
    store_id: UUID = Depends(get_demo_store_id),
    db: AsyncSession = Depends(get_db),
):
    return await adjust_inventory(
        db=db,
        store_id=store_id,
        payload=payload,
    )
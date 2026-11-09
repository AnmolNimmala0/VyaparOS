from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.inventory_repository import (
    create_inventory_movement,
    ensure_inventory_balance,
    get_product_for_adjustment,
    list_inventory,
)
from app.schemas.inventory import (
    InventoryAdjustmentCreate,
    InventoryAdjustmentRead,
    InventoryItemRead,
)


async def get_store_inventory(
    db: AsyncSession,
    store_id: UUID,
    limit: int,
    offset: int,
    low_stock_only: bool = False,
):
    rows = await list_inventory(
        db=db,
        store_id=store_id,
        limit=limit,
        offset=offset,
        low_stock_only=low_stock_only,
    )

    return [
        InventoryItemRead(
            product_id=row.product_id,
            product_name=row.product_name,
            sku=row.sku,
            unit=row.unit,
            quantity=row.quantity,
            reorder_level=row.reorder_level,
            is_low_stock=row.quantity <= row.reorder_level,
        )
        for row in rows
    ]


async def adjust_inventory_in_transaction(
    db: AsyncSession,
    store_id: UUID,
    payload: InventoryAdjustmentCreate,
    reference_type: str = "MANUAL_ADJUSTMENT",
    reference_id: UUID | None = None,
) -> InventoryAdjustmentRead:
    """
    Adjust inventory without committing or rolling back.
    The caller owns the transaction.
    """
    product = await get_product_for_adjustment(
        db, store_id, payload.product_id
    )

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Active product not found in this store.",
        )

    balance = await ensure_inventory_balance(
        db, store_id, payload.product_id
    )

    previous_quantity = balance.quantity
    new_quantity = previous_quantity + payload.quantity_delta

    if new_quantity < 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Insufficient stock. Current stock is "
                f"{previous_quantity} {product.unit}."
            ),
        )

    balance.quantity = new_quantity

    if payload.reorder_level is not None:
        balance.reorder_level = payload.reorder_level

    movement = await create_inventory_movement(
        db=db,
        store_id=store_id,
        product_id=payload.product_id,
        quantity_delta=payload.quantity_delta,
        note=payload.note,
        reference_type=reference_type,
        reference_id=reference_id,
    )

    return InventoryAdjustmentRead(
        product_id=product.id,
        product_name=product.name,
        previous_quantity=previous_quantity,
        quantity_delta=payload.quantity_delta,
        new_quantity=new_quantity,
        reorder_level=balance.reorder_level,
        movement_id=movement.id,
        movement_type=movement.movement_type,
        note=movement.note,
        created_at=movement.created_at,
    )


async def adjust_inventory(
    db: AsyncSession,
    store_id: UUID,
    payload: InventoryAdjustmentCreate,
):
    try:
        result = await adjust_inventory_in_transaction(
            db=db,
            store_id=store_id,
            payload=payload,
        )

        await db.commit()
        return result

    except HTTPException:
        await db.rollback()
        raise

    except Exception:
        await db.rollback()
        raise
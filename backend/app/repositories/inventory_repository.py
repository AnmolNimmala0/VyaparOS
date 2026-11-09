from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_balance import InventoryBalance
from app.models.inventory_movement import InventoryMovement
from app.models.product import Product


async def list_inventory(
    db: AsyncSession,
    store_id: UUID,
    limit: int = 50,
    offset: int = 0,
    low_stock_only: bool = False,
):
    query = (
        select(
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            Product.sku,
            Product.unit,
            func.coalesce(
                InventoryBalance.quantity, Decimal(0)
            ).label("quantity"),
            func.coalesce(
                InventoryBalance.reorder_level, Decimal(0)
            ).label("reorder_level"),
        )
        .outerjoin(
            InventoryBalance,
            (InventoryBalance.product_id == Product.id)
            & (InventoryBalance.store_id == Product.store_id),
        )
        .where(
            Product.store_id == store_id,
            Product.is_active.is_(True),
        )
    )

    if low_stock_only:
        query = query.where(
            func.coalesce(
                InventoryBalance.quantity, Decimal(0)
            )
            <= func.coalesce(
                InventoryBalance.reorder_level, Decimal(0)
            )
        )

    query = (
        query
        .order_by(Product.name.asc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(query)
    return result.all()


async def get_product_for_adjustment(
    db: AsyncSession,
    store_id: UUID,
    product_id: UUID,
):
    result = await db.execute(
        select(Product).where(
            Product.store_id == store_id,
            Product.id == product_id,
            Product.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def ensure_inventory_balance(
    db: AsyncSession,
    store_id: UUID,
    product_id: UUID,
):
    """
    Create a zero balance if one doesn't exist.
    PostgreSQL handles concurrent inserts through ON CONFLICT.
    """
    statement = (
        insert(InventoryBalance)
        .values(
            store_id=store_id,
            product_id=product_id,
            quantity=Decimal(0),
            reorder_level=Decimal(0),
        )
        .on_conflict_do_nothing(
            constraint="uq_inventory_balance_store_product"
        )
    )

    await db.execute(statement)

    result = await db.execute(
        select(InventoryBalance)
        .where(
            InventoryBalance.store_id == store_id,
            InventoryBalance.product_id == product_id,
        )
        .with_for_update()
    )

    return result.scalar_one()


async def create_inventory_movement(
    db: AsyncSession,
    store_id: UUID,
    product_id: UUID,
    quantity_delta: Decimal,
    note: str | None,
    reference_type: str = "MANUAL_ADJUSTMENT",
    reference_id: UUID | None = None,
):
    movement = InventoryMovement(
        store_id=store_id,
        product_id=product_id,
        movement_type="ADJUSTMENT",
        quantity_delta=quantity_delta,
        reference_type=reference_type,
        reference_id=reference_id,
        note=note,
    )

    db.add(movement)
    await db.flush()

    return movement
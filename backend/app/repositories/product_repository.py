from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.product_alias import ProductAlias


async def list_products(
    db: AsyncSession,
    store_id: UUID,
    limit: int = 50,
    offset: int = 0,
    active_only: bool = True,
) -> list[Product]:
    query = select(Product).where(
        Product.store_id == store_id
    )

    if active_only:
        query = query.where(Product.is_active.is_(True))

    query = (
        query
        .order_by(Product.name.asc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_product(
    db: AsyncSession,
    store_id: UUID,
    product_id: UUID,
) -> Product | None:
    result = await db.execute(
        select(Product).where(
            Product.store_id == store_id,
            Product.id == product_id,
        )
    )
    return result.scalar_one_or_none()


async def get_product_aliases(
    db: AsyncSession,
    store_id: UUID,
    product_id: UUID,
) -> list[ProductAlias]:
    result = await db.execute(
        select(ProductAlias).where(
            ProductAlias.store_id == store_id,
            ProductAlias.product_id == product_id,
        ).order_by(ProductAlias.alias.asc())
    )
    return list(result.scalars().all())

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.product import Product
from app.models.product_alias import ProductAlias


async def get_active_products_with_aliases(
    db: AsyncSession,
    store_id: UUID,
) -> list[tuple[Product, list[str]]]:
    """
    Return active products belonging to this store,
    together with their aliases.
    """

    result = await db.execute(
        select(Product, ProductAlias.alias)
        .outerjoin(
            ProductAlias,
            (ProductAlias.product_id == Product.id)
            & (ProductAlias.store_id == Product.store_id),
        )
        .where(
            Product.store_id == store_id,
            Product.is_active.is_(True),
        )
        .order_by(Product.name)
    )

    grouped: dict[UUID, tuple[Product, list[str]]] = {}

    for product, alias in result.all():
        if product.id not in grouped:
            grouped[product.id] = (product, [])

        if alias:
            grouped[product.id][1].append(alias)

    return list(grouped.values())


async def get_active_customers(
    db: AsyncSession,
    store_id: UUID,
) -> list[Customer]:
    """Return active customers belonging to this store."""

    result = await db.execute(
        select(Customer)
        .where(
            Customer.store_id == store_id,
            Customer.is_active.is_(True),
        )
        .order_by(Customer.name)
    )

    return list(result.scalars().all())

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.product_alias import ProductAlias
from app.repositories.product_repository import (
    get_product,
    get_product_aliases,
    list_products,
)
from app.schemas.product import ProductCreate, ProductDetail


async def list_store_products(
    db: AsyncSession,
    store_id: UUID,
    limit: int,
    offset: int,
    active_only: bool,
):
    return await list_products(
        db=db,
        store_id=store_id,
        limit=limit,
        offset=offset,
        active_only=active_only,
    )


async def get_store_product(
    db: AsyncSession,
    store_id: UUID,
    product_id: UUID,
):
    product = await get_product(db, store_id, product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found.",
        )

    aliases = await get_product_aliases(
        db, store_id, product_id
    )

    return ProductDetail(
        id=product.id,
        name=product.name,
        description=product.description,
        sku=product.sku,
        unit=product.unit,
        cost_price_paise=product.cost_price_paise,
        selling_price_paise=product.selling_price_paise,
        is_active=product.is_active,
        aliases=[
            {
                "alias": alias.alias,
                "language": alias.language,
            }
            for alias in aliases
        ],
    )


async def create_store_product(
    db: AsyncSession,
    store_id: UUID,
    payload: ProductCreate,
):
    product = Product(
        store_id=store_id,
        name=payload.name,
        description=payload.description,
        sku=payload.sku,
        unit=payload.unit,
        cost_price_paise=payload.cost_price_paise,
        selling_price_paise=payload.selling_price_paise,
        is_active=True,
    )

    try:
        db.add(product)
        await db.flush()

        for item in payload.aliases:
            db.add(
                ProductAlias(
                    store_id=store_id,
                    product_id=product.id,
                    alias=item.alias,
                    normalized_alias=item.alias.strip().casefold(),
                    language=item.language,
                )
            )

        await db.commit()

    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A product with this SKU or one of these aliases "
                "already exists in this store."
            ),
        ) from exc

    await db.refresh(product)

    aliases = await get_product_aliases(
        db, store_id, product.id
    )

    return ProductDetail(
        id=product.id,
        name=product.name,
        description=product.description,
        sku=product.sku,
        unit=product.unit,
        cost_price_paise=product.cost_price_paise,
        selling_price_paise=product.selling_price_paise,
        is_active=product.is_active,
        aliases=[
            {
                "alias": alias.alias,
                "language": alias.language,
            }
            for alias in aliases
        ],
    )
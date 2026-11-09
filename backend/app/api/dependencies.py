from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.store import Store
from app.models.user import User


async def get_demo_context(
    db: AsyncSession = Depends(get_db),
) -> tuple[UUID, UUID]:
    """
    Resolve the demo store and owner.

    Development-only. Replace with JWT-based tenant and user
    resolution before exposing the API publicly.
    """

    if settings.APP_ENV != "development":
        raise HTTPException(
            status_code=403,
            detail="Demo access is disabled outside development.",
        )

    store = await db.scalar(
        select(Store).where(
            Store.phone == settings.DEMO_STORE_PHONE
        )
    )

    if store is None:
        raise HTTPException(
            status_code=503,
            detail="Demo store not found. Run the demo seed script.",
        )

    owner = await db.scalar(
        select(User).where(
            User.store_id == store.id,
            User.phone == settings.DEMO_OWNER_PHONE,
            User.is_active.is_(True),
        )
    )

    if owner is None:
        raise HTTPException(
            status_code=503,
            detail="Active demo owner not found. Run the demo seed script.",
        )

    return store.id, owner.id


async def get_demo_store_id(
    context: tuple[UUID, UUID] = Depends(get_demo_context),
) -> UUID:
    return context[0]


async def get_demo_user_id(
    context: tuple[UUID, UUID] = Depends(get_demo_context),
) -> UUID:
    return context[1]
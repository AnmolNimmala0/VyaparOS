from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_demo_store_id
from app.core.database import get_db
from app.schemas.sale import SaleCreate, SaleRead
from app.services.sale_service import create_sale

router = APIRouter(prefix="/sales", tags=["Sales"])


@router.post(
    "",
    response_model=SaleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_sale(
    payload: SaleCreate,
    store_id: UUID = Depends(get_demo_store_id),
    db: AsyncSession = Depends(get_db),
):
    return await create_sale(
        db=db,
        store_id=store_id,
        payload=payload,
    )
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_demo_store_id,
    get_demo_user_id,
)
from app.core.database import get_db
from app.schemas.pending_operation import PendingOperationRead
from app.services.execution_service import execute_pending_operation
from app.services.pending_operation_service import (
    cancel_pending_operation,
    confirm_pending_operation,
)

router = APIRouter(
    prefix="/operations",
    tags=["Operations"],
)


@router.post(
    "/{operation_id}/confirm",
    response_model=PendingOperationRead,
)
async def confirm_operation(
    operation_id: UUID,
    store_id: UUID = Depends(get_demo_store_id),
    user_id: UUID = Depends(get_demo_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await confirm_pending_operation(
        db=db,
        store_id=store_id,
        user_id=user_id,
        operation_id=operation_id,
    )


@router.post(
    "/{operation_id}/execute",
    response_model=PendingOperationRead,
)
async def execute_operation(
    operation_id: UUID,
    store_id: UUID = Depends(get_demo_store_id),
    user_id: UUID = Depends(get_demo_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await execute_pending_operation(
        db=db,
        store_id=store_id,
        user_id=user_id,
        operation_id=operation_id,
    )


@router.post(
    "/{operation_id}/cancel",
    response_model=PendingOperationRead,
)
async def cancel_operation(
    operation_id: UUID,
    store_id: UUID = Depends(get_demo_store_id),
    user_id: UUID = Depends(get_demo_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await cancel_pending_operation(
        db=db,
        store_id=store_id,
        user_id=user_id,
        operation_id=operation_id,
    )
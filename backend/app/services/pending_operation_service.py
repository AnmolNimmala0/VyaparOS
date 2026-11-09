from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent
from app.models.conversation import Conversation
from app.models.pending_operation import PendingOperation
from app.schemas.operation_plan import (
    InventoryAdjustmentOperationPlan,
    OperationPlan,
    RepaymentOperationPlan,
    SaleOperationPlan,
)

PENDING_OPERATION_TTL_MINUTES = 5


async def create_pending_operation(
    db: AsyncSession,
    store_id: UUID,
    user_id: UUID,
    conversation_id: UUID,
    plan: OperationPlan,
) -> PendingOperation:
    """
    Persist a validated operation plan.

    This function does not execute the sale or repayment.
    It only creates an operation awaiting user confirmation.
    """

    conversation = await db.scalar(
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.store_id == store_id,
            Conversation.user_id == user_id,
            Conversation.status == "ACTIVE",
        )
        .with_for_update()
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Active conversation not found.",
        )

    if isinstance(plan, SaleOperationPlan):
        operation_type = "SALE"
    elif isinstance(plan, RepaymentOperationPlan):
        operation_type = "REPAYMENT"
    elif isinstance(plan, InventoryAdjustmentOperationPlan):
        operation_type = "INVENTORY_ADJUSTMENT"
    else:
        raise HTTPException(
            status_code=422,
            detail="Unsupported operation plan.",
        )

    now = datetime.now(UTC)

    pending = PendingOperation(
        store_id=store_id,
        conversation_id=conversation_id,
        created_by_user_id=user_id,
        operation_type=operation_type,
        status="AWAITING_CONFIRMATION",
        payload=plan.model_dump(mode="json"),
        confirmation_message=plan.confirmation_message,
        expires_at=now + timedelta(
            minutes=PENDING_OPERATION_TTL_MINUTES
        ),
    )

    try:
        db.add(pending)
        await db.flush()

        db.add(
            AuditEvent(
                store_id=store_id,
                user_id=user_id,
                conversation_id=conversation_id,
                pending_operation_id=pending.id,
                event_type="OPERATION_CREATED",
                entity_type="PENDING_OPERATION",
                entity_id=pending.id,
                event_data={
                    "operation_type": operation_type,
                    "status": "AWAITING_CONFIRMATION",
                    "expires_at": pending.expires_at.isoformat(),
                },
            )
        )

        await db.commit()
        await db.refresh(pending)

        return pending

    except Exception:
        await db.rollback()
        raise


async def confirm_pending_operation(
    db: AsyncSession,
    store_id: UUID,
    user_id: UUID,
    operation_id: UUID,
) -> PendingOperation:
    """
    Confirm a pending operation.

    Confirmation changes its status only.
    It does not execute the underlying business transaction.
    """

    pending = await db.scalar(
        select(PendingOperation)
        .where(
            PendingOperation.id == operation_id,
            PendingOperation.store_id == store_id,
            PendingOperation.created_by_user_id == user_id,
        )
        .with_for_update()
    )

    if pending is None:
        raise HTTPException(
            status_code=404,
            detail="Pending operation not found.",
        )

    if pending.status != "AWAITING_CONFIRMATION":
        raise HTTPException(
            status_code=409,
            detail=f"Operation cannot be confirmed from status {pending.status}.",
        )

    now = datetime.now(UTC)

    if pending.expires_at is not None and pending.expires_at <= now:
        try:
            pending.status = "EXPIRED"

            db.add(
                AuditEvent(
                    store_id=store_id,
                    user_id=user_id,
                    conversation_id=pending.conversation_id,
                    pending_operation_id=pending.id,
                    event_type="OPERATION_EXPIRED",
                    entity_type="PENDING_OPERATION",
                    entity_id=pending.id,
                    event_data={
                        "previous_status": "AWAITING_CONFIRMATION",
                        "new_status": "EXPIRED",
                    },
                )
            )

            await db.commit()

        except Exception:
            await db.rollback()
            raise

        raise HTTPException(
            status_code=409,
            detail="This operation has expired. Please create a new request.",
        )

    try:
        pending.status = "CONFIRMED"

        db.add(
            AuditEvent(
                store_id=store_id,
                user_id=user_id,
                conversation_id=pending.conversation_id,
                pending_operation_id=pending.id,
                event_type="OPERATION_CONFIRMED",
                entity_type="PENDING_OPERATION",
                entity_id=pending.id,
                event_data={
                    "previous_status": "AWAITING_CONFIRMATION",
                    "new_status": "CONFIRMED",
                },
            )
        )

        await db.commit()
        await db.refresh(pending)

        return pending

    except Exception:
        await db.rollback()
        raise


async def cancel_pending_operation(
    db: AsyncSession,
    store_id: UUID,
    user_id: UUID,
    operation_id: UUID,
) -> PendingOperation:
    """
    Cancel an operation that is awaiting confirmation.
    """

    pending = await db.scalar(
        select(PendingOperation)
        .where(
            PendingOperation.id == operation_id,
            PendingOperation.store_id == store_id,
            PendingOperation.created_by_user_id == user_id,
        )
        .with_for_update()
    )

    if pending is None:
        raise HTTPException(
            status_code=404,
            detail="Pending operation not found.",
        )

    if pending.status != "AWAITING_CONFIRMATION":
        raise HTTPException(
            status_code=409,
            detail=f"Operation cannot be cancelled from status {pending.status}.",
        )

    try:
        pending.status = "CANCELLED"

        db.add(
            AuditEvent(
                store_id=store_id,
                user_id=user_id,
                conversation_id=pending.conversation_id,
                pending_operation_id=pending.id,
                event_type="OPERATION_CANCELLED",
                entity_type="PENDING_OPERATION",
                entity_id=pending.id,
                event_data={
                    "previous_status": "AWAITING_CONFIRMATION",
                    "new_status": "CANCELLED",
                },
            )
        )

        await db.commit()
        await db.refresh(pending)

        return pending

    except Exception:
        await db.rollback()
        raise
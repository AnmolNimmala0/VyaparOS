from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent
from app.models.pending_operation import PendingOperation
from app.schemas.customer import CustomerRepaymentCreate
from app.schemas.inventory import InventoryAdjustmentCreate
from app.schemas.sale import SaleCreate
from app.services.credit_service import (
    record_repayment_in_transaction,
)
from app.services.inventory_service import (
    adjust_inventory_in_transaction,
)
from app.services.sale_service import (
    create_sale_in_transaction,
)


async def execute_pending_operation(
    db: AsyncSession,
    store_id: UUID,
    user_id: UUID,
    operation_id: UUID,
) -> PendingOperation:
    """
    Execute a confirmed pending operation exactly once.

    The pending-operation lock serializes concurrent execution requests.
    The business transaction, result reference, status and audit event
    are committed together.
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

    # Idempotency: a retry after successful execution must not
    # create another sale or repayment.
    if pending.status == "COMPLETED":
        return pending

    if pending.status != "CONFIRMED":
        raise HTTPException(
            status_code=409,
            detail=(
                "Operation must be confirmed before execution. "
                f"Current status: {pending.status}."
            ),
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
                        "previous_status": "CONFIRMED",
                        "new_status": "EXPIRED",
                        "reason": "Execution attempted after expiry.",
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
        if pending.operation_type in ("SALE", "CREDIT"):
            # Revalidate the stored plan using the API input schema.
            # Prices and available stock are fetched again by the
            # sale service, not trusted from the original plan.
            sale_payload = SaleCreate.model_validate(
                {
                    "items": [
                        {
                            "product_id": item["product_id"],
                            "quantity": item["quantity"],
                        }
                        for item in pending.payload["items"]
                    ],
                    "customer_id": pending.payload.get("customer_id"),
                    "amount_paid_paise": pending.payload[
                        "amount_paid_paise"
                    ],
                    "payment_method": pending.payload.get(
                        "payment_method"
                    ),
                    "note": pending.payload.get("note"),
                }
            )

            sale = await create_sale_in_transaction(
                db=db,
                store_id=store_id,
                payload=sale_payload,
            )

            result_entity_type = "SALE"
            result_entity_id = sale.id

        elif pending.operation_type == "REPAYMENT":
            repayment_payload = CustomerRepaymentCreate(
                amount_paise=pending.payload["amount_paise"],
                note=pending.payload.get("note"),
            )

            repayment = await record_repayment_in_transaction(
                db=db,
                store_id=store_id,
                customer_id=UUID(
                    str(pending.payload["customer_id"])
                ),
                payload=repayment_payload,
                reference_type="PENDING_OPERATION",
                reference_id=pending.id,
            )

            result_entity_type = "CUSTOMER_LEDGER_ENTRY"
            result_entity_id = repayment["entry_id"]

        elif pending.operation_type == "INVENTORY_ADJUSTMENT":
            product_id = UUID(str(pending.payload["product_id"]))
            quantity_delta = Decimal(str(pending.payload["quantity_delta"]))
            reorder_level = (
                Decimal(str(pending.payload["reorder_level"]))
                if pending.payload.get("reorder_level") is not None
                else None
            )

            adjustment_payload = InventoryAdjustmentCreate(
                product_id=product_id,
                quantity_delta=quantity_delta,
                reorder_level=reorder_level,
                note=pending.payload.get("note"),
            )

            adjustment = await adjust_inventory_in_transaction(
                db=db,
                store_id=store_id,
                payload=adjustment_payload,
                reference_type="PENDING_OPERATION",
                reference_id=pending.id,
            )

            result_entity_type = "INVENTORY_MOVEMENT"
            result_entity_id = adjustment.movement_id

        else:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Unsupported pending operation type: "
                    f"{pending.operation_type}."
                ),
            )

        # Save the execution result on the pending operation.
        pending.status = "COMPLETED"
        pending.result_entity_type = result_entity_type
        pending.result_entity_id = result_entity_id

        db.add(
            AuditEvent(
                store_id=store_id,
                user_id=user_id,
                conversation_id=pending.conversation_id,
                pending_operation_id=pending.id,
                event_type="OPERATION_COMPLETED",
                entity_type=result_entity_type,
                entity_id=result_entity_id,
                event_data={
                    "operation_type": pending.operation_type,
                    "previous_status": "CONFIRMED",
                    "new_status": "COMPLETED",
                    "result_entity_type": result_entity_type,
                    "result_entity_id": str(result_entity_id),
                },
            )
        )

        # One commit for the business transaction, result reference,
        # pending-operation status and audit event.
        await db.commit()
        await db.refresh(pending)

        return pending

    except Exception:
        await db.rollback()
        raise
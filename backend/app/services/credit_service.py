from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.customer_ledger_entry import CustomerLedgerEntry
from app.schemas.customer import CustomerRepaymentCreate


async def record_repayment_in_transaction(
    db: AsyncSession,
    store_id: UUID,
    customer_id: UUID,
    payload: CustomerRepaymentCreate,
    reference_type: str = "MANUAL_REPAYMENT",
    reference_id: UUID | None = None,
) -> dict:
    """
    Record a repayment without committing or rolling back.

    The caller owns the transaction.
    """

    # Lock the customer row to serialize concurrent repayments
    # and sales that create customer credit.
    customer = await db.scalar(
        select(Customer)
        .where(
            Customer.id == customer_id,
            Customer.store_id == store_id,
            Customer.is_active.is_(True),
        )
        .with_for_update()
    )

    if customer is None:
        raise HTTPException(
            status_code=404,
            detail="Customer not found or inactive.",
        )

    balance_query = select(
        func.coalesce(
            func.sum(
                case(
                    (
                        CustomerLedgerEntry.entry_type == "CREDIT",
                        CustomerLedgerEntry.amount_paise,
                    ),
                    (
                        CustomerLedgerEntry.entry_type.in_(
                            ["ADJUSTMENT", "REVERSAL"]
                        ),
                        CustomerLedgerEntry.amount_paise,
                    ),
                    else_=0,
                )
            ),
            0,
        )
        - func.coalesce(
            func.sum(
                case(
                    (
                        CustomerLedgerEntry.entry_type == "REPAYMENT",
                        CustomerLedgerEntry.amount_paise,
                    ),
                    else_=0,
                )
            ),
            0,
        )
    ).where(
        CustomerLedgerEntry.store_id == store_id,
        CustomerLedgerEntry.customer_id == customer_id,
    )

    outstanding = await db.scalar(balance_query)
    outstanding = int(outstanding or 0)

    if outstanding <= 0:
        raise HTTPException(
            status_code=409,
            detail="This customer has no outstanding balance.",
        )

    if payload.amount_paise > outstanding:
        raise HTTPException(
            status_code=409,
            detail=(
                "Repayment exceeds outstanding balance. "
                f"Outstanding: {outstanding} paise."
            ),
        )

    entry = CustomerLedgerEntry(
        store_id=store_id,
        customer_id=customer_id,
        entry_type="REPAYMENT",
        amount_paise=payload.amount_paise,
        reference_type=reference_type,
        reference_id=reference_id,
        note=payload.note,
    )

    db.add(entry)
    await db.flush()

    new_outstanding = outstanding - payload.amount_paise

    return {
        "entry_id": entry.id,
        "customer_id": customer.id,
        "customer_name": customer.name,
        "amount_paise": entry.amount_paise,
        "outstanding_paise": new_outstanding,
        "created_at": entry.created_at,
    }


async def record_repayment(
    db: AsyncSession,
    store_id: UUID,
    customer_id: UUID,
    payload: CustomerRepaymentCreate,
) -> dict:
    """
    Public service wrapper for the existing repayment API.
    """

    try:
        result = await record_repayment_in_transaction(
            db=db,
            store_id=store_id,
            customer_id=customer_id,
            payload=payload,
        )

        await db.commit()
        return result

    except Exception:
        await db.rollback()
        raise
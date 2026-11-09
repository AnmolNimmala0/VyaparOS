from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.customer_ledger_entry import CustomerLedgerEntry
from app.schemas.customer import CustomerCreate


async def list_customers(
    db: AsyncSession,
    store_id: UUID,
):
    statement = (
        select(Customer)
        .where(
            Customer.store_id == store_id,
            Customer.is_active.is_(True),
        )
        .order_by(Customer.name)
    )

    result = await db.execute(statement)
    return result.scalars().all()


async def create_customer(
    db: AsyncSession,
    store_id: UUID,
    payload: CustomerCreate,
):
    customer = Customer(
        store_id=store_id,
        name=payload.name.strip(),
        phone=payload.phone,
        notes=payload.notes,
        is_active=True,
    )

    db.add(customer)

    try:
        await db.commit()
        await db.refresh(customer)
        return customer
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer with this phone number already exists.",
        ) from exc


async def get_customer_balance(
    db: AsyncSession,
    store_id: UUID,
    customer_id: UUID,
):
    statement = (
        select(
            func.coalesce(
                func.sum(
                    case(
                        (CustomerLedgerEntry.entry_type == "CREDIT",
                         CustomerLedgerEntry.amount_paise),
                        (CustomerLedgerEntry.entry_type == "ADJUSTMENT",
                         CustomerLedgerEntry.amount_paise),
                        (CustomerLedgerEntry.entry_type == "REVERSAL",
                         CustomerLedgerEntry.amount_paise),
                        else_=0,
                    )
                ),
                0,
            ).label("total_credit"),
            func.coalesce(
                func.sum(
                    case(
                        (CustomerLedgerEntry.entry_type == "REPAYMENT",
                         CustomerLedgerEntry.amount_paise),
                        else_=0,
                    )
                ),
                0,
            ).label("total_repaid"),
        )
        .where(
            CustomerLedgerEntry.store_id == store_id,
            CustomerLedgerEntry.customer_id == customer_id,
        )
    )

    result = await db.execute(statement)
    row = result.one()

    customer = await db.scalar(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.store_id == store_id,
        )
    )

    if customer is None:
        raise HTTPException(
            status_code=404,
            detail="Customer not found.",
        )

    return {
        "customer_id": customer.id,
        "customer_name": customer.name,
        "total_credit_paise": row.total_credit,
        "total_repaid_paise": row.total_repaid,
        "outstanding_paise": row.total_credit - row.total_repaid,
    }


async def get_customer_ledger(
    db: AsyncSession,
    store_id: UUID,
    customer_id: UUID,
):
    customer = await db.scalar(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.store_id == store_id,
        )
    )

    if customer is None:
        raise HTTPException(
            status_code=404,
            detail="Customer not found.",
        )

    result = await db.execute(
        select(CustomerLedgerEntry)
        .where(
            CustomerLedgerEntry.store_id == store_id,
            CustomerLedgerEntry.customer_id == customer_id,
        )
        .order_by(CustomerLedgerEntry.created_at.desc())
    )

    return result.scalars().all()

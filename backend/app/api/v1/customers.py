from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_demo_store_id
from app.core.database import get_db
from app.schemas.customer import (
    CustomerBalanceRead,
    CustomerCreate,
    CustomerLedgerEntryRead,
    CustomerRead,
    CustomerRepaymentCreate,
    CustomerRepaymentRead,
)
from app.services.credit_service import record_repayment
from app.services.customer_service import (
    create_customer,
    get_customer_balance,
    get_customer_ledger,
    list_customers,
)

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("", response_model=list[CustomerRead])
async def get_customers(
    store_id: UUID = Depends(get_demo_store_id),
    db: AsyncSession = Depends(get_db),
):
    return await list_customers(db, store_id)


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
async def add_customer(
    payload: CustomerCreate,
    store_id: UUID = Depends(get_demo_store_id),
    db: AsyncSession = Depends(get_db),
):
    return await create_customer(db, store_id, payload)


@router.get("/{customer_id}/balance", response_model=CustomerBalanceRead)
async def customer_balance(
    customer_id: UUID,
    store_id: UUID = Depends(get_demo_store_id),
    db: AsyncSession = Depends(get_db),
):
    return await get_customer_balance(db, store_id, customer_id)


@router.get("/{customer_id}/ledger", response_model=list[CustomerLedgerEntryRead])
async def customer_ledger(
    customer_id: UUID,
    store_id: UUID = Depends(get_demo_store_id),
    db: AsyncSession = Depends(get_db),
):
    return await get_customer_ledger(db, store_id, customer_id)

@router.post(
    "/{customer_id}/repayments",
    response_model=CustomerRepaymentRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_customer_repayment(
    customer_id: UUID,
    payload: CustomerRepaymentCreate,
    store_id: UUID = Depends(get_demo_store_id),
    db: AsyncSession = Depends(get_db),
):
    return await record_repayment(
        db=db,
        store_id=store_id,
        customer_id=customer_id,
        payload=payload,
    )
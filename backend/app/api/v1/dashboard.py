from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_demo_store_id
from app.core.database import get_db
from app.services.report_service import (
    get_credit_summary,
    get_daily_summary,
    get_low_stock,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

IST = ZoneInfo("Asia/Kolkata")


@router.get("/summary")
async def daily_summary(
    report_date: date | None = Query(default=None),
    store_id: UUID = Depends(get_demo_store_id),
    db: AsyncSession = Depends(get_db),
):
    selected_date = report_date or datetime.now(IST).date()

    return await get_daily_summary(
        db=db,
        store_id=store_id,
        report_date=selected_date,
    )


@router.get("/credit")
async def credit_summary(
    store_id: UUID = Depends(get_demo_store_id),
    db: AsyncSession = Depends(get_db),
):
    return await get_credit_summary(
        db=db,
        store_id=store_id,
    )


@router.get("/low-stock")
async def low_stock_report(
    store_id: UUID = Depends(get_demo_store_id),
    db: AsyncSession = Depends(get_db),
):
    return await get_low_stock(
        db=db,
        store_id=store_id,
    )

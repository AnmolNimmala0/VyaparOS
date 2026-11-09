from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.customer_ledger_entry import CustomerLedgerEntry
from app.models.inventory_balance import InventoryBalance
from app.models.product import Product
from app.models.sale import Sale
from app.models.sale_item import SaleItem

IST = ZoneInfo("Asia/Kolkata")


def paise_from_decimal(value) -> int:
    return int(
        Decimal(value or 0).quantize(
            Decimal(1),
            rounding=ROUND_HALF_UP,
        )
    )


async def get_daily_summary(
    db: AsyncSession,
    store_id: UUID,
    report_date: date,
):
    # Convert the Indian calendar day into timezone-aware boundaries.
    start = datetime.combine(report_date, time.min, tzinfo=IST)
    end = start + timedelta(days=1)

    sales_result = await db.execute(
        select(
            func.count(Sale.id).label("transaction_count"),
            func.coalesce(
                func.sum(Sale.total_amount_paise), 0
            ).label("revenue"),
            func.coalesce(
                func.sum(Sale.amount_paid_paise), 0
            ).label("collected"),
            func.coalesce(
                func.sum(Sale.amount_due_paise), 0
            ).label("due"),
        ).where(
            Sale.store_id == store_id,
            Sale.status == "COMPLETED",
            Sale.created_at >= start,
            Sale.created_at < end,
        )
    )

    sales = sales_result.one()

    cogs_result = await db.execute(
        select(
            func.coalesce(
                func.sum(SaleItem.unit_cost_paise * SaleItem.quantity),
                0,
            )
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(
            Sale.store_id == store_id,
            Sale.status == "COMPLETED",
            Sale.created_at >= start,
            Sale.created_at < end,
        )
    )

    cost_of_goods_sold = paise_from_decimal(cogs_result.scalar_one())
    revenue = int(sales.revenue or 0)

    return {
        "date": report_date.isoformat(),
        "transaction_count": int(sales.transaction_count or 0),
        "revenue_paise": revenue,
        "collected_paise": int(sales.collected or 0),
        "outstanding_paise": int(sales.due or 0),
        "cost_of_goods_sold_paise": cost_of_goods_sold,
        "gross_profit_paise": revenue - cost_of_goods_sold,
    }


async def get_credit_summary(
    db: AsyncSession,
    store_id: UUID,
):
    signed_amount = case(
        (
            CustomerLedgerEntry.entry_type.in_(
                ["CREDIT", "ADJUSTMENT", "REVERSAL"]
            ),
            CustomerLedgerEntry.amount_paise,
        ),
        (
            CustomerLedgerEntry.entry_type == "REPAYMENT",
            -CustomerLedgerEntry.amount_paise,
        ),
        else_=0,
    )

    result = await db.execute(
        select(
            Customer.id.label("customer_id"),
            Customer.name.label("customer_name"),
            func.coalesce(func.sum(signed_amount), 0).label("outstanding"),
        )
        .outerjoin(
            CustomerLedgerEntry,
            (
                CustomerLedgerEntry.customer_id == Customer.id
            ) & (
                CustomerLedgerEntry.store_id == Customer.store_id
            ),
        )
        .where(
            Customer.store_id == store_id,
            Customer.is_active.is_(True),
        )
        .group_by(Customer.id, Customer.name)
        .order_by(Customer.name)
    )

    customers = []
    total_outstanding = 0

    for row in result:
        outstanding = int(row.outstanding or 0)
        total_outstanding += outstanding

        customers.append({
            "customer_id": row.customer_id,
            "customer_name": row.customer_name,
            "outstanding_paise": outstanding,
        })

    return {
        "total_outstanding_paise": total_outstanding,
        "customers": customers,
    }


async def get_low_stock(
    db: AsyncSession,
    store_id: UUID,
):
    result = await db.execute(
        select(
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            Product.sku,
            Product.unit,
            InventoryBalance.quantity,
            InventoryBalance.reorder_level,
        )
        .join(
            InventoryBalance,
            (
                InventoryBalance.product_id == Product.id
            ) & (
                InventoryBalance.store_id == Product.store_id
            ),
        )
        .where(
            Product.store_id == store_id,
            Product.is_active.is_(True),
            InventoryBalance.quantity <= InventoryBalance.reorder_level,
        )
        .order_by(InventoryBalance.quantity.asc())
    )

    return [
        {
            "product_id": row.product_id,
            "product_name": row.product_name,
            "sku": row.sku,
            "unit": row.unit,
            "quantity": row.quantity,
            "reorder_level": row.reorder_level,
        }
        for row in result
    ]

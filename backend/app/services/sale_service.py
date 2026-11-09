from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.customer_ledger_entry import CustomerLedgerEntry
from app.models.inventory_balance import InventoryBalance
from app.models.inventory_movement import InventoryMovement
from app.models.payment import Payment
from app.models.product import Product
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.schemas.sale import SaleCreate, SaleItemRead, SaleRead


def calculate_line_total(
    unit_price_paise: int,
    quantity: Decimal,
) -> int:
    return int(
        (Decimal(unit_price_paise) * quantity).quantize(
            Decimal(1),
            rounding=ROUND_HALF_UP,
        )
    )


async def create_sale_in_transaction(
    db: AsyncSession,
    store_id: UUID,
    payload: SaleCreate,
) -> SaleRead:
    """
    Create a sale without committing or rolling back.

    The caller owns the transaction. This allows a pending operation,
    sale, inventory movements, payments, ledger entries and audit event
    to be committed atomically.
    """

    product_ids = [item.product_id for item in payload.items]

    product_result = await db.execute(
        select(Product).where(
            Product.store_id == store_id,
            Product.id.in_(product_ids),
            Product.is_active.is_(True),
        )
    )

    products = {
        product.id: product
        for product in product_result.scalars().all()
    }

    if len(products) != len(product_ids):
        raise HTTPException(
            status_code=404,
            detail="One or more active products were not found.",
        )

    # Lock inventory rows in a consistent order.
    balance_result = await db.execute(
        select(InventoryBalance)
        .where(
            InventoryBalance.store_id == store_id,
            InventoryBalance.product_id.in_(product_ids),
        )
        .order_by(InventoryBalance.product_id)
        .with_for_update()
    )

    balances = {
        balance.product_id: balance
        for balance in balance_result.scalars().all()
    }

    calculated_items = []
    total_amount_paise = 0

    for item in payload.items:
        product = products[item.product_id]
        balance = balances.get(item.product_id)

        current_stock = (
            balance.quantity
            if balance is not None
            else Decimal(0)
        )

        if current_stock < item.quantity:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Insufficient stock for {product.name}. "
                    f"Available: {current_stock} {product.unit}; "
                    f"requested: {item.quantity}."
                ),
            )

        line_total = calculate_line_total(
            product.selling_price_paise,
            item.quantity,
        )

        calculated_items.append(
            {
                "product": product,
                "quantity": item.quantity,
                "line_total": line_total,
                "balance": balance,
            }
        )

        total_amount_paise += line_total

    if payload.amount_paid_paise > total_amount_paise:
        raise HTTPException(
            status_code=422,
            detail="Amount paid cannot exceed the sale total.",
        )

    amount_due_paise = (
        total_amount_paise - payload.amount_paid_paise
    )

    if amount_due_paise > 0 and payload.customer_id is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "A customer must be selected when the sale "
                "has an outstanding balance."
            ),
        )

    # Lock the customer row when a customer is attached to the sale.
    if payload.customer_id is not None:
        customer = await db.scalar(
            select(Customer)
            .where(
                Customer.id == payload.customer_id,
                Customer.store_id == store_id,
                Customer.is_active.is_(True),
            )
            .with_for_update()
        )

        if customer is None:
            raise HTTPException(
                status_code=404,
                detail="Active customer not found in this store.",
            )

    sale = Sale(
        store_id=store_id,
        customer_id=payload.customer_id,
        status="COMPLETED",
        total_amount_paise=total_amount_paise,
        amount_paid_paise=payload.amount_paid_paise,
        amount_due_paise=amount_due_paise,
        note=payload.note,
    )

    db.add(sale)
    await db.flush()

    response_items = []

    for item_data in calculated_items:
        product = item_data["product"]
        quantity = item_data["quantity"]
        balance = item_data["balance"]
        line_total = item_data["line_total"]

        db.add(
            SaleItem(
                store_id=store_id,
                sale_id=sale.id,
                product_id=product.id,
                quantity=quantity,
                unit_price_paise=product.selling_price_paise,
                unit_cost_paise=product.cost_price_paise,
                line_total_paise=line_total,
            )
        )

        balance.quantity -= quantity

        db.add(
            InventoryMovement(
                store_id=store_id,
                product_id=product.id,
                movement_type="SALE",
                quantity_delta=-quantity,
                reference_type="SALE",
                reference_id=sale.id,
                note=f"Sale {sale.id}",
            )
        )

        response_items.append(
            SaleItemRead(
                product_id=product.id,
                product_name=product.name,
                quantity=quantity,
                unit_price_paise=product.selling_price_paise,
                unit_cost_paise=product.cost_price_paise,
                line_total_paise=line_total,
            )
        )

    if payload.amount_paid_paise > 0:
        db.add(
            Payment(
                store_id=store_id,
                sale_id=sale.id,
                amount_paise=payload.amount_paid_paise,
                payment_method=payload.payment_method,
            )
        )

    if amount_due_paise > 0:
        db.add(
            CustomerLedgerEntry(
                store_id=store_id,
                customer_id=payload.customer_id,
                entry_type="CREDIT",
                amount_paise=amount_due_paise,
                reference_type="SALE",
                reference_id=sale.id,
                note=f"Credit from sale {sale.id}",
            )
        )

    await db.flush()

    return SaleRead(
        id=sale.id,
        customer_id=sale.customer_id,
        status=sale.status,
        items=response_items,
        total_amount_paise=sale.total_amount_paise,
        amount_paid_paise=sale.amount_paid_paise,
        amount_due_paise=sale.amount_due_paise,
        note=sale.note,
        created_at=sale.created_at,
    )


async def create_sale(
    db: AsyncSession,
    store_id: UUID,
    payload: SaleCreate,
) -> SaleRead:
    """
    Public service wrapper for the existing Sales API.
    """

    try:
        result = await create_sale_in_transaction(
            db=db,
            store_id=store_id,
            payload=payload,
        )

        await db.commit()
        return result

    except Exception:
        await db.rollback()
        raise
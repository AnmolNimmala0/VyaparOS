
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.customer_ledger_entry import CustomerLedgerEntry
from app.models.inventory_balance import InventoryBalance
from app.models.product import Product
from app.schemas.operation_plan import (
    InventoryAdjustmentOperationPlan,
    OperationPlanningResult,
    PlannedSaleItem,
    RepaymentOperationPlan,
    SaleOperationPlan,
)
from app.schemas.resolved_intent import ResolvedAction, ResolvedIntent

READ_ONLY_ACTIONS = {
    "check_inventory",
    "check_customer_balance",
    "get_daily_summary",
}


def rupees_to_paise(value: Decimal) -> int:
    """
    Convert rupees to integer paise without using floating-point arithmetic.
    Reject amounts containing fractions of a paisa.
    """
    value = Decimal(value)
    paise = value * Decimal(100)

    if paise != paise.to_integral_value():
        raise ValueError("Amount cannot contain fractions of a paisa.")

    return int(paise)


def calculate_line_total(
    quantity: Decimal,
    unit_price_paise: int,
) -> int:
    """
    Calculate a line total using the database selling price.
    """
    amount = Decimal(quantity) * Decimal(unit_price_paise)

    return int(
        amount.quantize(
            Decimal(1),
            rounding=ROUND_HALF_UP,
        )
    )


async def get_customer_outstanding(
    db: AsyncSession,
    store_id: UUID,
    customer_id: UUID,
) -> int:
    """
    Calculate outstanding credit from the customer ledger.

    CREDIT: positive amount increases outstanding.
    REPAYMENT: positive amount decreases outstanding.
    ADJUSTMENT and REVERSAL: their signed amounts are applied directly.
    """

    entries = (
        await db.scalars(
            select(CustomerLedgerEntry).where(
                CustomerLedgerEntry.store_id == store_id,
                CustomerLedgerEntry.customer_id == customer_id,
            )
        )
    ).all()

    outstanding = 0

    for entry in entries:
        if entry.entry_type == "CREDIT":
            outstanding += entry.amount_paise

        elif entry.entry_type == "REPAYMENT":
            outstanding -= entry.amount_paise

        elif entry.entry_type in {"ADJUSTMENT", "REVERSAL"}:
            outstanding += entry.amount_paise

    return outstanding


async def resolve_product_for_planning(
    db: AsyncSession,
    store_id: UUID,
    resolved_action: ResolvedAction,
):
    resolution = resolved_action.product

    if resolution is None or resolution.status != "matched":
        return None

    if resolution.entity_id is None:
        return None

    product = await db.scalar(
        select(Product).where(
            Product.id == resolution.entity_id,
            Product.store_id == store_id,
            Product.is_active.is_(True),
        )
    )

    return product


async def resolve_customer_for_planning(
    db: AsyncSession,
    store_id: UUID,
    resolved_action: ResolvedAction,
):
    resolution = resolved_action.customer

    if resolution is None or resolution.status != "matched":
        return None

    if resolution.entity_id is None:
        return None

    customer = await db.scalar(
        select(Customer).where(
            Customer.id == resolution.entity_id,
            Customer.store_id == store_id,
            Customer.is_active.is_(True),
        )
    )

    return customer


async def plan_sale(
    db: AsyncSession,
    store_id: UUID,
    resolved_action: ResolvedAction,
    questions: list[str],
    language: str = "en",
):
    action = resolved_action.original_action

    product = await resolve_product_for_planning(
        db,
        store_id,
        resolved_action,
    )

    if product is None:
        resolution = resolved_action.product

        if resolution and resolution.status == "ambiguous":
            names = ", ".join(
                candidate.name for candidate in resolution.candidates
            )
            questions.append(
                f"Which product did you mean: {names}?"
            )
        else:
            questions.append(
                f"I couldn't identify the product '{action.product_name}'."
            )

        return None

    quantity = action.quantity

    if quantity is None or quantity <= 0:
        questions.append(
            f"Please specify a valid quantity for {product.name}."
        )
        return None

    inventory = await db.scalar(
        select(InventoryBalance).where(
            InventoryBalance.store_id == store_id,
            InventoryBalance.product_id == product.id,
        )
    )

    available_quantity = (
        inventory.quantity if inventory is not None else Decimal(0)
    )

    if quantity > available_quantity:
        questions.append(
            f"Only {available_quantity} units of {product.name} "
            f"are available, but {quantity} were requested."
        )
        return None

    line_total_paise = calculate_line_total(
        quantity,
        product.selling_price_paise,
    )

    total_amount_paise = line_total_paise

    customer = None

    if action.customer_name:
        customer = await resolve_customer_for_planning(
            db,
            store_id,
            resolved_action,
        )

        if customer is None:
            resolution = resolved_action.customer

            if resolution and resolution.status == "ambiguous":
                names = ", ".join(
                    candidate.name for candidate in resolution.candidates
                )
                questions.append(
                    f"Which customer did you mean: {names}?"
                )
            else:
                questions.append(
                    f"I couldn't identify customer '{action.customer_name}'."
                )

            return None

    payment_type = action.payment_type

    if action.action_type == "record_credit_sale" and payment_type != "CREDIT":
        questions.append(
            "The credit sale payment details are inconsistent."
        )
        return None

    if payment_type == "FULL_PAYMENT":

        if action.payment_method is None:
            questions.append(
                "Please specify the payment method."
            )
            return None

        amount_paid_paise = total_amount_paise

        if action.amount_paid_rupees is not None:
            try:
                explicitly_paid = rupees_to_paise(
                    action.amount_paid_rupees
                )
            except ValueError:
                questions.append(
                    "The payment amount must be specified in rupees "
                    "and paise."
                )
                return None

            if explicitly_paid != total_amount_paise:
                questions.append(
                    f"The sale total is ₹{total_amount_paise / 100:.2f}, "
                    f"but the stated payment is "
                    f"₹{explicitly_paid / 100:.2f}. "
                    "Please clarify the payment."
                )
                return None

    elif payment_type == "CREDIT":

        if customer is None:
            questions.append(
                "Which customer should this credit sale be assigned to?"
            )
            return None

        amount_paid_paise = 0

    elif payment_type == "PARTIAL_PAYMENT":

        if customer is None:
            questions.append(
                "Which customer should this partial payment be assigned to?"
            )
            return None

        if action.amount_paid_rupees is None:
            questions.append(
                "Please specify how much the customer paid."
            )
            return None

        if action.payment_method is None:
            questions.append(
                "Please specify the partial payment method."
            )
            return None

        try:
            amount_paid_paise = rupees_to_paise(
                action.amount_paid_rupees
            )
        except ValueError:
            questions.append(
                "The payment amount must be specified in rupees and paise."
            )
            return None

        if amount_paid_paise <= 0:
            questions.append(
                "The partial payment must be greater than zero."
            )
            return None

        if amount_paid_paise >= total_amount_paise:
            questions.append(
                "The partial payment must be less than the sale total. "
                "Please clarify whether this was a fully paid sale."
            )
            return None

    else:
        questions.append(
            "Was this sale fully paid, partially paid, or on credit?"
        )
        return None

    amount_due_paise = total_amount_paise - amount_paid_paise

    if amount_due_paise > 0 and customer is None:
        questions.append(
            "Which customer should the outstanding amount be assigned to?"
        )
        return None

    planned_item = PlannedSaleItem(
        product_id=product.id,
        product_name=product.name,
        quantity=quantity,
        available_quantity=available_quantity,
        unit_price_paise=product.selling_price_paise,
        line_total_paise=line_total_paise,
    )

    if language == "hi":
        prefix = "Ji, ise table mein abhi update kar rahe hain. Kripya confirm karein: "
        customer_text = (
            f" ({customer.name} ke liye)" if customer is not None else ""
        )
        if amount_due_paise == 0:
            payment_text = f"{action.payment_method or 'CASH'} mein chukta"
        elif amount_paid_paise == 0:
            payment_text = "poora udhaar pe"
        else:
            payment_text = (
                f"₹{amount_paid_paise / 100:.2f} {action.payment_method or 'CASH'} mein, "
                f"₹{amount_due_paise / 100:.2f} udhaar"
            )
        confirmation = (
            f"{prefix}{quantity} x {product.name}{customer_text} bechein. "
            f"Kul: ₹{total_amount_paise / 100:.2f} ({payment_text})."
        )
    else:
        prefix = "Yes, updating this in our table right now. Please confirm: "
        customer_text = (
            f" for {customer.name}" if customer is not None else ""
        )
        if amount_due_paise == 0:
            payment_text = (
                f"paid in {action.payment_method or 'CASH'}"
            )
        elif amount_paid_paise == 0:
            payment_text = "fully on credit"
        else:
            payment_text = (
                f"₹{amount_paid_paise / 100:.2f} paid in "
                f"{action.payment_method or 'CASH'}, "
                f"₹{amount_due_paise / 100:.2f} on credit"
            )
        confirmation = (
            f"{prefix}Sell {quantity} x {product.name}{customer_text}. "
            f"Total: ₹{total_amount_paise / 100:.2f} ({payment_text})."
        )

    return SaleOperationPlan(
        customer_id=customer.id if customer else None,
        customer_name=customer.name if customer else None,
        items=[planned_item],
        total_amount_paise=total_amount_paise,
        amount_paid_paise=amount_paid_paise,
        amount_due_paise=amount_due_paise,
        payment_method=action.payment_method,
        confirmation_message=confirmation,
    )


async def plan_repayment(
    db: AsyncSession,
    store_id: UUID,
    resolved_action: ResolvedAction,
    questions: list[str],
    language: str = "en",
):
    action = resolved_action.original_action

    customer = await resolve_customer_for_planning(
        db,
        store_id,
        resolved_action,
    )

    if customer is None:
        resolution = resolved_action.customer

        if resolution and resolution.status == "ambiguous":
            names = ", ".join(
                candidate.name for candidate in resolution.candidates
            )
            questions.append(
                f"Which customer did you mean: {names}?"
            )
        else:
            questions.append(
                f"I couldn't identify customer '{action.customer_name}'."
            )

        return None

    if action.amount_rupees is None:
        questions.append(
            f"How much did {customer.name} repay?"
        )
        return None

    try:
        amount_paise = rupees_to_paise(action.amount_rupees)
    except ValueError:
        questions.append(
            "The repayment amount must be specified in rupees and paise."
        )
        return None

    if amount_paise <= 0:
        questions.append(
            "The repayment amount must be greater than zero."
        )
        return None

    outstanding_paise = await get_customer_outstanding(
        db,
        store_id,
        customer.id,
    )

    if outstanding_paise < 0:
        questions.append(
            f"{customer.name}'s ledger has a negative balance. "
            "Please review the account before recording repayment."
        )
        return None

    if amount_paise > outstanding_paise:
        questions.append(
            f"{customer.name} owes only "
            f"₹{outstanding_paise / 100:.2f}, but the stated repayment "
            f"is ₹{amount_paise / 100:.2f}. Please clarify."
        )
        return None

    new_outstanding_paise = outstanding_paise - amount_paise

    if language == "hi":
        prefix = "Ji, ise table mein abhi update kar rahe hain. Kripya confirm karein: "
        confirmation = (
            f"{prefix}{customer.name} se ₹{amount_paise / 100:.2f} ki vasooli darj karein. "
            f"Baaki udhaar: ₹{new_outstanding_paise / 100:.2f}."
        )
    else:
        prefix = "Yes, updating this in our table right now. Please confirm: "
        confirmation = (
            f"{prefix}Record a repayment of ₹{amount_paise / 100:.2f} "
            f"from {customer.name}. "
            f"Remaining balance: ₹{new_outstanding_paise / 100:.2f}."
        )

    return RepaymentOperationPlan(
        customer_id=customer.id,
        customer_name=customer.name,
        amount_paise=amount_paise,
        previous_outstanding_paise=outstanding_paise,
        new_outstanding_paise=new_outstanding_paise,
        confirmation_message=confirmation,
    )


async def plan_inventory_adjustment(
    db: AsyncSession,
    store_id: UUID,
    resolved_action: ResolvedAction,
    questions: list[str],
    language: str = "en",
) -> InventoryAdjustmentOperationPlan | None:
    action = resolved_action.original_action

    product = await resolve_product_for_planning(
        db,
        store_id,
        resolved_action,
    )

    if product is None:
        resolution = resolved_action.product

        if resolution and resolution.status == "ambiguous":
            names = ", ".join(
                candidate.name for candidate in resolution.candidates
            )
            questions.append(
                f"Which product did you mean: {names}?"
            )
        else:
            questions.append(
                f"I couldn't identify the product '{action.product_name}'."
            )

        return None

    quantity = action.quantity

    if quantity is None or quantity <= 0:
        questions.append(
            f"Please specify a valid quantity for {product.name}."
        )
        return None

    inventory = await db.scalar(
        select(InventoryBalance).where(
            InventoryBalance.store_id == store_id,
            InventoryBalance.product_id == product.id,
        )
    )

    current_quantity = (
        inventory.quantity if inventory is not None else Decimal(0)
    )

    direction = action.adjustment_direction or "ADD"
    quantity_delta = quantity if direction == "ADD" else -quantity
    new_quantity = current_quantity + quantity_delta

    if new_quantity < 0:
        questions.append(
            f"Cannot reduce stock of {product.name} by {quantity} {product.unit}. "
            f"Current stock is only {current_quantity} {product.unit}."
        )
        return None

    if language == "hi":
        prefix = "Ji, ise table mein abhi update kar rahe hain. Kripya confirm karein: "
        if direction == "ADD":
            confirmation = (
                f"{prefix}{product.name} ke {quantity} {product.unit} stock mein jodein "
                f"({current_quantity} → {new_quantity} {product.unit})."
            )
        else:
            confirmation = (
                f"{prefix}{product.name} ke {quantity} {product.unit} stock se ghatayein "
                f"({current_quantity} → {new_quantity} {product.unit})."
            )
    else:
        prefix = "Yes, updating this in our table right now. Please confirm: "
        if direction == "ADD":
            confirmation = (
                f"{prefix}Add {quantity} {product.unit} of {product.name} to stock "
                f"({current_quantity} → {new_quantity} {product.unit})."
            )
        else:
            confirmation = (
                f"{prefix}Remove {quantity} {product.unit} of {product.name} from stock "
                f"({current_quantity} → {new_quantity} {product.unit})."
            )

    return InventoryAdjustmentOperationPlan(
        product_id=product.id,
        product_name=product.name,
        unit=product.unit,
        quantity_delta=quantity_delta,
        previous_quantity=current_quantity,
        new_quantity=new_quantity,
        adjustment_direction=direction,
        note=f"Stock adjustment via assistant ({direction})",
        confirmation_message=confirmation,
    )


async def plan_operations(
    db: AsyncSession,
    store_id: UUID,
    resolved_intent: ResolvedIntent,
    language: str = "en",
) -> OperationPlanningResult:
    """
    Create read-only operation proposals from resolved Gemini intent.

    No sales, payments, inventory movements or ledger entries are created.
    """

    if resolved_intent.needs_clarification:
        return OperationPlanningResult(
            needs_clarification=True,
            clarification_questions=(
                resolved_intent.clarification_questions
            ),
        )

    plans = []
    questions = []

    for resolved_action in resolved_intent.actions:

        action_type = resolved_action.original_action.action_type

        if action_type in READ_ONLY_ACTIONS:
            continue

        if action_type in {"record_sale", "record_credit_sale"}:
            plan = await plan_sale(
                db,
                store_id,
                resolved_action,
                questions,
                language=language,
            )

        elif action_type == "record_credit_repayment":
            plan = await plan_repayment(
                db,
                store_id,
                resolved_action,
                questions,
                language=language,
            )

        elif action_type == "adjust_inventory":
            plan = await plan_inventory_adjustment(
                db,
                store_id,
                resolved_action,
                questions,
                language=language,
            )

        else:
            questions.append(
                "I couldn't determine a supported business operation."
            )
            continue

        if plan is not None:
            plans.append(plan)

    # Do not allow partial approval of a multi-action request.
    # If any action needs clarification, discard all proposed plans.
    if questions:
        return OperationPlanningResult(
            plans=[],
            needs_clarification=True,
            clarification_questions=list(dict.fromkeys(questions)),
        )

    return OperationPlanningResult(
        plans=plans,
        needs_clarification=False,
        clarification_questions=[],
    )


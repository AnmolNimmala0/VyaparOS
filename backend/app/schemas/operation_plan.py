
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PlannedSaleItem(BaseModel):
    product_id: UUID
    product_name: str
    quantity: Decimal
    available_quantity: Decimal
    unit_price_paise: int
    line_total_paise: int


class SaleOperationPlan(BaseModel):
    operation_type: Literal["SALE"] = "SALE"

    customer_id: UUID | None = None
    customer_name: str | None = None

    items: list[PlannedSaleItem]

    total_amount_paise: int
    amount_paid_paise: int
    amount_due_paise: int

    payment_method: Literal["CASH", "UPI", "CARD", "OTHER"] | None = None

    confirmation_message: str


class RepaymentOperationPlan(BaseModel):
    operation_type: Literal["REPAYMENT"] = "REPAYMENT"

    customer_id: UUID
    customer_name: str

    amount_paise: int
    previous_outstanding_paise: int
    new_outstanding_paise: int

    confirmation_message: str


class InventoryAdjustmentOperationPlan(BaseModel):
    operation_type: Literal["INVENTORY_ADJUSTMENT"] = "INVENTORY_ADJUSTMENT"

    product_id: UUID
    product_name: str
    unit: str
    quantity_delta: Decimal
    previous_quantity: Decimal
    new_quantity: Decimal
    adjustment_direction: Literal["ADD", "REMOVE"] = "ADD"
    note: str | None = None

    confirmation_message: str


OperationPlan = (
    SaleOperationPlan
    | RepaymentOperationPlan
    | InventoryAdjustmentOperationPlan
)


class OperationPlanningResult(BaseModel):
    plans: list[OperationPlan] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)




from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

PaymentType = Literal[
    "FULL_PAYMENT",
    "CREDIT",
    "PARTIAL_PAYMENT",
]

PaymentMethod = Literal[
    "CASH",
    "UPI",
    "CARD",
    "OTHER",
]

AdjustmentDirection = Literal[
    "ADD",
    "REMOVE",
]


class IntentAction(BaseModel):
    action_type: Literal[
        "record_sale",
        "record_credit_repayment",
        "record_credit_sale",
        "check_inventory",
        "check_customer_balance",
        "get_daily_summary",
        "adjust_inventory",
        "unknown",
    ]

    product_name: str | None = None
    customer_name: str | None = None

    quantity: Decimal | None = Field(default=None, gt=0)

    # Used for repayments and other explicitly stated amounts.
    amount_rupees: Decimal | None = Field(default=None, gt=0)

    # Explicit sale-payment information.
    payment_type: PaymentType | None = None
    amount_paid_rupees: Decimal | None = Field(default=None, ge=0)
    payment_method: PaymentMethod | None = None

    # Stock adjustments: ADD for new stock received,
    # REMOVE for damaged, expired or missing stock.
    adjustment_direction: AdjustmentDirection | None = None


class IntentAnalysis(BaseModel):
    language: str
    actions: list[IntentAction]
    needs_clarification: bool = False
    clarification_question: str | None = None
    summary: str

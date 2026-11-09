from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class SaleItemCreate(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(gt=0)

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Quantity must be finite.")

        if value.as_tuple().exponent < -3:
            raise ValueError("Maximum 3 decimal places allowed.")

        return value


class SaleCreate(BaseModel):
    items: list[SaleItemCreate] = Field(min_length=1, max_length=50)
    customer_id: UUID | None = None

    amount_paid_paise: int = Field(default=0, ge=0)
    payment_method: Literal["CASH", "UPI", "CARD", "OTHER"] | None = None

    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_payment(self):
        if self.amount_paid_paise > 0 and self.payment_method is None:
            raise ValueError(
                "Payment method is required when an amount is paid."
            )

        if self.amount_paid_paise == 0 and self.payment_method is not None:
            raise ValueError(
                "Payment method must be omitted when no amount is paid."
            )

        product_ids = [item.product_id for item in self.items]

        if len(product_ids) != len(set(product_ids)):
            raise ValueError(
                "A product can only appear once in a sale. "
                "Combine quantities for duplicate products."
            )

        return self


class SaleItemRead(BaseModel):
    product_id: UUID
    product_name: str
    quantity: Decimal
    unit_price_paise: int
    unit_cost_paise: int
    line_total_paise: int


class SaleRead(BaseModel):
    id: UUID
    customer_id: UUID | None
    status: str

    items: list[SaleItemRead]

    total_amount_paise: int
    amount_paid_paise: int
    amount_due_paise: int

    note: str | None
    created_at: datetime
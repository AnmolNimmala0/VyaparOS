from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InventoryItemRead(BaseModel):
    product_id: UUID
    product_name: str
    sku: str | None
    unit: str
    quantity: Decimal
    reorder_level: Decimal
    is_low_stock: bool

    model_config = ConfigDict(from_attributes=True)


class InventoryAdjustmentCreate(BaseModel):
    product_id: UUID
    quantity_delta: Decimal
    reorder_level: Decimal | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("quantity_delta")
    @classmethod
    def validate_quantity_delta(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Quantity must be a finite number.")

        if value == 0:
            raise ValueError("Quantity adjustment cannot be zero.")

        if abs(value) > Decimal("99999999999.999"):
            raise ValueError("Quantity adjustment is too large.")

        if value.as_tuple().exponent < -3:
            raise ValueError("Quantity supports at most 3 decimal places.")

        return value


class InventoryAdjustmentRead(BaseModel):
    product_id: UUID
    product_name: str
    previous_quantity: Decimal
    quantity_delta: Decimal
    new_quantity: Decimal
    reorder_level: Decimal
    movement_id: UUID
    movement_type: str
    note: str | None
    created_at: datetime
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CustomerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=500)


class CustomerRead(BaseModel):
    id: UUID
    name: str
    phone: str | None
    notes: str | None
    is_active: bool


class CustomerBalanceRead(BaseModel):
    customer_id: UUID
    customer_name: str
    total_credit_paise: int
    total_repaid_paise: int
    outstanding_paise: int


class CustomerLedgerEntryRead(BaseModel):
    id: UUID
    entry_type: str
    amount_paise: int
    note: str | None
    created_at: datetime

class CustomerRepaymentCreate(BaseModel):
    amount_paise: int = Field(gt=0)
    note: str | None = Field(default=None, max_length=500)


class CustomerRepaymentRead(BaseModel):
    entry_id: UUID
    customer_id: UUID
    customer_name: str
    amount_paise: int
    outstanding_paise: int
    created_at: datetime
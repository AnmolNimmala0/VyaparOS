from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ConversationTurnCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    input_type: Literal["TEXT", "VOICE"] = "TEXT"


class ConversationTurnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    sequence_number: int
    role: str
    content: str
    input_type: str
    created_at: datetime

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PendingOperationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    operation_type: str
    status: str
    payload: dict[str, Any]
    confirmation_message: str
    expires_at: datetime | None

    result_entity_type: str | None
    result_entity_id: UUID | None

    created_at: datetime
    updated_at: datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

VoiceProcessStatus = Literal[
    "CLARIFICATION_REQUIRED",
    "AWAITING_CONFIRMATION",
    "READ_ONLY_SUCCESS",
    "READ_ONLY_NOT_IMPLEMENTED",
]


class VoiceProcessResponse(BaseModel):
    status: VoiceProcessStatus
    message: str
    transcript: str
    detected_language: str | None = None

    conversation_id: UUID
    turn_id: UUID

    intent: dict[str, Any] | None = None
    resolved_intent: dict[str, Any] | None = None

    operation_plan: dict[str, Any] | None = None
    pending_operation: dict[str, Any] | None = None

    # Actual data returned by read-only operations.
    data: dict[str, Any] | None = None

    clarification_questions: list[str] = Field(default_factory=list)
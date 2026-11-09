from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.intent import IntentAction

ResolutionStatus = Literal["matched", "ambiguous", "not_found"]


class EntityCandidate(BaseModel):
    id: UUID
    name: str


class EntityResolution(BaseModel):
    status: ResolutionStatus
    query: str | None = None
    entity_id: UUID | None = None
    canonical_name: str | None = None
    candidates: list[EntityCandidate] = Field(default_factory=list)


class ResolvedAction(BaseModel):
    original_action: IntentAction
    product: EntityResolution | None = None
    customer: EntityResolution | None = None


class ResolvedIntent(BaseModel):
    actions: list[ResolvedAction]
    needs_clarification: bool
    clarification_questions: list[str] = Field(default_factory=list)

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"

    __table_args__ = (
        ForeignKeyConstraint(
            ["store_id", "conversation_id"],
            ["conversations.store_id", "conversations.id"],
            ondelete="CASCADE",
            name="fk_conversation_turns_store_conversation",
        ),
        UniqueConstraint(
            "store_id",
            "conversation_id",
            "sequence_number",
            name="uq_conversation_turn_sequence",
        ),
        CheckConstraint(
            "sequence_number > 0",
            name="ck_conversation_turn_sequence",
        ),
        CheckConstraint(
            "role IN ('USER', 'ASSISTANT', 'SYSTEM', 'TOOL')",
            name="ck_conversation_turn_role",
        ),
        CheckConstraint(
            "input_type IN ('TEXT', 'VOICE', 'INTERNAL')",
            name="ck_conversation_turn_input_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    input_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="TEXT",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PendingOperation(Base):
    __tablename__ = "pending_operations"

    __table_args__ = (
        ForeignKeyConstraint(
            ["store_id", "conversation_id"],
            ["conversations.store_id", "conversations.id"],
            ondelete="RESTRICT",
            name="fk_pending_operations_conversation",
        ),
        ForeignKeyConstraint(
            ["store_id", "created_by_user_id"],
            ["users.store_id", "users.id"],
            ondelete="RESTRICT",
            name="fk_pending_operations_user",
        ),
        CheckConstraint(
            "status IN ("
            "'CREATED', "
            "'AWAITING_CONFIRMATION', "
            "'CONFIRMED', "
            "'EXECUTING', "
            "'COMPLETED', "
            "'CANCELLED', "
            "'EXPIRED', "
            "'FAILED'"
            ")",
            name="ck_pending_operation_status",
        ),
        CheckConstraint(
            "operation_type IN ("
            "'SALE', "
            "'CREDIT', "
            "'REPAYMENT', "
            "'INVENTORY_ADJUSTMENT'"
            ")",
            name="ck_pending_operation_type",
        ),
        Index(
            "ix_pending_operations_store_status",
            "store_id",
            "status",
        ),
        Index(
            "ix_pending_operations_conversation",
            "store_id",
            "conversation_id",
        ),
        UniqueConstraint(
            "store_id",
            "id",
            name="uq_pending_operations_store_id_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    operation_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="CREATED",
    )

    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    confirmation_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    result_entity_type: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )

    result_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

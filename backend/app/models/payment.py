import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Payment(Base):
    __tablename__ = "payments"

    __table_args__ = (
        ForeignKeyConstraint(
            ["store_id", "sale_id"],
            ["sales.store_id", "sales.id"],
            ondelete="RESTRICT",
            name="fk_payments_store_sale",
        ),
        CheckConstraint(
            "amount_paise > 0",
            name="ck_payment_amount",
        ),
        CheckConstraint(
            "payment_method IN ('CASH', 'UPI', 'CARD', 'OTHER')",
            name="ck_payment_method",
        ),
        Index("ix_payments_store_created", "store_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )

    amount_paise: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    payment_method: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    reference_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
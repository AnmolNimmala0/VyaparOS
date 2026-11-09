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
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CustomerLedgerEntry(Base):
    __tablename__ = "customer_ledger_entries"

    __table_args__ = (
        ForeignKeyConstraint(
            ["store_id", "customer_id"],
            ["customers.store_id", "customers.id"],
            ondelete="CASCADE",
            name="fk_ledger_store_customer",
        ),
        CheckConstraint(
            """
            (entry_type IN ('CREDIT', 'REPAYMENT') AND amount_paise > 0)
            OR
            (entry_type IN ('ADJUSTMENT', 'REVERSAL') AND amount_paise != 0)
            """,
            name="ck_ledger_entry_amount",
        ),
        CheckConstraint(
            "entry_type IN ('CREDIT', 'REPAYMENT', 'ADJUSTMENT', 'REVERSAL')",
            name="ck_ledger_entry_type",
        ),
        Index(
            "ix_ledger_store_customer_created",
            "store_id",
            "customer_id",
            "created_at",
        ),
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
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )

    entry_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    # Stored in paise. For CREDIT and REPAYMENT, always positive.
    amount_paise: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    reference_type: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    note: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
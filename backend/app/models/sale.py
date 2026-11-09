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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Sale(Base):
    __tablename__ = "sales"

    __table_args__ = (
        UniqueConstraint(
            "store_id", "id",
            name="uq_sales_store_id_id",
        ),
        ForeignKeyConstraint(
            ["store_id", "customer_id"],
            ["customers.store_id", "customers.id"],
            ondelete="RESTRICT",
            name="fk_sales_store_customer",
        ),
        CheckConstraint(
            "total_amount_paise >= 0",
            name="ck_sales_total",
        ),
        CheckConstraint(
            "amount_paid_paise >= 0",
            name="ck_sales_paid",
        ),
        CheckConstraint(
            "amount_due_paise >= 0",
            name="ck_sales_due",
        ),
        CheckConstraint(
            "status IN ('COMPLETED', 'VOIDED')",
            name="ck_sales_status",
        ),
        Index("ix_sales_store_created", "store_id", "created_at"),
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
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="COMPLETED"
    )

    total_amount_paise: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    amount_paid_paise: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    amount_due_paise: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    note: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
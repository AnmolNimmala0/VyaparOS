import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    __table_args__ = (
        ForeignKeyConstraint(
            ["store_id", "product_id"],
            ["products.store_id", "products.id"],
            ondelete="CASCADE",
            name="fk_inventory_movement_store_product",
        ),
        Index(
            "ix_inventory_movements_store_product_created",
            "store_id",
            "product_id",
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
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )

    # Examples: OPENING, PURCHASE, SALE, RETURN, ADJUSTMENT, REVERSAL
    movement_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    # Positive means stock added; negative means stock removed.
    quantity_delta: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False
    )

    reference_type: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
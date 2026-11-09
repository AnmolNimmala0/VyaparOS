import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InventoryBalance(Base):
    __tablename__ = "inventory_balances"

    __table_args__ = (
        ForeignKeyConstraint(
            ["store_id", "product_id"],
            ["products.store_id", "products.id"],
            ondelete="CASCADE",
            name="fk_inventory_balance_store_product",
        ),
        UniqueConstraint(
            "store_id", "product_id",
            name="uq_inventory_balance_store_product",
        ),
        CheckConstraint("quantity >= 0", name="ck_inventory_quantity"),
        CheckConstraint(
            "reorder_level >= 0", name="ck_inventory_reorder_level"
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

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal(0)
    )
    reorder_level: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal(0)
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
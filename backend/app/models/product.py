import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Product(Base):
    __tablename__ = "products"

    __table_args__ = (
        UniqueConstraint("store_id", "id", name="uq_products_store_id_id"),
        UniqueConstraint("store_id", "sku", name="uq_products_store_sku"),
        CheckConstraint("cost_price_paise >= 0", name="ck_products_cost_price"),
        CheckConstraint(
            "selling_price_paise >= 0",
            name="ck_products_selling_price",
        ),
        Index("ix_products_store_name", "store_id", "name"),
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

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(80), nullable=True)
    unit: Mapped[str] = mapped_column(
        String(30), nullable=False, default="piece"
    )

    cost_price_paise: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    selling_price_paise: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    is_active: Mapped[bool] = mapped_column(
        default=True, nullable=False
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
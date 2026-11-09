import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SaleItem(Base):
    __tablename__ = "sale_items"

    __table_args__ = (
        ForeignKeyConstraint(
            ["store_id", "sale_id"],
            ["sales.store_id", "sales.id"],
            ondelete="CASCADE",
            name="fk_sale_items_store_sale",
        ),
        ForeignKeyConstraint(
            ["store_id", "product_id"],
            ["products.store_id", "products.id"],
            ondelete="RESTRICT",
            name="fk_sale_items_store_product",
        ),
        CheckConstraint("quantity > 0", name="ck_sale_item_quantity"),
        CheckConstraint(
            "unit_price_paise >= 0",
            name="ck_sale_item_unit_price",
        ),
        CheckConstraint(
            "unit_cost_paise >= 0",
            name="ck_sale_item_unit_cost",
        ),
        CheckConstraint(
            "line_total_paise >= 0",
            name="ck_sale_item_line_total",
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
    sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False
    )

    unit_price_paise: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    unit_cost_paise: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    line_total_paise: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
import uuid

from sqlalchemy import (
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProductAlias(Base):
    __tablename__ = "product_aliases"

    __table_args__ = (
        ForeignKeyConstraint(
            ["store_id", "product_id"],
            ["products.store_id", "products.id"],
            ondelete="CASCADE",
            name="fk_product_aliases_store_product",
        ),
        UniqueConstraint(
            "store_id",
            "normalized_alias",
            name="uq_product_aliases_store_normalized",
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

    alias: Mapped[str] = mapped_column(String(150), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(
        String(150), nullable=False
    )
    language: Mapped[str] = mapped_column(
        String(20), nullable=False, default="hi"
    )
"""add pending operation execution result

Revision ID: f7a91c2d4e60
Revises: e651811e7ff1
"""

from alembic import op
import sqlalchemy as sa


revision = "f7a91c2d4e60"
down_revision = "e651811e7ff1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pending_operations",
        sa.Column(
            "result_entity_type",
            sa.String(length=40),
            nullable=True,
        ),
    )

    op.add_column(
        "pending_operations",
        sa.Column(
            "result_entity_id",
            sa.UUID(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "pending_operations",
        "result_entity_id",
    )

    op.drop_column(
        "pending_operations",
        "result_entity_type",
    )
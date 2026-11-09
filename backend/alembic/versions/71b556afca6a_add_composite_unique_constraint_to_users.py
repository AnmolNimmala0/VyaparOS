"""add composite unique constraint to users

Revision ID: 71b556afca6a
Revises: e651811e7ff1
Create Date: 2026-11-04 15:07:10.556703

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71b556afca6a'
down_revision: Union[str, Sequence[str], None] = '677c00cfd27f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None





def upgrade() -> None:
    op.create_unique_constraint(
        "uq_users_store_id_id",
        "users",
        ["store_id", "id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_users_store_id_id",
        "users",
        type_="unique",
    )

"""m4_billing

Revision ID: a1b2c3d4e5f6
Revises: 8fa9f3ea26c8
Create Date: 2026-06-15

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '8fa9f3ea26c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column(
        "plan", sa.String(10), nullable=False, server_default="'free'"
    ))
    op.add_column("users", sa.Column(
        "stripe_customer_id", sa.String(255), nullable=True
    ))
    op.create_check_constraint("ck_users_plan", "users", "plan IN ('free', 'pro')")


def downgrade() -> None:
    op.drop_constraint("ck_users_plan", "users", type_="check")
    op.drop_column("users", "stripe_customer_id")
    op.drop_column("users", "plan")

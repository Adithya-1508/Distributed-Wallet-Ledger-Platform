"""Add idempotency_key to transactions

Revision ID: a7b8c9d0e1f2
Revises: c3f9a1d72b40
Create Date: 2026-06-01 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'c3f9a1d72b40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'transactions',
        sa.Column('idempotency_key', sa.String(length=255), nullable=True),
    )
    # Unique index enforces "one transaction per key"; many NULLs allowed.
    op.create_index(
        op.f('ix_transactions_idempotency_key'),
        'transactions', ['idempotency_key'], unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_transactions_idempotency_key'), table_name='transactions'
    )
    op.drop_column('transactions', 'idempotency_key')

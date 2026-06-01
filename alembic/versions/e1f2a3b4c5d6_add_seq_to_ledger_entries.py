"""Add monotonic seq to ledger_entries

Gives the append-only ledger a strict insertion order independent of the
created_at timestamp (which ties for entries written in the same transaction).

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-06-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'ledger_entries',
        sa.Column('seq', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    )
    op.create_index(
        op.f('ix_ledger_entries_seq'), 'ledger_entries', ['seq'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_ledger_entries_seq'), table_name='ledger_entries')
    op.drop_column('ledger_entries', 'seq')

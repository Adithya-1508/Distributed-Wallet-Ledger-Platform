"""Create transaction_stats and processed_events tables

Revision ID: d0e1f2a3b4c5
Revises: b8c9d0e1f2a3
Create Date: 2026-06-02 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, Sequence[str], None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'transaction_stats',
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('count', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('total_amount', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.PrimaryKeyConstraint('currency', 'type'),
    )

    op.create_table(
        'processed_events',
        sa.Column('consumer', sa.String(length=50), nullable=False),
        sa.Column('transaction_id', sa.UUID(), nullable=False),
        sa.Column(
            'processed_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.PrimaryKeyConstraint('consumer', 'transaction_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('processed_events')
    op.drop_table('transaction_stats')

"""Create transactions and ledger_entries tables

Revision ID: c3f9a1d72b40
Revises: ace04db20b32
Create Date: 2026-06-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f9a1d72b40'
down_revision: Union[str, Sequence[str], None] = 'ace04db20b32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # transactions must exist before ledger_entries (FK dependency).
    op.create_table(
        'transactions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column(
            'type',
            sa.Enum(
                'DEPOSIT', 'TRANSFER', 'WITHDRAWAL',
                name='transaction_type', native_enum=False, length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            'status',
            sa.Enum(
                'PENDING', 'COMPLETED', 'FAILED',
                name='transaction_status', native_enum=False, length=20,
            ),
            nullable=False,
        ),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'ledger_entries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('transaction_id', sa.UUID(), nullable=False),
        sa.Column(
            'entry_type',
            sa.Enum(
                'CREDIT', 'DEBIT',
                name='entry_type', native_enum=False, length=10,
            ),
            nullable=False,
        ),
        sa.Column('amount', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('wallet_id', sa.UUID(), nullable=True),
        sa.Column('system_account', sa.String(length=50), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.CheckConstraint('amount > 0', name='ck_ledger_amount_positive'),
        sa.CheckConstraint(
            '(wallet_id IS NOT NULL)::int + (system_account IS NOT NULL)::int = 1',
            name='ck_ledger_exactly_one_side',
        ),
        sa.ForeignKeyConstraint(
            ['transaction_id'], ['transactions.id'], ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['wallet_id'], ['wallets.id'], ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_ledger_entries_transaction_id'),
        'ledger_entries', ['transaction_id'], unique=False,
    )
    op.create_index(
        op.f('ix_ledger_entries_wallet_id'),
        'ledger_entries', ['wallet_id'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_ledger_entries_wallet_id'), table_name='ledger_entries')
    op.drop_index(
        op.f('ix_ledger_entries_transaction_id'), table_name='ledger_entries'
    )
    op.drop_table('ledger_entries')
    op.drop_table('transactions')

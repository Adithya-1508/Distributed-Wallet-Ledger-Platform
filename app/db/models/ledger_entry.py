import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EntryType(str, enum.Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class LedgerEntry(Base):
    """One leg of a double-entry transaction.

    Money direction lives ONLY in `entry_type` (CREDIT/DEBIT); `amount` is
    always positive. Every entry points at exactly one side: either a user
    `wallet_id` or a named `system_account` (e.g. EXTERNAL_FUNDING) -- never
    both, never neither. Entries are immutable (FK uses RESTRICT).
    """

    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_ledger_amount_positive"),
        CheckConstraint(
            "(wallet_id IS NOT NULL)::int + (system_account IS NOT NULL)::int = 1",
            name="ck_ledger_exactly_one_side",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    entry_type: Mapped[EntryType] = mapped_column(
        Enum(EntryType, name="entry_type", native_enum=False, length=10),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    wallet_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    system_account: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

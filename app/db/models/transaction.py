import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TransactionType(str, enum.Enum):
    DEPOSIT = "DEPOSIT"
    TRANSFER = "TRANSFER"
    WITHDRAWAL = "WITHDRAWAL"


class TransactionStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Transaction(Base):
    """A single business operation (deposit / transfer / withdrawal).

    The transaction is the *header*; the actual money movement lives in the
    balanced pair(s) of LedgerEntry rows that reference it.
    """

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # native_enum=False -> stored as VARCHAR + CHECK (no native PG type to
    # fight with on autogenerate / re-runs). Still type-safe in Python.
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transaction_type", native_enum=False, length=20),
        nullable=False,
    )
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(
            TransactionStatus,
            name="transaction_status",
            native_enum=False,
            length=20,
        ),
        nullable=False,
        default=TransactionStatus.PENDING,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

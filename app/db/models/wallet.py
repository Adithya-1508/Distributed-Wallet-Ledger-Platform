import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, CheckConstraint, DateTime, ForeignKey, String,
    UniqueConstraint, func
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        UniqueConstraint("user_id", "currency", name="uq_wallet_user_currency"),
        CheckConstraint("available_balance >= 0", name="ck_wallet_available_nonneg"),
        CheckConstraint("locked_balance >= 0", name="ck_wallet_locked_nonneg"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    available_balance : Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    locked_balance : Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")

    created_at : Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at : Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),onupdate= func.now(), nullable=False)

    
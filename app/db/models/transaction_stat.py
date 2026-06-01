from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TransactionStat(Base):
    """Running analytics rollup, one row per (currency, transaction type).

    Maintained incrementally by the analytics consumer as transaction events
    arrive. Natural composite key (currency, type) -- no surrogate id needed.
    """

    __tablename__ = "transaction_stats"

    currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    type: Mapped[str] = mapped_column(String(20), primary_key=True)
    count: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    total_amount: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

import uuid
from datetime import datetime

from pydantic import BaseModel


class TransactionHistoryItem(BaseModel):
    transaction_id: uuid.UUID
    entry_type: str  # CREDIT / DEBIT, from the wallet's point of view
    amount: int
    currency: str
    created_at: datetime


class TransactionHistory(BaseModel):
    items: list[TransactionHistoryItem]
    limit: int
    offset: int

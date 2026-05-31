import uuid
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

class WalletCreate(BaseModel):
    currency : str = Field(min_length=3, max_length=3)


class WalletRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    currency: str
    available_balance: int
    locked_balance: int
    created_at: datetime


class BalanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id : uuid.UUID
    currency: str
    available_balance: int
    locked_balance: int
    updated_at:datetime




import uuid

from pydantic import BaseModel, Field


class DepositRequest(BaseModel):
    amount: int = Field(gt=0)  # minor units (e.g. paise); must be > 0 else 422
    currency: str = Field(min_length=3, max_length=3)


class DepositResponse(BaseModel):
    transaction_id: uuid.UUID
    available_balance: int
    currency: str

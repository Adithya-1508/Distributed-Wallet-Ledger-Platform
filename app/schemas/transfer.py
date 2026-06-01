import uuid

from pydantic import BaseModel, Field


class TransferRequest(BaseModel):
    recipient_wallet_id: uuid.UUID
    amount: int = Field(gt=0)  # minor units; must be > 0 else 422
    currency: str = Field(min_length=3, max_length=3)


class TransferResponse(BaseModel):
    transaction_id: uuid.UUID
    status: str
    available_balance: int  # the SENDER's balance after the transfer
    currency: str

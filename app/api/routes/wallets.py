import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.wallet import BalanceRead, WalletCreate, WalletRead
from app.services.wallet_service import (
    WalletAccessDeniedError,
    WalletAlreadyExistsError,
    WalletNotFoundError,
    WalletService,
)

router = APIRouter(prefix="/wallets", tags=["wallets"])


@router.post("", response_model=WalletRead, status_code=status.HTTP_201_CREATED)
def create_wallet(
    data: WalletCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WalletRead:
    try:
        return WalletService(db).create_wallet(owner_id=current_user.id, data=data)
    except WalletAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a wallet in this currency.",
        )


@router.get("/{wallet_id}/balance", response_model=BalanceRead)
def get_balance(
    wallet_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BalanceRead:
    try:
        return WalletService(db).get_balance(
            wallet_id=wallet_id, requester_id=current_user.id
        )
    except (WalletNotFoundError, WalletAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found."
        )
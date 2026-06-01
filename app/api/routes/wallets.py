import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.deposit import DepositRequest, DepositResponse
from app.schemas.transfer import TransferRequest, TransferResponse
from app.schemas.wallet import BalanceRead, WalletCreate, WalletRead
from app.schemas.withdrawal import WithdrawalRequest, WithdrawalResponse
from app.services.ledger_service import (
    CurrencyMismatchError,
    InsufficientFundsError,
    LedgerService,
    RecipientNotFoundError,
    SameWalletTransferError,
)
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


@router.post("/{wallet_id}/deposit", response_model=DepositResponse)
def deposit(
    wallet_id: uuid.UUID,
    data: DepositRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DepositResponse:
    try:
        txn, wallet = LedgerService(db).deposit(
            wallet_id=wallet_id,
            requester_id=current_user.id,
            data=data,
        )
    except (WalletNotFoundError, WalletAccessDeniedError):
        # Same 404 for "missing" and "not yours" -- don't leak existence.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found."
        )
    except CurrencyMismatchError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Deposit currency does not match the wallet.",
        )

    return DepositResponse(
        transaction_id=txn.id,
        available_balance=wallet.available_balance,
        currency=wallet.currency,
    )


@router.post("/{wallet_id}/transfer", response_model=TransferResponse)
def transfer(
    wallet_id: uuid.UUID,
    data: TransferRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransferResponse:
    try:
        txn, sender = LedgerService(db).transfer(
            sender_wallet_id=wallet_id,
            requester_id=current_user.id,
            data=data,
            idempotency_key=idempotency_key,
        )
    except (WalletNotFoundError, WalletAccessDeniedError):
        # Same 404 for "missing" and "not yours" -- don't leak existence.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found."
        )
    except RecipientNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient wallet not found.",
        )
    except CurrencyMismatchError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sender and recipient currencies must match.",
        )
    except SameWalletTransferError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot transfer to the same wallet.",
        )
    except InsufficientFundsError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Insufficient funds.",
        )

    return TransferResponse(
        transaction_id=txn.id,
        status=txn.status.value,
        available_balance=sender.available_balance,
        currency=sender.currency,
    )


@router.post("/{wallet_id}/withdraw", response_model=WithdrawalResponse)
def withdraw(
    wallet_id: uuid.UUID,
    data: WithdrawalRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WithdrawalResponse:
    try:
        txn, wallet = LedgerService(db).withdraw(
            wallet_id=wallet_id,
            requester_id=current_user.id,
            data=data,
            idempotency_key=idempotency_key,
        )
    except (WalletNotFoundError, WalletAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found."
        )
    except CurrencyMismatchError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Withdrawal currency does not match the wallet.",
        )
    except InsufficientFundsError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Insufficient funds.",
        )

    return WithdrawalResponse(
        transaction_id=txn.id,
        status=txn.status.value,
        available_balance=wallet.available_balance,
        currency=wallet.currency,
    )
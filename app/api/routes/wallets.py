import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.cache.deps import get_balance_cache
from app.cache.redis_cache import BalanceCache
from app.db.models.user import User
from app.db.session import get_db
from app.repositories.ledger_repo import LedgerRepository
from app.repositories.wallet_repo import WalletRepository
from app.schemas.deposit import DepositRequest, DepositResponse
from app.schemas.history import TransactionHistory, TransactionHistoryItem
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
    cache: BalanceCache = Depends(get_balance_cache),
) -> BalanceRead:
    # Cache stores user_id too, so a hit can enforce ownership without the DB
    # (never serve one user's cached balance to another).
    cached = cache.get(wallet_id)
    if cached is not None:
        if cached["user_id"] != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found."
            )
        return BalanceRead(
            id=cached["id"],
            currency=cached["currency"],
            available_balance=cached["available_balance"],
            locked_balance=cached["locked_balance"],
            updated_at=cached["updated_at"],
        )

    try:
        wallet = WalletService(db).get_balance(
            wallet_id=wallet_id, requester_id=current_user.id
        )
    except (WalletNotFoundError, WalletAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found."
        )

    cache.set(
        wallet_id,
        {
            "id": str(wallet.id),
            "user_id": str(wallet.user_id),
            "currency": wallet.currency,
            "available_balance": wallet.available_balance,
            "locked_balance": wallet.locked_balance,
            "updated_at": wallet.updated_at.isoformat(),
        },
    )
    return wallet


@router.get("/{wallet_id}/transactions", response_model=TransactionHistory)
def list_transactions(
    wallet_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionHistory:
    # Ownership: only the wallet's owner can read its statement.
    wallet = WalletRepository(db).get_by_id(wallet_id)
    if wallet is None or wallet.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found."
        )

    entries = LedgerRepository(db).get_entries_for_wallet(
        wallet_id, limit=limit, offset=offset
    )
    return TransactionHistory(
        items=[
            TransactionHistoryItem(
                transaction_id=e.transaction_id,
                entry_type=e.entry_type.value,
                amount=e.amount,
                currency=e.currency,
                created_at=e.created_at,
            )
            for e in entries
        ],
        limit=limit,
        offset=offset,
    )


@router.post("/{wallet_id}/deposit", response_model=DepositResponse)
def deposit(
    wallet_id: uuid.UUID,
    data: DepositRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    cache: BalanceCache = Depends(get_balance_cache),
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

    cache.invalidate(wallet_id)  # balance changed -> bust the cache
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
    cache: BalanceCache = Depends(get_balance_cache),
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

    # both balances moved -> bust both
    cache.invalidate(wallet_id, data.recipient_wallet_id)
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
    cache: BalanceCache = Depends(get_balance_cache),
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

    cache.invalidate(wallet_id)  # balance changed -> bust the cache
    return WithdrawalResponse(
        transaction_id=txn.id,
        status=txn.status.value,
        available_balance=wallet.available_balance,
        currency=wallet.currency,
    )
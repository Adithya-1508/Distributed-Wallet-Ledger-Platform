import uuid
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.wallet import Wallet
from app.repositories.wallet_repo import WalletRepository
from app.schemas.wallet import WalletCreate


class WalletAlreadyExistsError(Exception):
    """User already has a wallet in this currency"""


class WalletNotFoundError(Exception):
    """No such Wallet found"""

class WalletAccessDeniedError(Exception):
    """Wallet exists but is not owned by the requester"""


class WalletService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.wallets = WalletRepository(db)

    def create_wallet(self, *, owner_id: uuid.UUID, data:WalletCreate) -> Wallet:
        currency = data.currency.upper()
        if self.wallets.get_by_user_and_currency(owner_id, currency) is not None:
            raise WalletAlreadyExistsError(currency)

        wallet = self.wallets.create(user_id=owner_id, currency=currency)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise WalletAlreadyExistsError(currency) from exc

        self.db.refresh(wallet)
        return wallet

    def get_balance(self, *, wallet_id: uuid.UUID, requester_id: uuid.UUID) -> Wallet:
        wallet = self.wallets.get_by_id(wallet_id)
        if wallet is None:
            raise WalletNotFoundError(wallet_id)
        if wallet.user_id != requester_id:
            raise WalletAccessDeniedError(wallet_id)
        return wallet    

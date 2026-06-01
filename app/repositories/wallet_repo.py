import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Wallet


class WalletRepository:
    def __init__(self, db:Session) -> None:
        self.db = db


    def create(self, *, user_id: uuid.UUID, currency: str) -> Wallet:
        wallet = Wallet(user_id=user_id,currency=currency)
        self.db.add(wallet)
        self.db.flush()
        self.db.refresh(wallet)
        return wallet

    def get_by_id(self, wallet_id: uuid.UUID) -> Wallet | None:
        return self.db.get(Wallet,wallet_id)


    def get_with_lock(self, wallet_id: uuid.UUID) -> Wallet | None:
        """SELECT ... FOR UPDATE. Holds a row lock until the surrounding
        transaction commits, so concurrent writes to the same wallet serialise.
        """
        return self.db.scalar(
            select(Wallet).where(Wallet.id == wallet_id).with_for_update()
        )


    def get_for_update_ordered(
        self, wallet_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, "Wallet | None"]:
        """Lock several wallet rows FOR UPDATE in a deterministic order.

        Locking always in ascending id order means two transfers in opposite
        directions (A->B and B->A) can never each hold one lock while waiting
        for the other -- no circular wait, so no deadlock. Missing ids map to
        None (no row to lock).
        """
        result: dict[uuid.UUID, "Wallet | None"] = {}
        for wallet_id in sorted(set(wallet_ids)):
            result[wallet_id] = self.db.scalar(
                select(Wallet).where(Wallet.id == wallet_id).with_for_update()
            )
        return result


    def get_by_user_and_currency(self,user_id:uuid.UUID,currency:str) -> Wallet | None:
        return self.db.scalar(
            select(Wallet).where(
                Wallet.user_id == user_id, Wallet.currency == currency
            )
        ) 
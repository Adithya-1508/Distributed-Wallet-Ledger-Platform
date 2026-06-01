#This is the model registry. Anything imported here gets registered on Base.metadata

from app.db.models.user import User
from app.db.models.wallet import Wallet
from app.db.models.transaction import Transaction
from app.db.models.ledger_entry import LedgerEntry
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User

class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, name:str, email:str, password_hash:str) -> User:
        user = User(name= name, email=email,password_hash=password_hash)
        self.db.add(user)
        self.db.flush() # Assigns the uuid and stays inside the transaction
        self.db.refresh(user)
        return user

    def get_by_email(self, email:str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def get_by_id(self, id:uuid.UUID) -> User | None:
        return self.db.scalar(select(User).where(User.id == id))                
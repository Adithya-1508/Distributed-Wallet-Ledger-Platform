from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.security import hash_password, verify_password
from app.db.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserCreate


class EmailAlreadyExistsError(Exception):
    """Raised when registering an email that already exists."""


class UserService:
    def __init__(self,db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)

    def register(self, data: UserCreate) -> User:
        if self.users.get_by_email(data.email) is not None:
            raise EmailAlreadyExistsError(data.email)


        user = self.users.create(
            name = data.name,
            email = data.email,
            password_hash= hash_password(data.password), 
        )

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise EmailAlreadyExistsError(data.email) from exc

        self.db.refresh(user)
        return user           


    def authenticate(self, email: str, password:str) -> User | None:
        user = self.users.get_by_email(email)
        if user is None:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user        
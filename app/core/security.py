#  JWT Implemenation

#Encoding

from pygments.token import Error
from datetime import datetime, timedelta, timezone
from pwdlib import PasswordHash
import jwt

from app.core.config import settings

_hasher = PasswordHash.recommended()

def hash_password(password : str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) ->  bool:
    return _hasher.verify(password, password_hash)

def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    """Creates an access token with the given subject and expiry time."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expiry_minutes
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret,algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret,algorithms=[settings.jwt_algorithm]
        )
        return payload.get("sub")
    except jwt.PyJWTError:
        return None    


import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models.user import User
from app.db.session import get_db
from app.repositories.user_repo import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

def get_current_user(token : str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exc = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED,
        detail = "Could not validate credentials",
        headers = {"WWW-Authenticate": "Bearer"} 
    )

    subject = decode_access_token(token)
    if subject is None:
        raise credentials_exc
    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise credentials_exc


    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise credentials_exc

    return user            
    
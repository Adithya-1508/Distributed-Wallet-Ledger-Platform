from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.schemas.auth import Token
from app.services.user_service import UserService


router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=Token)
def login (form : OAuth2PasswordRequestForm = Depends (),db : Session = Depends(get_db)) -> Token:
    user = UserService(db).authenticate(form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Incorrect email or password",
            headers = {"WWW-Authenticate" : "Bearer"}
        )

    return Token(access_token=create_access_token(subject=str(user.id)))    



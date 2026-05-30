from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.user import UserCreate, UserRead
from app.services.user_service import EmailAlreadyExistsError, UserService

from fastapi import Depends
from app.api.deps import get_current_user
from app.db.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(data: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    service = UserService(db)
    try:
        return service.register(data)
    except EmailAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists",)


@router.get("/me", response_model=UserRead)
def read_me(current_user: User = Depends(get_current_user))-> UserRead:
    return current_user        
    
    
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.user import UserRead
from app.services.user_service import get_user_by_session_token


router = APIRouter(prefix="/users", tags=["users"])
bearer = HTTPBearer(auto_error=False)


@router.get("/me", response_model=UserRead)
def read_current_user(
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> UserRead:
    user = get_user_by_session_token(db, credentials.credentials) if credentials else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return UserRead.model_validate(user)

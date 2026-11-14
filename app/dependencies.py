from typing import Annotated

from fastapi import Depends, HTTPException, Path, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.common import MAX_BIGINT
from app.services.user_service import get_user_by_session_token


Database = Annotated[Session, Depends(get_db)]
PathId = Annotated[int, Path(gt=0, le=MAX_BIGINT)]
bearer = HTTPBearer(auto_error=False)


def get_current_user(
    db: Database,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    user = get_user_by_session_token(db, credentials.credentials) if credentials else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator required")
    return user


Administrator = Annotated[User, Depends(require_admin)]


class Pagination(BaseModel):
    offset: int = Field(default=0, ge=0, le=MAX_BIGINT)
    limit: int = Field(default=20, ge=1, le=100)


Page = Annotated[Pagination, Query()]

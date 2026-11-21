from typing import Annotated

from fastapi import Depends, Path, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import ForbiddenError, UnauthorizedError
from app.models import User
from app.schemas.common import MAX_BIGINT
from app.schemas.pagination import ProjectPagination, TaskPagination, UserPagination
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
        raise UnauthorizedError()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise ForbiddenError("Administrator required")
    return user


Administrator = Annotated[User, Depends(require_admin)]


UserPage = Annotated[UserPagination, Query()]
ProjectPage = Annotated[ProjectPagination, Query()]
TaskPage = Annotated[TaskPagination, Query()]

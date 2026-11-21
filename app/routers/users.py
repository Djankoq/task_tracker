from fastapi import APIRouter
from sqlalchemy import select

from app.dependencies import Administrator, CurrentUser, Database, UserPage
from app.models import User
from app.schemas.common import PageResponse
from app.schemas.user import UserRead
from app.services.crud import CRUD_ERRORS
from app.services.pagination import paginate


router = APIRouter(prefix="/users", tags=["users"], responses=CRUD_ERRORS)
SORT_COLUMNS = {
    "user_id": User.user_id, "login": User.login, "display_name": User.display_name,
    "name": User.display_name, "is_admin": User.is_admin,
}


@router.get("/")
def list_users(db: Database, _: Administrator, page: UserPage) -> PageResponse[UserRead]:
    return paginate(db, select(User), page, SORT_COLUMNS, User.user_id, UserRead)


@router.get("/me", response_model=UserRead)
def read_current_user(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)

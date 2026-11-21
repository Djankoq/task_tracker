from fastapi import APIRouter
from sqlalchemy import select

from app.dependencies import Administrator, CurrentUser, Database, UserPage
from app.models import ProjectMember, User
from app.services.search import search_text
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
    statement = select(User)
    if page.is_active is not None:
        statement = statement.where(User.is_active == page.is_active)
    if page.is_admin is not None:
        statement = statement.where(User.is_admin == page.is_admin)
    if page.project_id is not None:
        members = select(ProjectMember.user_id).where(
            ProjectMember.project_id == page.project_id, ProjectMember.removed_at.is_(None),
        )
        statement = statement.where(User.user_id.in_(members))
    statement = search_text(statement, page.search, User.login, User.display_name)
    return paginate(db, statement, page, SORT_COLUMNS, User.user_id, UserRead)


@router.get("/me", response_model=UserRead)
def read_current_user(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)

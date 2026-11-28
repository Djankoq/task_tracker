from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.dependencies import Administrator, CurrentUser, Database, PathId, UserPage
from app.exceptions import ForbiddenError, NotFoundError
from app.models import ProjectMember, User
from app.services.search import search_text
from app.schemas.common import PageResponse
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.crud import CRUD_ERRORS, DELETE_CONFLICT, write_transaction
from app.services.user_service import hash_password
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
    if page.user_id_min is not None:
        statement = statement.where(User.user_id >= page.user_id_min)
    if page.user_id_max is not None:
        statement = statement.where(User.user_id <= page.user_id_max)
    statement = search_text(statement, page.search, User.login, User.display_name)
    return paginate(db, statement, page, SORT_COLUMNS, User.user_id, UserRead)


@router.get("/me", response_model=UserRead)
def read_current_user(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


def get_user(user_id: int, db: Database, *, lock: bool = False) -> User:
    statement = select(User).where(User.user_id == user_id)
    if lock:
        statement = statement.with_for_update()
    user = db.scalar(statement)
    if user is None:
        raise NotFoundError("User not found")
    return user


@router.get("/{user_id}")
def read_user(user_id: PathId, db: Database, _: Administrator) -> UserRead:
    return UserRead.model_validate(get_user(user_id, db))


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Database, _: Administrator) -> UserRead:
    with write_transaction(db):
        user = User(
            login=payload.login, display_name=payload.display_name,
            is_admin=payload.is_admin, password_hash=hash_password(payload.password.get_secret_value()),
        )
        db.add(user)
        db.flush()
        result = UserRead.model_validate(user)
    return result


@router.put("/{user_id}")
def update_user(user_id: PathId, payload: UserUpdate, db: Database, actor: Administrator) -> UserRead:
    if user_id == actor.user_id and not payload.is_admin:
        raise ForbiddenError("You cannot remove your own administrator role")
    with write_transaction(db):
        user = get_user(user_id, db, lock=True)
        user.login = payload.login
        user.display_name = payload.display_name
        user.is_admin = payload.is_admin
        if payload.password is not None:
            user.password_hash = hash_password(payload.password.get_secret_value())
        db.flush()
        result = UserRead.model_validate(user)
    return result


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, responses=DELETE_CONFLICT)
def delete_user(user_id: PathId, db: Database, actor: Administrator) -> Response:
    if user_id == actor.user_id:
        raise ForbiddenError("You cannot delete your own account")
    with write_transaction(db, deleting=True):
        user = get_user(user_id, db, lock=True)
        db.execute(User.__table__.delete().where(User.user_id == user.user_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

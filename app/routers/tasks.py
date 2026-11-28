from collections.abc import Mapping

from fastapi import APIRouter, Response, status
from sqlalchemy import func, select

from app.dependencies import CurrentUser, Database, TaskPage, PathId
from app.exceptions import ForbiddenError, NotFoundError
from app.models import Project, Task
from app.schemas.task import TaskCreate, TaskPatch, TaskRead, TaskReplace
from app.schemas.common import PageResponse
from app.services.pagination import paginate
from app.services.search import search_text
from app.services.crud import (
    CRUD_ERRORS,
    DELETE_CONFLICT,
    project_role,
    visible_projects,
    write_transaction,
)


router = APIRouter(prefix="/tasks", tags=["tasks"], responses=CRUD_ERRORS)
SORT_COLUMNS = {
    "task_id": Task.task_id, "project_id": Task.project_id, "assignee_id": Task.assignee_id,
    "title": Task.title, "due_at": Task.due_at, "priority": Task.priority, "status": Task.status,
}


def get_task(task_id: int, db: Database, user: CurrentUser, *, lock: bool = False) -> Task:
    statement = select(Task).where(Task.task_id == task_id)
    if not user.is_admin:
        statement = statement.where(Task.project_id.in_(visible_projects(user)))
    if lock:
        statement = statement.with_for_update()
    task = db.scalar(statement)
    if task is None:
        raise NotFoundError("Task not found")
    return task


def set_task_actor(db: Database, user: CurrentUser, review_reason: str | None = None) -> None:
    db.execute(select(func.set_config("task_tracker.actor_id", str(user.user_id), True)))
    if review_reason is not None:
        db.execute(select(func.set_config("task_tracker.review_reason", review_reason, True)))


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: Database, user: CurrentUser) -> TaskRead:
    with write_transaction(db):
        if db.get(Project, payload.project_id) is None:
            raise NotFoundError("Project not found")
        if project_role(db, payload.project_id, user.user_id) != "manager":
            raise ForbiddenError("Project manager required")
        set_task_actor(db, user)
        task = Task(**payload.model_dump())
        db.add(task)
        db.flush()
        result = TaskRead.model_validate(task)
    return result


@router.get("/")
def list_tasks(db: Database, user: CurrentUser, page: TaskPage) -> PageResponse[TaskRead]:
    statement = select(Task)
    if not user.is_admin:
        statement = statement.where(Task.project_id.in_(visible_projects(user)))
    for field in ("project_id", "assignee_id", "status", "priority"):
        value = getattr(page, field)
        if value is not None:
            statement = statement.where(getattr(Task, field) == value)
    if page.task_id_min is not None:
        statement = statement.where(Task.task_id >= page.task_id_min)
    if page.task_id_max is not None:
        statement = statement.where(Task.task_id <= page.task_id_max)
    if page.due_from is not None:
        statement = statement.where(Task.due_at >= page.due_from)
    if page.due_to is not None:
        statement = statement.where(Task.due_at <= page.due_to)
    statement = search_text(statement, page.search, Task.title, Task.description)
    return paginate(db, statement, page, SORT_COLUMNS, Task.task_id, TaskRead)


@router.get("/{task_id}")
def read_task(task_id: PathId, db: Database, user: CurrentUser) -> TaskRead:
    return TaskRead.model_validate(get_task(task_id, db, user))


def update_task(task_id: int, payload: Mapping[str, object], db: Database, user: CurrentUser) -> TaskRead:
    with write_transaction(db):
        task = get_task(task_id, db, user, lock=True)
        role = project_role(db, task.project_id, user.user_id)
        if role != "manager" and (role != "executor" or user.user_id != task.assignee_id):
            raise ForbiddenError("This user cannot edit the task")
        changes = dict(payload)
        set_task_actor(db, user, changes.pop("review_reason", None))
        for field, value in changes.items():
            setattr(task, field, value)
        db.flush()
        result = TaskRead.model_validate(task)
    return result


@router.put("/{task_id}")
def replace_task(task_id: PathId, payload: TaskReplace, db: Database, user: CurrentUser) -> TaskRead:
    return update_task(task_id, payload.model_dump(), db, user)


@router.patch("/{task_id}")
def patch_task(task_id: PathId, payload: TaskPatch, db: Database, user: CurrentUser) -> TaskRead:
    return update_task(task_id, payload.model_dump(exclude_unset=True), db, user)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT, responses=DELETE_CONFLICT)
def delete_task(task_id: PathId, db: Database, user: CurrentUser) -> Response:
    with write_transaction(db, deleting=True):
        task = get_task(task_id, db, user, lock=True)
        if project_role(db, task.project_id, user.user_id) != "manager":
            raise ForbiddenError("Project manager required")
        db.execute(Task.__table__.delete().where(Task.task_id == task.task_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

from collections.abc import Mapping

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select

from app.dependencies import CurrentUser, Database, Page, PathId
from app.models import Project, Task
from app.schemas.task import TaskCreate, TaskPatch, TaskRead, TaskReplace
from app.services.crud import (
    CRUD_ERRORS,
    DELETE_CONFLICT,
    project_role,
    visible_projects,
    write_transaction,
)


router = APIRouter(prefix="/tasks", tags=["tasks"], responses=CRUD_ERRORS)


def get_task(task_id: int, db: Database, user: CurrentUser, *, lock: bool = False) -> Task:
    statement = select(Task).where(Task.task_id == task_id)
    if not user.is_admin:
        statement = statement.where(Task.project_id.in_(visible_projects(user)))
    if lock:
        statement = statement.with_for_update()
    task = db.scalar(statement)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return task


def set_task_actor(db: Database, user: CurrentUser, review_reason: str | None = None) -> None:
    db.execute(select(func.set_config("task_tracker.actor_id", str(user.user_id), True)))
    if review_reason is not None:
        db.execute(select(func.set_config("task_tracker.review_reason", review_reason, True)))


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: Database, user: CurrentUser) -> TaskRead:
    with write_transaction(db):
        if db.get(Project, payload.project_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
        if project_role(db, payload.project_id, user.user_id) != "manager":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Project manager required")
        set_task_actor(db, user)
        task = Task(**payload.model_dump())
        db.add(task)
        db.flush()
        result = TaskRead.model_validate(task)
    return result


@router.get("/")
def list_tasks(db: Database, user: CurrentUser, page: Page) -> list[TaskRead]:
    statement = select(Task).order_by(Task.task_id).offset(page.offset).limit(page.limit)
    if not user.is_admin:
        statement = statement.where(Task.project_id.in_(visible_projects(user)))
    return [TaskRead.model_validate(task) for task in db.scalars(statement)]


@router.get("/{task_id}")
def read_task(task_id: PathId, db: Database, user: CurrentUser) -> TaskRead:
    return TaskRead.model_validate(get_task(task_id, db, user))


def update_task(task_id: int, payload: Mapping[str, object], db: Database, user: CurrentUser) -> TaskRead:
    with write_transaction(db):
        task = get_task(task_id, db, user, lock=True)
        role = project_role(db, task.project_id, user.user_id)
        if role != "manager" and (role != "executor" or user.user_id != task.assignee_id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "This user cannot edit the task")
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
    return update_task(task_id, payload, db, user)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT, responses=DELETE_CONFLICT)
def delete_task(task_id: PathId, db: Database, user: CurrentUser) -> Response:
    with write_transaction(db, deleting=True):
        task = get_task(task_id, db, user, lock=True)
        if project_role(db, task.project_id, user.user_id) != "manager":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Project manager required")
        db.execute(Task.__table__.delete().where(Task.task_id == task.task_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

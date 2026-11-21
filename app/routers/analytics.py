from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.dependencies import CurrentUser, Database
from app.models import Project, Task, User
from app.schemas.task import TaskStatus
from app.services.crud import CRUD_ERRORS, visible_projects


router = APIRouter(tags=["analytics"], responses=CRUD_ERRORS)


class ProjectSummary(BaseModel):
    total_projects: int
    total_tasks: int
    avg_tasks_per_project: float | None


class StatusCount(BaseModel):
    status: TaskStatus
    task_count: int


class RankedProject(BaseModel):
    project_id: int
    name: str
    task_count: int


def project_workloads(user: User):
    statement = (
        select(Project.project_id, Project.name, func.count(Task.task_id).label("task_count"))
        .outerjoin(Project.tasks)
        .group_by(Project.project_id, Project.name)
    )
    if not user.is_admin:
        statement = statement.where(Project.project_id.in_(visible_projects(user)))
    return statement.subquery()


@router.get("/stats/summary")
def summary(db: Database, user: CurrentUser) -> ProjectSummary:
    projects = project_workloads(user)
    statement = select(
        func.count().label("total_projects"),
        func.coalesce(func.sum(projects.c.task_count), 0).label("total_tasks"),
        func.avg(projects.c.task_count).label("avg_tasks_per_project"),
    ).select_from(projects)
    return ProjectSummary(**db.execute(statement).mappings().one())


@router.get("/stats/tasks-by-status")
def tasks_by_status(db: Database, user: CurrentUser) -> list[StatusCount]:
    statement = select(Task.status, func.count().label("task_count")).group_by(Task.status)
    if not user.is_admin:
        statement = statement.where(Task.project_id.in_(visible_projects(user)))
    return [StatusCount(**row) for row in db.execute(statement.order_by(Task.status)).mappings()]


@router.get("/reports/top-projects")
def top_projects(
    db: Database, user: CurrentUser, limit: Annotated[int, Query(ge=1, le=100)] = 5,
) -> list[RankedProject]:
    projects = project_workloads(user)
    statement = select(projects).order_by(projects.c.task_count.desc(), projects.c.project_id).limit(limit)
    return [RankedProject(**row) for row in db.execute(statement).mappings()]

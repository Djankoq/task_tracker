from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.dependencies import Administrator, CurrentUser, Database, Page, PathId
from app.models import Project
from app.schemas.project import ProjectCreate, ProjectPatch, ProjectRead, ProjectReplace
from app.services.crud import CRUD_ERRORS, DELETE_CONFLICT, visible_projects, write_transaction


router = APIRouter(prefix="/projects", tags=["projects"], responses=CRUD_ERRORS)


def get_project(project_id: int, db: Database, user: CurrentUser, *, lock: bool = False) -> Project:
    statement = select(Project).where(Project.project_id == project_id)
    if not user.is_admin:
        statement = statement.where(Project.project_id.in_(visible_projects(user)))
    if lock:
        statement = statement.with_for_update()
    project = db.scalar(statement)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Database, _: Administrator) -> ProjectRead:
    with write_transaction(db):
        project = Project(**payload.model_dump())
        db.add(project)
        db.flush()
        result = ProjectRead.model_validate(project)
    return result


@router.get("/")
def list_projects(db: Database, user: CurrentUser, page: Page) -> list[ProjectRead]:
    statement = select(Project).order_by(Project.project_id).offset(page.offset).limit(page.limit)
    if not user.is_admin:
        statement = statement.where(Project.project_id.in_(visible_projects(user)))
    return [ProjectRead.model_validate(project) for project in db.scalars(statement)]


@router.get("/{project_id}")
def read_project(project_id: PathId, db: Database, user: CurrentUser) -> ProjectRead:
    return ProjectRead.model_validate(get_project(project_id, db, user))


@router.put("/{project_id}")
def replace_project(
    project_id: PathId, payload: ProjectReplace, db: Database, user: Administrator
) -> ProjectRead:
    with write_transaction(db):
        project = get_project(project_id, db, user, lock=True)
        project.name = payload.name
        project.description = payload.description
        result = ProjectRead.model_validate(project)
    return result


@router.patch("/{project_id}")
def patch_project(
    project_id: PathId, payload: ProjectPatch, db: Database, user: Administrator
) -> ProjectRead:
    with write_transaction(db):
        project = get_project(project_id, db, user, lock=True)
        for field, value in payload.items():
            setattr(project, field, value)
        result = ProjectRead.model_validate(project)
    return result


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, responses=DELETE_CONFLICT)
def delete_project(project_id: PathId, db: Database, user: Administrator) -> Response:
    with write_transaction(db, deleting=True):
        project = get_project(project_id, db, user, lock=True)
        # A direct DELETE lets the database enforce its foreign keys without the ORM nulling them.
        db.execute(Project.__table__.delete().where(Project.project_id == project.project_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

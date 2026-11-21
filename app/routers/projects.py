from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.dependencies import Administrator, CurrentUser, Database, ProjectPage, PathId
from app.exceptions import NotFoundError
from app.models import Project, ProjectMember, User
from app.services.search import search_text
from app.schemas.project import ProjectCreate, ProjectMemberRead, ProjectPatch, ProjectRead, ProjectReplace
from app.schemas.common import PageResponse
from app.services.pagination import paginate
from app.services.crud import CRUD_ERRORS, DELETE_CONFLICT, visible_projects, write_transaction


router = APIRouter(prefix="/projects", tags=["projects"], responses=CRUD_ERRORS)
SORT_COLUMNS = {"project_id": Project.project_id, "name": Project.name, "description": Project.description}


def get_project(project_id: int, db: Database, user: CurrentUser, *, lock: bool = False) -> Project:
    statement = select(Project).where(Project.project_id == project_id)
    if not user.is_admin:
        statement = statement.where(Project.project_id.in_(visible_projects(user)))
    if lock:
        statement = statement.with_for_update()
    project = db.scalar(statement)
    if project is None:
        raise NotFoundError("Project not found")
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
def list_projects(db: Database, user: CurrentUser, page: ProjectPage) -> PageResponse[ProjectRead]:
    statement = select(Project)
    if not user.is_admin:
        statement = statement.where(Project.project_id.in_(visible_projects(user)))
    if page.name is not None:
        statement = statement.where(Project.name == page.name)
    if page.member_id is not None:
        members = select(ProjectMember.project_id).where(
            ProjectMember.user_id == page.member_id, ProjectMember.removed_at.is_(None),
        )
        statement = statement.where(Project.project_id.in_(members))
    if page.has_tasks is not None:
        has_tasks = Project.tasks.any()
        statement = statement.where(has_tasks if page.has_tasks else ~has_tasks)
    statement = search_text(statement, page.search, Project.name, Project.description)
    return paginate(db, statement, page, SORT_COLUMNS, Project.project_id, ProjectRead)


@router.get("/{project_id}")
def read_project(project_id: PathId, db: Database, user: CurrentUser) -> ProjectRead:
    return ProjectRead.model_validate(get_project(project_id, db, user))


@router.get("/{project_id}/members")
def list_project_members(project_id: PathId, db: Database, user: CurrentUser) -> list[ProjectMemberRead]:
    get_project(project_id, db, user)
    statement = (
        select(
            ProjectMember.project_id, ProjectMember.user_id, ProjectMember.role,
            ProjectMember.removed_at, User.login, User.display_name,
        )
        .join(User, User.user_id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id, ProjectMember.removed_at.is_(None))
        .order_by(ProjectMember.user_id)
    )
    return [ProjectMemberRead(**row) for row in db.execute(statement).mappings()]


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
        for field, value in payload.model_dump(exclude_unset=True).items():
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

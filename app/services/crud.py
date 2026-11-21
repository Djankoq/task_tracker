from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models import ProjectMember, User
from app.exceptions import ConflictError, ForbiddenError, ValidationError
from app.schemas.common import ErrorResponse


CRUD_ERRORS = {
    400: {"model": ErrorResponse, "description": "Invalid request data"},
    401: {"model": ErrorResponse, "description": "Invalid or expired session"},
    403: {"model": ErrorResponse, "description": "Insufficient permissions"},
    404: {"model": ErrorResponse, "description": "Record not found"},
    409: {"model": ErrorResponse, "description": "Record conflict"},
}
DELETE_CONFLICT = {409: {"model": ErrorResponse, "description": "Related records prevent deletion"}}


def visible_projects(user: User):
    return (
        select(ProjectMember.project_id)
        .where(ProjectMember.user_id == user.user_id, ProjectMember.removed_at.is_(None))
    )


def project_role(db: Session, project_id: int, user_id: int) -> str | None:
    statement = select(ProjectMember.role).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
        ProjectMember.removed_at.is_(None),
    )
    return db.scalar(statement.with_for_update(read=True))


@contextmanager
def write_transaction(db: Session, *, deleting: bool = False) -> Iterator[None]:
    try:
        yield
        db.commit()
    except DBAPIError as error:
        db.rollback()
        code = getattr(error.orig, "pgcode", None)
        if code == "23503" and deleting:
            raise ConflictError("Related records prevent deletion") from None
        if code == "23505":
            raise ConflictError("A record with these unique values already exists") from None
        if code == "23503":
            raise ValidationError("Invalid reference to a related record") from None
        if code == "23514":
            raise ValidationError(error.orig.diag.message_primary) from None
        if code == "42501":
            raise ForbiddenError("Insufficient permissions") from None
        raise
    except Exception:
        db.rollback()
        raise

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models import ProjectMember, User
from app.schemas.common import ApiError


CRUD_ERRORS = {
    400: {"model": ApiError, "description": "Invalid request data"},
    401: {"model": ApiError, "description": "Invalid or expired session"},
    403: {"model": ApiError, "description": "Insufficient permissions"},
    404: {"model": ApiError, "description": "Record not found"},
}
DELETE_CONFLICT = {409: {"model": ApiError, "description": "Related records prevent deletion"}}


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
            raise HTTPException(status.HTTP_409_CONFLICT, "Related records prevent deletion") from None
        if code == "23503":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid reference to a related record") from None
        if code == "23514":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, error.orig.diag.message_primary) from None
        if code == "42501":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions") from None
        raise

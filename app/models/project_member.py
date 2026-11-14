from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import project_role

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.task import Task
    from app.models.user import User


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = {"schema": "task_tracker"}

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("task_tracker.projects.project_id"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("task_tracker.users.user_id"), primary_key=True
    )
    role: Mapped[str] = mapped_column(project_role, nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")
    assigned_tasks: Mapped[list[Task]] = relationship(
        back_populates="assignee_membership", viewonly=True
    )

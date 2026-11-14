from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Identity, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.auth_session import AuthSession
    from app.models.project_member import ProjectMember
    from app.models.task_change import TaskChange
    from app.models.task_comment import TaskComment


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("btrim(display_name) <> ''"),
        CheckConstraint("btrim(password_hash) <> ''"),
        CheckConstraint("login <> '' AND login = lower(btrim(login))"),
        {"schema": "task_tracker"},
    )

    user_id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    login: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False, deferred=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    auth_sessions: Mapped[list[AuthSession]] = relationship(back_populates="user")
    memberships: Mapped[list[ProjectMember]] = relationship(back_populates="user")
    comments: Mapped[list[TaskComment]] = relationship(back_populates="author")
    changes: Mapped[list[TaskChange]] = relationship(
        back_populates="actor", foreign_keys="TaskChange.actor_id"
    )
    changes_as_old_assignee: Mapped[list[TaskChange]] = relationship(
        back_populates="old_assignee", foreign_keys="TaskChange.old_assignee_id"
    )
    changes_as_new_assignee: Mapped[list[TaskChange]] = relationship(
        back_populates="new_assignee", foreign_keys="TaskChange.new_assignee_id"
    )

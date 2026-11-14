from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Identity, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import task_priority, task_status

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.project_member import ProjectMember
    from app.models.task_change import TaskChange
    from app.models.task_comment import TaskComment


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "assignee_id"],
            ["task_tracker.project_members.project_id", "task_tracker.project_members.user_id"],
            name="tasks_project_assignee_fk",
        ),
        CheckConstraint("btrim(title) <> ''"),
        CheckConstraint("btrim(description) <> ''"),
        {"schema": "task_tracker"},
    )

    task_id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("task_tracker.projects.project_id"), nullable=False
    )
    assignee_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    priority: Mapped[str] = mapped_column(task_priority, nullable=False)
    status: Mapped[str] = mapped_column(task_status, nullable=False, server_default=text("'todo'"))

    project: Mapped[Project] = relationship(back_populates="tasks")
    # The composite FK shares project_id with Task.project. Write the assignee via assignee_id.
    assignee_membership: Mapped[ProjectMember] = relationship(
        back_populates="assigned_tasks", viewonly=True
    )
    comments: Mapped[list[TaskComment]] = relationship(back_populates="task")
    changes: Mapped[list[TaskChange]] = relationship(back_populates="task")

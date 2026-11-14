from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import task_priority, task_status

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


class TaskChange(Base):
    __tablename__ = "task_changes"
    __table_args__ = (
        CheckConstraint("(old_status IS NULL AND new_status IS NULL) OR (old_status <> new_status) IS TRUE"),
        CheckConstraint(
            "(old_assignee_id IS NULL AND new_assignee_id IS NULL) "
            "OR (old_assignee_id <> new_assignee_id) IS TRUE"
        ),
        CheckConstraint(
            "(old_priority IS NULL AND new_priority IS NULL) OR (old_priority <> new_priority) IS TRUE"
        ),
        CheckConstraint("(old_due_at IS NULL AND new_due_at IS NULL) OR (old_due_at <> new_due_at) IS TRUE"),
        CheckConstraint("num_nonnulls(old_status, old_assignee_id, old_priority, old_due_at) > 0"),
        {"schema": "task_tracker"},
    )

    change_id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    task_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("task_tracker.tasks.task_id"), nullable=False
    )
    actor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("task_tracker.users.user_id"), nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("clock_timestamp()")
    )
    old_status: Mapped[str | None] = mapped_column(task_status)
    new_status: Mapped[str | None] = mapped_column(task_status)
    old_assignee_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("task_tracker.users.user_id"))
    new_assignee_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("task_tracker.users.user_id"))
    old_priority: Mapped[str | None] = mapped_column(task_priority)
    new_priority: Mapped[str | None] = mapped_column(task_priority)
    old_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    new_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    task: Mapped[Task] = relationship(back_populates="changes")
    actor: Mapped[User] = relationship(back_populates="changes", foreign_keys=[actor_id])
    old_assignee: Mapped[User | None] = relationship(
        back_populates="changes_as_old_assignee", foreign_keys=[old_assignee_id]
    )
    new_assignee: Mapped[User | None] = relationship(
        back_populates="changes_as_new_assignee", foreign_keys=[new_assignee_id]
    )

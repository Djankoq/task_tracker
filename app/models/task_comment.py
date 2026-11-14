from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


class TaskComment(Base):
    __tablename__ = "task_comments"
    __table_args__ = (
        CheckConstraint(r"btrim(body, E' \t\n\r') <> ''"),
        {"schema": "task_tracker"},
    )

    comment_id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    task_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("task_tracker.tasks.task_id"), nullable=False
    )
    author_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("task_tracker.users.user_id"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("clock_timestamp()")
    )

    task: Mapped[Task] = relationship(back_populates="comments")
    author: Mapped[User] = relationship(back_populates="comments")

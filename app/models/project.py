from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, Identity, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.project_member import ProjectMember
    from app.models.task import Task


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (CheckConstraint("btrim(name) <> ''"), {"schema": "task_tracker"})

    project_id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))

    memberships: Mapped[list[ProjectMember]] = relationship(back_populates="project")
    tasks: Mapped[list[Task]] = relationship(back_populates="project")

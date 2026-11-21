from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import MAX_BIGINT, NonBlankText
from app.schemas.task import TaskPriority, TaskStatus


QueryId = Annotated[int, Field(gt=0, le=MAX_BIGINT)]


class Pagination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1, le=MAX_BIGINT)
    per_page: int = Field(default=10, ge=1, le=100)
    sort_order: Literal["asc", "desc"] = "asc"
    search: NonBlankText | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    @model_validator(mode="after")
    def valid_offset(self) -> Self:
        if self.offset > MAX_BIGINT:
            raise ValueError("Page offset exceeds the database integer range")
        return self


class UserPagination(Pagination):
    is_active: bool | None = None
    is_admin: bool | None = None
    project_id: QueryId | None = None
    sort_by: Literal["user_id", "login", "display_name", "name", "is_admin"] = "user_id"


class ProjectPagination(Pagination):
    name: NonBlankText | None = None
    member_id: QueryId | None = None
    has_tasks: bool | None = None
    sort_by: Literal["project_id", "name", "description"] = "project_id"


class TaskPagination(Pagination):
    project_id: QueryId | None = None
    assignee_id: QueryId | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_from: AwareDatetime | None = None
    due_to: AwareDatetime | None = None
    sort_by: Literal[
        "task_id", "project_id", "assignee_id", "title", "due_at", "priority", "status",
    ] = "task_id"

    @model_validator(mode="after")
    def valid_due_range(self) -> Self:
        if self.due_from and self.due_to and self.due_from > self.due_to:
            raise ValueError("due_from must be on or before due_to")
        return self

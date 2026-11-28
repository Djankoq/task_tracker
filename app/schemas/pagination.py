from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import MAX_BIGINT, NonBlankText
from app.schemas.task import TaskPriority, TaskStatus


QueryId = Annotated[int, Field(gt=0, le=MAX_BIGINT)]
QueryCount = Annotated[int, Field(ge=0, le=MAX_BIGINT)]


def validate_range(
    start: int | datetime | None, end: int | datetime | None, start_name: str, end_name: str
) -> None:
    if start is not None and end is not None and start > end:
        raise ValueError(f"{start_name} must be on or before {end_name}")


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
    user_id_min: QueryId | None = None
    user_id_max: QueryId | None = None
    sort_by: Literal["user_id", "login", "display_name", "name", "is_admin"] = "user_id"

    @model_validator(mode="after")
    def valid_user_id_range(self) -> Self:
        validate_range(self.user_id_min, self.user_id_max, "user_id_min", "user_id_max")
        return self


class ProjectPagination(Pagination):
    name: NonBlankText | None = None
    member_id: QueryId | None = None
    has_tasks: bool | None = None
    task_count_min: QueryCount | None = None
    task_count_max: QueryCount | None = None
    sort_by: Literal["project_id", "name", "description"] = "project_id"

    @model_validator(mode="after")
    def valid_task_count_range(self) -> Self:
        validate_range(self.task_count_min, self.task_count_max, "task_count_min", "task_count_max")
        return self


class TaskPagination(Pagination):
    project_id: QueryId | None = None
    assignee_id: QueryId | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    task_id_min: QueryId | None = None
    task_id_max: QueryId | None = None
    due_from: AwareDatetime | None = None
    due_to: AwareDatetime | None = None
    sort_by: Literal[
        "task_id", "project_id", "assignee_id", "title", "due_at", "priority", "status",
    ] = "task_id"

    @model_validator(mode="after")
    def valid_ranges(self) -> Self:
        validate_range(self.task_id_min, self.task_id_max, "task_id_min", "task_id_max")
        validate_range(self.due_from, self.due_to, "due_from", "due_to")
        return self

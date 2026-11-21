from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import MAX_BIGINT


class Pagination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1, le=MAX_BIGINT)
    per_page: int = Field(default=10, ge=1, le=100)
    sort_order: Literal["asc", "desc"] = "asc"

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    @model_validator(mode="after")
    def valid_offset(self) -> Self:
        if self.offset > MAX_BIGINT:
            raise ValueError("Page offset exceeds the database integer range")
        return self


class UserPagination(Pagination):
    sort_by: Literal["user_id", "login", "display_name", "name", "is_admin"] = "user_id"


class ProjectPagination(Pagination):
    sort_by: Literal["project_id", "name", "description"] = "project_id"


class TaskPagination(Pagination):
    sort_by: Literal[
        "task_id", "project_id", "assignee_id", "title", "due_at", "priority", "status",
    ] = "task_id"

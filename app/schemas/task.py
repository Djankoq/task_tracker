from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

from app.schemas.common import NonBlankText, PatchModel, RecordId


TaskPriority = Literal["low", "medium", "high"]
TaskStatus = Literal["todo", "in_progress", "in_review", "done"]


class TaskFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignee_id: RecordId
    title: NonBlankText
    description: NonBlankText
    due_at: AwareDatetime
    priority: TaskPriority


class TaskCreate(TaskFields):
    project_id: RecordId


class ReviewFields(BaseModel):
    @model_validator(mode="after")
    def valid_review_reason(self) -> Self:
        if self.review_reason is not None and self.status != "in_progress":
            raise ValueError("A review reason requires status in_progress")
        return self


class TaskReplace(TaskFields, ReviewFields):
    status: TaskStatus
    review_reason: NonBlankText | None = None


class TaskPatch(PatchModel, ReviewFields):
    assignee_id: RecordId | None = None
    title: NonBlankText | None = None
    description: NonBlankText | None = None
    due_at: AwareDatetime | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    review_reason: NonBlankText | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: RecordId
    project_id: RecordId
    assignee_id: RecordId
    title: NonBlankText
    description: NonBlankText
    due_at: AwareDatetime
    priority: TaskPriority
    status: TaskStatus

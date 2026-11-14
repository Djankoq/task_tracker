from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, with_config
from typing_extensions import TypedDict

from app.schemas.common import NonBlankText, RecordId


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


class TaskReplace(TaskFields):
    status: TaskStatus
    review_reason: NonBlankText | None = None


@with_config(ConfigDict(extra="forbid"))
class TaskPatch(TypedDict, total=False):
    assignee_id: RecordId
    title: NonBlankText
    description: NonBlankText
    due_at: AwareDatetime
    priority: TaskPriority
    status: TaskStatus
    review_reason: NonBlankText | None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: int
    project_id: int
    assignee_id: int
    title: str
    description: str
    due_at: datetime
    priority: TaskPriority
    status: TaskStatus

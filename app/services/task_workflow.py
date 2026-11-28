import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions import (
    ForbiddenError,
    InvalidTaskTransitionError,
    NotFoundError,
    ReviewReasonRequiredError,
    TaskActionForbiddenError,
    TaskStatusConflictError,
)
from app.models import Task, User
from app.schemas.task import RequestChanges, TaskPatch, TaskRead, TaskReplace, TaskStatus, TaskTransition
from app.services.crud import project_role, visible_projects, write_transaction


# Inherit the server's configured log level and output.
logger = logging.getLogger("uvicorn.error.task_workflow")


@dataclass(frozen=True)
class TransitionRule:
    required_status: TaskStatus
    next_status: TaskStatus
    role: Literal["executor", "manager"]


REVIEW_RULES = {
    "submit_review": TransitionRule("in_progress", "in_review", "executor"),
    "approve_review": TransitionRule("in_review", "done", "manager"),
    "request_changes": TransitionRule("in_review", "in_progress", "manager"),
}
STATUS_ROLES = {
    ("todo", "in_progress"): "executor",
    **{(rule.required_status, rule.next_status): rule.role for rule in REVIEW_RULES.values()},
}


def get_task(task_id: int, db: Session, user: User, *, lock: bool = False) -> Task:
    statement = select(Task).where(Task.task_id == task_id)
    if not user.is_admin:
        statement = statement.where(Task.project_id.in_(visible_projects(user)))
    if lock:
        # Refresh any instance already loaded into this session after waiting on another writer.
        statement = statement.with_for_update().execution_options(populate_existing=True)
    task = db.scalar(statement)
    if task is None:
        raise NotFoundError("Task not found")
    return task


def set_task_actor(db: Session, actor_id: int, review_reason: str | None = None) -> None:
    db.execute(select(
        func.set_config("task_tracker.actor_id", str(actor_id), True),
        func.set_config("task_tracker.review_reason", review_reason or "", True),
    ))


def validate_review_action(
    request: TaskTransition, *, current_status: str, role: str | None, is_assignee: bool,
) -> TaskStatus:
    rule = REVIEW_RULES[request.action]
    if role != rule.role or (role == "executor" and not is_assignee):
        message = (
            "Only the assigned executor can submit a task for review"
            if rule.role == "executor" else "Project manager required"
        )
        raise TaskActionForbiddenError(message)
    if current_status != rule.required_status:
        raise TaskStatusConflictError(rule.required_status, current_status)
    return rule.next_status


def validate_status_update(current: str, target: TaskStatus | None, role: str, reason: str | None) -> None:
    if target is None or target == current:
        return
    if STATUS_ROLES.get((current, target)) != role:
        raise InvalidTaskTransitionError()
    if current == "in_review" and target == "in_progress" and reason is None:
        raise ReviewReasonRequiredError()


def save_task(task_id: int, payload: TaskPatch | TaskReplace | TaskTransition, db: Session, user: User) -> TaskRead:
    actor_id = user.user_id
    with write_transaction(db):
        task = get_task(task_id, db, user, lock=True)
        previous_status = task.status
        role = project_role(db, task.project_id, actor_id)
        is_assignee = actor_id == task.assignee_id

        if isinstance(payload, (TaskPatch, TaskReplace)):
            if role != "manager" and (role != "executor" or not is_assignee):
                raise ForbiddenError("This user cannot edit the task")
            reason = payload.review_reason
            validate_status_update(previous_status, payload.status, role, reason)
            changes = payload.model_dump(exclude_unset=isinstance(payload, TaskPatch), exclude={"review_reason"})
        else:
            next_status = validate_review_action(payload, current_status=previous_status, role=role, is_assignee=is_assignee)
            changes = {"status": next_status}
            reason = payload.reason if isinstance(payload, RequestChanges) else None

        set_task_actor(db, actor_id, reason)
        for field, value in changes.items():
            setattr(task, field, value)
        # The PostgreSQL trigger records history and the return comment in this transaction.
        db.flush()
        result = TaskRead.model_validate(task)

    if previous_status != result.status:
        logger.info(
            "Task status changed: task_id=%s actor_id=%s from=%s to=%s",
            result.task_id, actor_id, previous_status, result.status,
        )
    return result

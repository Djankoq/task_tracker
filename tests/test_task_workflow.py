import logging
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event
from time import monotonic, sleep

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import (
    InvalidTaskTransitionError,
    ReviewReasonRequiredError,
    TaskActionForbiddenError,
    TaskStatusConflictError,
)
from app.main import app
from app.models import Task, TaskChange, TaskComment
from app.schemas.task import TaskTransition
from app.services import task_workflow
from tests.test_api import ADMIN, EXECUTOR, MANAGER, assert_error, task_payload


SUBMIT = {"action": "submit_review"}
APPROVE = {"action": "approve_review"}
RETURN = {"action": "request_changes", "reason": "Check the acceptance criteria"}
transition_adapter = TypeAdapter(TaskTransition)


@pytest.mark.parametrize(("payload", "current", "role", "assignee", "expected"), [
    (SUBMIT, "in_progress", "executor", True, "in_review"),
    (APPROVE, "in_review", "manager", False, "done"),
    (RETURN, "in_review", "manager", False, "in_progress"),
])
def test_action_rules(payload, current, role, assignee, expected):
    action = transition_adapter.validate_python(payload)
    assert task_workflow.validate_review_action(
        action, current_status=current, role=role, is_assignee=assignee,
    ) == expected


@pytest.mark.parametrize(("payload", "current", "role", "assignee", "error"), [
    (SUBMIT, "in_progress", "executor", False, TaskActionForbiddenError),
    (SUBMIT, "todo", "executor", True, TaskStatusConflictError),
    (APPROVE, "in_review", "executor", True, TaskActionForbiddenError),
    (APPROVE, "done", "manager", False, TaskStatusConflictError),
    (RETURN, "in_progress", "manager", False, TaskStatusConflictError),
])
def test_action_rule_errors(payload, current, role, assignee, error):
    with pytest.raises(error):
        task_workflow.validate_review_action(
            transition_adapter.validate_python(payload),
            current_status=current, role=role, is_assignee=assignee,
        )


def test_legacy_status_rule_errors():
    with pytest.raises(InvalidTaskTransitionError):
        task_workflow.validate_status_update("todo", "done", "manager", None)
    with pytest.raises(ReviewReasonRequiredError):
        task_workflow.validate_status_update("in_review", "in_progress", "manager", None)


def start_task(client):
    created = client.post("/tasks/", headers=MANAGER, json=task_payload())
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]
    started = client.patch(f"/tasks/{task_id}", headers=EXECUTOR, json={"status": "in_progress"})
    assert started.status_code == 200, started.text
    return task_id


def history(db, task_id):
    rows = db.execute(
        select(TaskChange.old_status, TaskChange.new_status, TaskChange.actor_id)
        .where(TaskChange.task_id == task_id)
        .order_by(TaskChange.change_id)
    )
    return rows.all()


def comments(db, task_id):
    rows = db.execute(
        select(TaskComment.body, TaskComment.author_id)
        .where(TaskComment.task_id == task_id)
        .order_by(TaskComment.comment_id)
    )
    return rows.all()


@pytest.mark.parametrize(("payload", "expected_status", "expected_comments"), [
    (APPROVE, "done", []),
    (RETURN, "in_progress", [(RETURN["reason"], 2)]),
])
def test_submit_and_review_persist_history_and_comments(client, db, monkeypatch, payload, expected_status, expected_comments):
    task_id = start_task(client)
    path = f"/tasks/{task_id}/transitions"
    log_events = []

    def capture_log(message, *args):
        assert not db.in_transaction(), "A success log must follow commit"
        log_events.append(message % args)

    monkeypatch.setattr(task_workflow.logger, "info", capture_log)
    submitted = client.post(path, headers=EXECUTOR, json=SUBMIT)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "in_review"
    decided = client.post(path, headers=MANAGER, json=payload)
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == expected_status
    assert history(db, task_id) == [
        ("todo", "in_progress", 3), ("in_progress", "in_review", 3), ("in_review", expected_status, 2),
    ]
    assert comments(db, task_id) == expected_comments
    assert log_events == [
        f"Task status changed: task_id={task_id} actor_id=3 from=in_progress to=in_review",
        f"Task status changed: task_id={task_id} actor_id=2 from=in_review to={expected_status}",
    ]


@pytest.mark.parametrize("payload", [
    {"action": "request_changes"},
    {"action": "request_changes", "reason": "  "},
    {"action": "request_changes", "reason": "bad\x00reason"},
    {"action": "approve_review", "reason": "unnecessary"},
    {"action": "unknown"},
])
def test_invalid_payload_is_rejected_before_workflow(client, monkeypatch, payload):
    def fail_if_called(*_args, **_kwargs):
        pytest.fail("An invalid request entered the write transaction")

    monkeypatch.setattr("app.routers.tasks.save_task", fail_if_called)
    assert_error(client.post("/tasks/1/transitions", headers=MANAGER, json=payload), 400, "validation_error")


def test_permissions_and_stale_status_leave_task_unchanged(client, db):
    task_id = start_task(client)
    path = f"/tasks/{task_id}/transitions"
    assert_error(client.post(path, headers=MANAGER, json=SUBMIT), 403, "task_action_forbidden")
    assert_error(client.post(path, headers=ADMIN, json=APPROVE), 403, "task_action_forbidden")
    assert_error(client.post(path, headers=MANAGER, json=APPROVE), 409, "task_status_conflict")
    assert client.get(f"/tasks/{task_id}", headers=MANAGER).json()["status"] == "in_progress"
    assert history(db, task_id) == [("todo", "in_progress", 3)]
    assert comments(db, task_id) == []


def test_legacy_put_keeps_frontend_payload_and_does_not_duplicate_return_comment(client, db):
    task_id = start_task(client)
    path = f"/tasks/{task_id}"
    submitted = client.post(f"{path}/transitions", headers=EXECUTOR, json=SUBMIT)
    assert submitted.status_code == 200, submitted.text
    replacement = submitted.json()
    replacement.pop("task_id")
    replacement.pop("project_id")
    replacement.update(status="in_progress", review_reason=RETURN["reason"])

    for _ in range(2):
        response = client.put(path, headers=MANAGER, json=replacement)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "in_progress"

    assert history(db, task_id) == [
        ("todo", "in_progress", 3), ("in_progress", "in_review", 3), ("in_review", "in_progress", 2),
    ]
    assert comments(db, task_id) == [(RETURN["reason"], 2)]


def test_failed_commit_rolls_back_status_comment_and_history(client, db, monkeypatch, caplog):
    task_id = start_task(client)
    path = f"/tasks/{task_id}/transitions"
    assert client.post(path, headers=EXECUTOR, json=SUBMIT).status_code == 200
    saved_history = history(db, task_id)
    caplog.clear()
    attempts = []

    def fail_before_commit():
        assert db.get(Task, task_id).status == "in_progress"
        assert comments(db, task_id) == [(RETURN["reason"], 2)]
        assert history(db, task_id) == [*saved_history, ("in_review", "in_progress", 2)]
        attempts.append(True)
        raise RuntimeError("injected commit failure")

    monkeypatch.setattr(db, "commit", fail_before_commit)
    with caplog.at_level(logging.INFO, logger=task_workflow.logger.name):
        assert_error(client.post(path, headers=MANAGER, json=RETURN), 500, "internal_error")
    assert attempts == [True]
    assert db.get(Task, task_id).status == "in_review"
    assert comments(db, task_id) == []
    assert history(db, task_id) == saved_history
    assert not any(record.name == task_workflow.logger.name for record in caplog.records)


def test_concurrent_review_decisions_wait_for_row_lock(concurrent_engine, monkeypatch):
    def separate_sessions():
        with Session(concurrent_engine) as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db, separate_sessions)
    # Do not enter TestClient's lifespan, which checks the configured development database.
    client = TestClient(app, raise_server_exceptions=False)
    try:
        task_id = start_task(client)
        path = f"/tasks/{task_id}/transitions"
        assert client.post(path, headers=EXECUTOR, json=SUBMIT).status_code == 200
    finally:
        client.close()

    get_task = task_workflow.get_task
    first_locked = Event()
    allow_commit = Event()
    pids = Queue()

    def pause_first_writer(task_id, db, user, *, lock=False):
        pid = db.scalar(text("SELECT pg_backend_pid()"))
        pids.put(pid)
        task = get_task(task_id, db, user, lock=lock)
        if not first_locked.is_set():
            first_locked.set()
            if not allow_commit.wait(10):
                raise TimeoutError("Test did not release the first writer")
        return task

    monkeypatch.setattr(task_workflow, "get_task", pause_first_writer)

    def request(payload):
        http = TestClient(app, raise_server_exceptions=False)
        try:
            return http.post(path, headers=MANAGER, json=payload)
        finally:
            http.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(request, APPROVE)
        try:
            assert first_locked.wait(5), "First request never acquired the row lock"
            blocker = pids.get(timeout=5)
            second = pool.submit(request, RETURN)
            waiter = pids.get(timeout=5)
            assert blocker != waiter
            deadline = monotonic() + 4
            with concurrent_engine.connect() as observer:
                while not observer.scalar(
                    text("SELECT :blocker = ANY(pg_blocking_pids(:waiter))"),
                    {"blocker": blocker, "waiter": waiter},
                ):
                    assert monotonic() < deadline and not second.done(), "Second request did not wait for the lock"
                    sleep(0.02)
        finally:
            allow_commit.set()
        approved = first.result(timeout=5)
        rejected = second.result(timeout=5)

    assert approved.status_code == 200, approved.text
    assert_error(rejected, 409, "task_status_conflict")
    with Session(concurrent_engine) as db:
        assert db.get(Task, task_id).status == "done"
        assert history(db, task_id) == [
            ("todo", "in_progress", 3), ("in_progress", "in_review", 3), ("in_review", "done", 2),
        ]
        assert comments(db, task_id) == []

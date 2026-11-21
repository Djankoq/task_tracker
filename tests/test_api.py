from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import func
from sqlalchemy.exc import DBAPIError

from app.error_handlers import register_error_handlers
from app.exceptions import ConflictError, ForbiddenError, ValidationError
from app.main import app
from app.models import Project
from app.schemas.project import ProjectCreate, ProjectPatch
from app.schemas.task import TaskCreate, TaskPatch, TaskReplace
from app.schemas.user import UserRead
from app.services.crud import write_transaction


ADMIN = {"Authorization": "Bearer test-admin-token"}
MANAGER = {"Authorization": "Bearer test-active-token"}
EXECUTOR = {"Authorization": "Bearer test-executor-token"}


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"code", "message", "details"}
    assert body["code"] == code
    assert body["message"]
    assert isinstance(body["details"], list)
    return body


@pytest.mark.parametrize("entity,total,key", [("users", 7, "user_id"), ("projects", 2, "project_id"), ("tasks", 8, "task_id")])
def test_pages_and_sorting(client, entity, total, key):
    default = client.get(f"/{entity}/", headers=ADMIN).json()
    assert (default["total"], default["page"], default["per_page"], default["total_pages"]) == (total, 1, 10, 1)
    first = client.get(f"/{entity}/?per_page=1", headers=ADMIN).json()
    second = client.get(f"/{entity}/?page=2&per_page=1", headers=ADMIN).json()
    assert first["total_pages"] == total
    assert first["items"][0][key] < second["items"][0][key]
    descending = client.get(f"/{entity}/?sort_by={key}&sort_order=desc&per_page=100", headers=ADMIN).json()
    assert [r[key] for r in descending["items"]] == sorted([r[key] for r in descending["items"]], reverse=True)
    last = client.get(f"/{entity}/?page=999&per_page=2", headers=ADMIN).json()
    assert last == {"items": [], "total": total, "page": 999, "per_page": 2, "total_pages": (total + 1) // 2}


@pytest.mark.parametrize("entity", ["users", "projects", "tasks"])
@pytest.mark.parametrize("query", [
    "page=0", "page=-1", "page=abc", "page=1.5", "per_page=0", "per_page=-1",
    "per_page=101", "per_page=abc", "sort_by=password_hash", "sort_by=name;DROP TABLE users",
    "sort_order=DESC", "sort_order=invalid", "page=9223372036854775807&per_page=100",
    "offset=0", "unexpected=true",
])
def test_invalid_list_parameters(client, entity, query):
    body = assert_error(client.get(f"/{entity}/?{query}", headers=ADMIN), 400, "validation_error")
    assert body["details"]
    assert body["details"][0]["loc"][0] == "query"


@pytest.mark.parametrize("entity,fields", [
    ("users", ["user_id", "login", "display_name", "name", "is_admin"]),
    ("projects", ["project_id", "name", "description"]),
    ("tasks", ["task_id", "project_id", "assignee_id", "title", "due_at", "priority", "status"]),
])
def test_all_allowed_sort_fields(client, entity, fields):
    for field in fields:
        for order in ("asc", "desc"):
            response = client.get(f"/{entity}/?sort_by={field}&sort_order={order}", headers=ADMIN)
            assert response.status_code == 200, response.text


def test_user_name_alias_and_security(client):
    example = client.get("/users/?page=2&per_page=5&sort_by=name&sort_order=desc", headers=ADMIN)
    assert example.status_code == 200
    assert len(example.json()["items"]) == 2
    canonical = client.get("/users/?page=2&per_page=5&sort_by=display_name&sort_order=desc", headers=ADMIN)
    assert canonical.json() == example.json()
    for item in example.json()["items"]:
        assert set(item) == {"user_id", "login", "display_name", "is_admin"}
    assert_error(client.get("/users/", headers=MANAGER), 403, "forbidden")


def test_visibility_metadata_and_empty_list(client, db):
    for entity, expected in (("projects", 1), ("tasks", 6)):
        page = client.get(f"/{entity}/?per_page=1", headers=MANAGER).json()
        assert (page["total"], page["total_pages"]) == (expected, expected)
    # Removing visibility, rather than data, also verifies the filtered count.
    from app.models import ProjectMember
    db.execute(ProjectMember.__table__.update().where(ProjectMember.user_id == 2).values(removed_at=func.now()))
    empty = client.get("/projects/", headers=MANAGER).json()
    assert empty == {"items": [], "total": 0, "page": 1, "per_page": 10, "total_pages": 0}


def test_duplicate_sort_values_have_stable_pages(client):
    ids = []
    for _ in range(3):
        response = client.post("/projects/", headers=ADMIN, json={"name": "Identical"})
        assert response.status_code == 201
        ids.append(response.json()["project_id"])
    all_items = client.get("/projects/?sort_by=name&per_page=100", headers=ADMIN).json()["items"]
    paged = [client.get(f"/projects/?sort_by=name&page={p}&per_page=1", headers=ADMIN).json()["items"][0] for p in range(1, 6)]
    assert paged == all_items
    assert [i["project_id"] for i in paged if i["name"] == "Identical"] == ids


def test_auth_and_not_found(client):
    for token in (None, "test-expired-token", "test-revoked-token", "invalid"):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = client.get("/users/me", headers=headers)
        assert_error(response, 401, "unauthorized")
        assert response.headers["WWW-Authenticate"] == "Bearer"
    assert client.get("/users/me", headers=MANAGER).status_code == 200
    for entity in ("projects", "tasks"):
        assert_error(client.get(f"/{entity}/999999", headers=ADMIN), 404, "not_found")
    assert_error(client.get("/unknown"), 404, "not_found")
    assert_error(client.put("/users/"), 405, "method_not_allowed")


def task_payload(**changes):
    return {"project_id": 1, "assignee_id": 3, "title": "Test", "description": "Details",
            "due_at": "2099-01-01T00:00:00Z", "priority": "medium", **changes}


def test_conflict_and_database_business_rules(client):
    assert_error(client.delete("/projects/1", headers=ADMIN), 409, "conflict")
    assert_error(client.post("/tasks/", headers=MANAGER, json=task_payload(assignee_id=1)), 400, "validation_error")
    created = client.post("/tasks/", headers=MANAGER, json=task_payload())
    assert created.status_code == 201, created.text
    path = f"/tasks/{created.json()['task_id']}"
    assert_error(client.patch(path, headers=MANAGER, json={"status": "done"}), 400, "validation_error")
    assert_error(client.patch(path, headers=EXECUTOR, json={"description": "Forbidden"}), 403, "forbidden")
    assert client.patch(path, headers=EXECUTOR, json={"status": "in_progress"}).status_code == 200
    assert client.patch(path, headers=EXECUTOR, json={"status": "in_review"}).status_code == 200
    assert_error(client.patch(path, headers=MANAGER, json={"status": "in_progress"}), 400, "validation_error")
    assert client.patch(path, headers=MANAGER, json={"status": "in_progress", "review_reason": "Fix tests"}).status_code == 200


@pytest.mark.parametrize("entity", ["projects", "tasks"])
@pytest.mark.parametrize("payload", [{}, {"title": None}, {"unexpected": True}])
def test_invalid_patches(client, entity, payload):
    assert_error(client.patch(f"/{entity}/1", headers=MANAGER if entity == "tasks" else ADMIN, json=payload), 400, "validation_error")


def test_malformed_json_and_validation_details(client):
    response = client.post("/projects/", headers={**ADMIN, "Content-Type": "application/json"}, content="{")
    assert assert_error(response, 400, "validation_error")["details"]
    for changes in ({"title": "  "}, {"due_at": "2099-01-01T00:00:00"}, {"assignee_id": 0}, {"priority": "critical"}, {"title": "bad\x00text"}):
        assert_error(client.post("/tasks/", headers=MANAGER, json=task_payload(**changes)), 400, "validation_error")


@pytest.mark.parametrize("schema,payload", [
    (ProjectCreate, {"name": "\t\n "}), (ProjectPatch, {"name": None}),
    (TaskCreate, task_payload(assignee_id=True)), (TaskCreate, task_payload(assignee_id=2**63)),
    (TaskPatch, {"status": "done", "review_reason": "Changes"}),
    (TaskReplace, {k: v for k, v in task_payload().items() if k != "project_id"} | {"status": "done", "review_reason": "Changes"}),
    (UserRead, {"user_id": 1, "login": " UPPER ", "display_name": "User", "is_admin": False}),
])
def test_pydantic_validators(schema, payload):
    with pytest.raises(PydanticValidationError):
        schema.model_validate(payload)


@pytest.mark.parametrize("code,deleting,expected", [
    ("23505", False, ConflictError), ("23503", True, ConflictError),
    ("23503", False, ValidationError), ("23514", False, ValidationError),
    ("42501", False, ForbiddenError),
])
def test_database_error_translation(code, deleting, expected):
    class DatabaseFailure(Exception):
        pgcode = code
        diag = SimpleNamespace(message_primary="Invalid status transition")

    db = Mock()
    db.commit.side_effect = DBAPIError("query", {}, DatabaseFailure(), False)
    with pytest.raises(expected):
        with write_transaction(db, deleting=deleting):
            pass
    db.rollback.assert_called_once()


def test_global_handlers_and_safe_internal_errors():
    isolated = FastAPI()
    register_error_handlers(isolated)

    @isolated.get("/fail")
    def fail():
        raise RuntimeError("secret database credentials")

    response = TestClient(isolated, raise_server_exceptions=False).get("/fail")
    assert_error(response, 500, "internal_error")
    assert "secret" not in response.text


def test_openapi_contract():
    schema = app.openapi()
    for path in ("/users/", "/projects/", "/tasks/"):
        operation = schema["paths"][path]["get"]
        assert {p["name"] for p in operation["parameters"]} >= {"page", "per_page", "sort_by", "sort_order", "search"}
        assert "400" in operation["responses"]
        assert "422" not in operation["responses"]
    assert "ErrorResponse" in schema["components"]["schemas"]

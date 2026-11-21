from hashlib import pbkdf2_hmac

import pytest
from sqlalchemy import select

from app.models import User
from tests.test_api import ADMIN, MANAGER, assert_error


PAYLOAD = {"login": "frontend_user", "display_name": "Frontend User", "password": "test-password-123", "is_admin": False}


def test_user_crud_and_password_security(client, db):
    response = client.post("/users/", headers=ADMIN, json=PAYLOAD)
    assert response.status_code == 201, response.text
    user = response.json()
    user_id = user["user_id"]
    assert set(user) == {"user_id", "login", "display_name", "is_admin"}
    stored = db.scalar(select(User.password_hash).where(User.user_id == user_id))
    algorithm, iterations, salt, digest = stored.split("$")
    assert algorithm == "pbkdf2_sha256"
    assert digest == pbkdf2_hmac("sha256", PAYLOAD["password"].encode(), bytes.fromhex(salt), int(iterations)).hex()
    assert client.get(f"/users/{user_id}", headers=ADMIN).json() == user
    update = {"login": "frontend_changed", "display_name": "Changed", "is_admin": False}
    assert client.put(f"/users/{user_id}", headers=ADMIN, json=update).json()["display_name"] == "Changed"
    assert db.scalar(select(User.password_hash).where(User.user_id == user_id)) == stored
    assert client.put(f"/users/{user_id}", headers=ADMIN, json={**update, "password": "another-password"}).status_code == 200
    assert db.scalar(select(User.password_hash).where(User.user_id == user_id)) != stored
    assert client.delete(f"/users/{user_id}", headers=ADMIN).status_code == 204
    assert_error(client.get(f"/users/{user_id}", headers=ADMIN), 404, "not_found")


@pytest.mark.parametrize("patch", [
    {"login": "MixedCase"}, {"login": " padded "}, {"login": ""},
    {"display_name": "  "}, {"password": "short"}, {"password": "a" * 129},
    {"unexpected": True},
])
def test_invalid_user_creation(client, patch):
    assert_error(client.post("/users/", headers=ADMIN, json={**PAYLOAD, **patch}), 400, "validation_error")


def test_user_crud_access_and_conflicts(client):
    assert_error(client.post("/users/", json=PAYLOAD), 401, "unauthorized")
    for method, path, payload in [("post", "/users/", PAYLOAD), ("get", "/users/1", None), ("put", "/users/1", PAYLOAD), ("delete", "/users/1", None)]:
        kwargs = {"json": payload} if payload else {}
        assert_error(getattr(client, method)(path, headers=MANAGER, **kwargs), 403, "forbidden")
    assert_error(client.post("/users/", headers=ADMIN, json={**PAYLOAD, "login": "admin"}), 409, "conflict")
    assert_error(client.delete("/users/1", headers=ADMIN), 403, "forbidden")
    assert_error(client.put("/users/1", headers=ADMIN, json={"login": "admin", "display_name": "Admin", "is_admin": False}), 403, "forbidden")
    assert_error(client.delete("/users/3", headers=ADMIN), 409, "conflict")
    assert_error(client.delete("/users/99999", headers=ADMIN), 404, "not_found")


def test_members_are_visible_only_with_the_project(client):
    response = client.get("/projects/1/members", headers=MANAGER)
    assert response.status_code == 200
    assert response.json()
    assert all(row["project_id"] == 1 and row["removed_at"] is None for row in response.json())
    assert any(row["user_id"] == 2 and row["role"] == "manager" for row in response.json())
    assert_error(client.get("/projects/2/members", headers=MANAGER), 404, "not_found")
    assert_error(client.get("/projects/1/members"), 401, "unauthorized")

from sqlalchemy import update

from app.models import ProjectMember


ADMIN = {"Authorization": "Bearer test-admin-token"}
MANAGER = {"Authorization": "Bearer test-active-token"}


def test_empty_projects_in_workload(client, db):
    created = client.post("/projects/", json={"name": "Empty"}, headers=ADMIN)
    assert created.status_code == 201
    summary = client.get("/stats/summary", headers=ADMIN).json()
    assert summary == {"total_projects": 3, "total_tasks": 8, "avg_tasks_per_project": 8 / 3}
    empty = client.get("/projects/?has_tasks=false", headers=ADMIN).json()
    assert [p["project_id"] for p in empty["items"]] == [created.json()["project_id"]]
    db.execute(update(ProjectMember).where(ProjectMember.user_id == 2).values(removed_at="2026-01-01"))
    assert client.get("/stats/summary", headers=MANAGER).json() == {
        "total_projects": 0, "total_tasks": 0, "avg_tasks_per_project": None,
    }
    for path in ("/stats/tasks-by-status", "/reports/top-projects"):
        assert client.get(path, headers=MANAGER).json() == []


def test_search_sort_and_page(client):
    for name in ("Example A", "Example B", "Example C"):
        assert client.post("/projects/", headers=ADMIN, json={"name": name, "description": "50%_OFF/"}).status_code == 201
    page = client.get("/projects/", headers=ADMIN, params={
        "search": "%_off/", "has_tasks": "false", "sort_by": "name", "sort_order": "desc",
        "page": 2, "per_page": 2,
    }).json()
    assert page["total"] == 3 and page["total_pages"] == 2
    assert [item["name"] for item in page["items"]] == ["Example A"]


def test_deadline_bounds_are_inclusive(client):
    item = client.get("/tasks/?per_page=1", headers=ADMIN).json()["items"][0]
    params = {"due_from": item["due_at"], "due_to": item["due_at"]}
    page = client.get("/tasks/", params=params, headers=ADMIN).json()
    assert item["task_id"] in [task["task_id"] for task in page["items"]]
    assert all(task["due_at"] == item["due_at"] for task in page["items"])

"""Optional end-to-end run of the real Postman collection through Newman."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time

import pytest
import uvicorn
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
import app.main as main


@pytest.mark.skipif(os.getenv("RUN_POSTMAN") != "1", reason="Set RUN_POSTMAN=1 to run Newman")
def test_postman_collection(test_engine, tmp_path, monkeypatch):
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    assert npx, "Install Node.js with npx to run the Postman collection"

    def override_db():
        with Session(test_engine) as session:
            yield session

    def check_test_database():
        with test_engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM task_tracker.users LIMIT 0"))

    monkeypatch.setattr(main, "check_database", check_test_database)
    app.dependency_overrides[get_db] = override_db
    server = uvicorn.Server(uvicorn.Config(app, lifespan="off", log_level="error"))
    thread = None
    try:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
            thread.start()
            deadline = time.monotonic() + 10
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert server.started, "Test API failed to start"
            root = Path(__file__).resolve().parents[1]
            report = tmp_path / "newman.json"
            result = subprocess.run(
                [npx, "--yes", "newman@6.2.2", "run",
                 str(root / "postman" / "Task Tracker CRUD.postman_collection.json"),
                 "--env-var", f"base_url=http://127.0.0.1:{port}",
                 "--reporters", "json", "--reporter-json-export", str(report)],
                cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
            )
            assert report.exists(), result.stdout + result.stderr
            run = json.loads(report.read_text(encoding="utf-8"))["run"]
            failures = [
                {"request": failure.get("source", {}).get("name"), "error": failure["error"]["message"]}
                for failure in run["failures"]
            ]
            assert result.returncode == 0 and not failures, json.dumps(failures, ensure_ascii=False, indent=2)
            print(f"Newman: {run['stats']['requests']['total']} requests, {run['stats']['assertions']['total']} assertions passed")
    finally:
        server.should_exit = True
        if thread is not None:
            thread.join(timeout=10)
        app.dependency_overrides.clear()

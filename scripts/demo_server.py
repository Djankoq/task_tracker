"""Run the API against a disposable seeded database for UI demonstrations."""

import os
import sys
from pathlib import Path
from uuid import uuid4

import psycopg2
from psycopg2 import sql


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_database_url


def main() -> None:
    url = get_database_url()
    database_name = "task_tracker_demo_" + uuid4().hex
    connection_options = {
        "user": url.username, "password": url.password, "host": url.host,
        "port": url.port, "connect_timeout": 5,
    }
    admin = psycopg2.connect(dbname=url.database, **connection_options)
    admin.autocommit = True
    created = False
    try:
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(
                sql.Identifier(database_name),
            ))
        created = True
        with psycopg2.connect(dbname=database_name, **connection_options) as demo:
            with demo.cursor() as cursor:
                for filename in ("01_schema.sql", "02_seed.sql", "migrations/001_search_indexes.up.sql"):
                    cursor.execute((ROOT / filename).read_text(encoding="utf-8"))
        os.environ["DATABASE_URL"] = url.set(database=database_name).render_as_string(hide_password=False)
        os.environ.pop("CREATE_TABLES", None)
        import uvicorn
        from app.main import app

        print("Disposable demonstration API: http://127.0.0.1:8002", flush=True)
        print("Seed session tokens are valid for 24 hours. Stop with Ctrl+C to remove this demo database.", flush=True)
        uvicorn.run(app, host="127.0.0.1", port=8002, log_level="warning")
    finally:
        if created:
            # The target is generated above, never supplied by a caller or taken from .env.
            assert database_name.startswith("task_tracker_demo_") and len(database_name) == 50
            with admin.cursor() as cursor:
                cursor.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name)))
        admin.close()


if __name__ == "__main__":
    main()

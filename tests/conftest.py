from pathlib import Path
from uuid import uuid4

import psycopg2
from psycopg2 import sql
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import get_database_url
from app.database import get_db
from app.main import app


@pytest.fixture(scope="session")
def test_engine():
    """Use a fresh database; never load fixtures into the development database."""
    url = get_database_url()
    database_name = "task_tracker_test_" + uuid4().hex
    connection = psycopg2.connect(
        dbname=url.database, user=url.username, password=url.password,
        host=url.host, port=url.port, connect_timeout=5,
    )
    connection.autocommit = True
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(
            sql.Identifier(database_name),
        ))
    engine = create_engine(url.set(database=database_name))
    try:
        root = Path(__file__).resolve().parents[1]
        db = engine.raw_connection()
        try:
            with db.cursor() as cursor:
                for script in ("01_schema.sql", "02_seed.sql", "migrations/001_search_indexes.up.sql"):
                    cursor.execute((root / script).read_text(encoding="utf-8"))
        finally:
            db.close()
        yield engine
    finally:
        engine.dispose()
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name)))
        connection.close()


@pytest.fixture
def db(test_engine):
    with test_engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()


@pytest.fixture
def client(db):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        # Without the context manager, lifespan does not touch the development DB.
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.clear()

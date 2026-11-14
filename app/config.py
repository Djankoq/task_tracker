import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def get_database_url() -> URL:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("Set DATABASE_URL in .env or in the environment.")

    try:
        url = make_url(value)
    except (ArgumentError, ValueError):
        raise RuntimeError("DATABASE_URL is invalid.") from None

    if url.drivername not in {"postgresql", "postgresql+psycopg2"}:
        raise RuntimeError("DATABASE_URL must use PostgreSQL with psycopg2.")
    return url


def get_app_port() -> int:
    try:
        port = int(os.getenv("APP_PORT", "8000"))
    except ValueError:
        port = 0
    if not 1 <= port <= 65535:
        raise RuntimeError("APP_PORT must be an integer between 1 and 65535.")
    return port

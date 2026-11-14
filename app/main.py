import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.schema import CreateSchema
from starlette.concurrency import run_in_threadpool

# Keep absolute imports available when the IDE runs this file as a script.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_app_port
from app.database import Base, check_database, engine
from app.models import AuthSession, Project, ProjectMember, Task, TaskChange, TaskComment, User
from app.routers.users import router as users_router


def prepare_database() -> None:
    if os.getenv("CREATE_TABLES") == "1":
        with engine.begin() as connection:
            connection.execute(CreateSchema("task_tracker", if_not_exists=True))
            Base.metadata.create_all(
                connection,
                tables=[
                    User.__table__,
                    AuthSession.__table__,
                    Project.__table__,
                    ProjectMember.__table__,
                    Task.__table__,
                    TaskComment.__table__,
                    TaskChange.__table__,
                ],
            )
    check_database()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        try:
            await run_in_threadpool(prepare_database)
        except OperationalError:
            raise RuntimeError(
                "Cannot connect to PostgreSQL. Check that it is running and that "
                "the host, port and credentials in DATABASE_URL are correct."
            ) from None
        except SQLAlchemyError:
            raise RuntimeError(
                "Cannot prepare the Task Tracker schema. Check the database permissions "
                "and setup instructions in README.md."
            ) from None
        yield
    finally:
        await run_in_threadpool(engine.dispose)


app = FastAPI(title="Task Tracker", lifespan=lifespan)
app.include_router(users_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    try:
        check_database()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from None
    return {"status": "ok", "database": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=get_app_port())

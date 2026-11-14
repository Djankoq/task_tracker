from pydantic import BaseModel, ConfigDict, with_config
from typing_extensions import TypedDict

from app.schemas.common import DatabaseText, NonBlankText


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: NonBlankText
    description: DatabaseText = ""


class ProjectReplace(ProjectCreate):
    description: DatabaseText


@with_config(ConfigDict(extra="forbid"))
class ProjectPatch(TypedDict, total=False):
    name: NonBlankText
    description: DatabaseText


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: int
    name: str
    description: str

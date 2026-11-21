from pydantic import BaseModel, ConfigDict

from app.schemas.common import DatabaseText, NonBlankText, PatchModel, RecordId


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: NonBlankText
    description: DatabaseText = ""


class ProjectReplace(ProjectCreate):
    description: DatabaseText


class ProjectPatch(PatchModel):
    name: NonBlankText | None = None
    description: DatabaseText | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: RecordId
    name: NonBlankText
    description: DatabaseText

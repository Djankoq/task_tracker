from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.common import DatabaseText, NonBlankText, RecordId


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: RecordId
    login: DatabaseText
    display_name: NonBlankText
    is_admin: bool

    @field_validator("login")
    @classmethod
    def valid_login(cls, value: str) -> str:
        if not value or value != value.strip().lower():
            raise ValueError("Login must be nonempty, lowercase and without surrounding whitespace")
        return value

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

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


class UserWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login: DatabaseText
    display_name: NonBlankText
    is_admin: bool = False

    @field_validator("login")
    @classmethod
    def valid_login(cls, value: str) -> str:
        return UserRead.valid_login(value)


class UserCreate(UserWrite):
    password: SecretStr = Field(min_length=8, max_length=128)


class UserUpdate(UserWrite):
    # Omit password to keep the current hash; it is never returned to clients.
    password: SecretStr | None = Field(default=None, min_length=8, max_length=128)

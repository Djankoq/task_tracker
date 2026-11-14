from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    login: str
    display_name: str
    is_admin: bool

from typing import Annotated, Generic, Self, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator


MAX_BIGINT = 2**63 - 1
RecordId = Annotated[int, Field(strict=True, gt=0, le=MAX_BIGINT)]


def without_null_byte(value: str) -> str:
    if "\x00" in value:
        raise ValueError("Text must not contain a null byte")
    return value


DatabaseText = Annotated[str, AfterValidator(without_null_byte)]
NonBlankText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1), AfterValidator(without_null_byte)
]


class PatchModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def valid_patch(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for field in self.model_fields_set - {"review_reason"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        return self


class ValidationIssue(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: list[ValidationIssue] = Field(default_factory=list)


Item = TypeVar("Item")


class PageResponse(BaseModel, Generic[Item]):
    items: list[Item]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    per_page: int = Field(ge=1, le=100)
    total_pages: int = Field(ge=0)

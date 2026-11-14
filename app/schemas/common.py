from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, StringConstraints


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


class ValidationIssue(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ApiError(BaseModel):
    detail: str | list[ValidationIssue]

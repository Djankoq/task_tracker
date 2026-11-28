from app.schemas.common import ValidationIssue


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(
        self, message: str, *, details: list[ValidationIssue] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []
        self.headers = headers


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationError(AppError):
    status_code = 400
    code = "validation_error"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"

    def __init__(self, message: str = "Invalid or expired session") -> None:
        super().__init__(message, headers={"WWW-Authenticate": "Bearer"})


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"


class InvalidTaskTransitionError(ValidationError):
    def __init__(self) -> None:
        super().__init__("Invalid status transition")


class ReviewReasonRequiredError(ValidationError):
    def __init__(self) -> None:
        super().__init__("A review return requires a reason")


class TaskActionForbiddenError(ForbiddenError):
    code = "task_action_forbidden"


class TaskStatusConflictError(ConflictError):
    code = "task_status_conflict"

    def __init__(self, expected: str, current: str) -> None:
        super().__init__(f"Task status must be {expected}; current status is {current}. Reload the task.")

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.exceptions import AppError, ValidationError
from app.schemas.common import ErrorResponse, ValidationIssue


logger = logging.getLogger(__name__)


def error_response(error: AppError) -> JSONResponse:
    body = ErrorResponse(code=error.code, message=error.message, details=error.details)
    return JSONResponse(
        status_code=error.status_code, content=body.model_dump(mode="json"), headers=error.headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def application_error(_: Request, error: AppError) -> JSONResponse:
        return error_response(error)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_: Request, error: RequestValidationError) -> JSONResponse:
        issues = [
            ValidationIssue(loc=list(item["loc"]), msg=item["msg"], type=item["type"])
            for item in error.errors()
        ]
        return error_response(ValidationError("Invalid request data", details=issues))

    @app.exception_handler(HTTPException)
    async def framework_error(_: Request, error: HTTPException) -> JSONResponse:
        # Includes Starlette's unknown-route and method-not-allowed responses.
        body = ErrorResponse(
            code=HTTPStatus(error.status_code).name.lower(), message=str(error.detail),
        )
        return JSONResponse(
            status_code=error.status_code, content=body.model_dump(mode="json"), headers=error.headers,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, error: Exception) -> JSONResponse:
        logger.error("Unhandled API error", exc_info=error)
        return error_response(AppError("Internal server error"))

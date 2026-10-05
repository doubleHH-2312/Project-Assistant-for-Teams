from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = Field(alias="correlationId")


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


async def app_error_handler(request: Request, error: AppError) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    body = ErrorBody(
        code=error.code,
        message=error.message,
        details=error.details,
        correlationId=correlation_id,
    )
    return JSONResponse(status_code=error.status_code, content=body.model_dump(by_alias=True))


async def request_validation_error_handler(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    fields = [
        ".".join(str(part) for part in item["loc"])
        for item in error.errors()
    ]
    body = ErrorBody(
        code="REQUEST_VALIDATION_FAILED",
        message="The request is invalid",
        details={"fields": fields},
        correlationId=correlation_id,
    )
    return JSONResponse(status_code=422, content=body.model_dump(by_alias=True))

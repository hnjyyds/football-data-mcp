from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ErrorCategory(StrEnum):
    """Stable buckets used by clients to distinguish error handling paths."""

    BUSINESS = "business"
    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    AUTHORIZATION = "authorization"
    NOT_FOUND = "not_found"
    SYSTEM = "system"


@dataclass(slots=True)
class AppError(Exception):
    """Base application exception converted to the public API error envelope."""

    code: str
    message: str
    status_code: int = 500
    category: ErrorCategory = ErrorCategory.SYSTEM
    details: dict[str, Any] | None = None


class NotFoundError(AppError):
    def __init__(self, *, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=404,
            category=ErrorCategory.NOT_FOUND,
            details=details,
        )


class AuthorizationError(AppError):
    def __init__(self, *, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=403,
            category=ErrorCategory.AUTHORIZATION,
            details=details,
        )


class RequestValidationAppError(AppError):
    def __init__(self, *, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=422,
            category=ErrorCategory.VALIDATION,
            details=details,
        )


class ServiceExecutionError(AppError):
    def __init__(self, *, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=500,
            category=ErrorCategory.SYSTEM,
            details=details,
        )

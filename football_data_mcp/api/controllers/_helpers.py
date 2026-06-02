from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import Response

from football_data_mcp.api.schemas.common import error_json
from football_data_mcp.api_http import dashboard_cors_headers
from football_data_mcp.core.errors import AppError, RequestValidationAppError


def headers_for(request: Request, *, allow_methods: str = "GET, OPTIONS") -> dict[str, str]:
    return dashboard_cors_headers(request, allow_methods=allow_methods)


def options_response(headers: dict[str, str]) -> Response:
    return Response(status_code=204, headers=headers)


def api_error_response(exc: Exception, *, headers: dict[str, str]) -> Response:
    if isinstance(exc, ValidationError):
        exc = RequestValidationAppError(
            code="request_validation_failed",
            message="Request parameters failed validation.",
            details={"errors": exc.errors()},
        )
    if isinstance(exc, AppError):
        return error_json(
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            headers=headers,
            details=exc.details,
        )
    return error_json(
        code="internal_server_error",
        message="The API request could not be completed.",
        status_code=500,
        headers=headers,
        details={"reason": str(exc)},
    )


def bool_query(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def route(path: str, methods: list[str]) -> dict[str, Any]:
    return {"path": path, "methods": methods}

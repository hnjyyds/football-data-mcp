from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import JSONResponse


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    status: str = "error"
    error: ErrorBody
    generated_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LooseObjectResponse(BaseModel):
    """Typed envelope for legacy dynamic payloads while migration continues."""

    model_config = ConfigDict(extra="allow")

    status: str | None = None


def success_json(payload: BaseModel | dict[str, Any], *, headers: dict[str, str], status_code: int = 200) -> JSONResponse:
    if isinstance(payload, BaseModel):
        content = payload.model_dump(mode="json")
    else:
        content = payload
    return JSONResponse(content, status_code=status_code, headers=headers)


def error_json(
    *,
    code: str,
    message: str,
    status_code: int,
    headers: dict[str, str],
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(payload.model_dump(mode="json"), status_code=status_code, headers=headers)

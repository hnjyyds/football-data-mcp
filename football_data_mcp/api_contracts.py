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


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    uptime_seconds: int
    db_path: str
    db_accessible: bool
    last_learning_cycle_at: str | None
    last_learning_cycle_error: str | None
    auto_learning_enabled: bool
    generated_at_utc: str


class DashboardSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    generated_at_utc: str | None
    kpis: dict[str, Any]
    prediction_kpis: dict[str, Any]
    strategy_status: str | None
    strategy_sample_count: int | None


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

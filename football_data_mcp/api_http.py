from __future__ import annotations

from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from football_data_mcp.api_contracts import error_json
from football_data_mcp.config import load_server_settings


def dashboard_cors_headers(request: Request | None = None, *, allow_methods: str = "GET, OPTIONS") -> dict[str, str]:
    headers = {
        "Access-Control-Allow-Methods": allow_methods,
        "Access-Control-Allow-Headers": "Content-Type, X-Admin-Token",
        "Cache-Control": "no-store",
    }
    origin = request.headers.get("origin") if request else None
    if origin and origin in load_server_settings().dashboard_cors_origins:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Vary"] = "Origin"
    return headers


def json_error(
    *,
    code: str,
    message: str,
    status_code: int,
    headers: dict[str, str],
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return error_json(code=code, message=message, status_code=status_code, headers=headers, details=details)


def admin_token_error(request: Request, headers: dict[str, str]) -> JSONResponse | None:
    expected = load_server_settings().admin_token
    if not expected:
        return json_error(
            code="admin_token_not_configured",
            message="Admin token is required before executing database cleanup.",
            status_code=403,
            headers=headers,
        )
    provided = request.headers.get("x-admin-token", "")
    if provided != expected:
        return json_error(
            code="admin_token_invalid",
            message="Admin token is invalid.",
            status_code=403,
            headers=headers,
        )
    return None

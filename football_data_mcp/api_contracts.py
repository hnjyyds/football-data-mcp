from __future__ import annotations

from football_data_mcp.api.schemas.common import ErrorBody, ErrorResponse, error_json, success_json
from football_data_mcp.api.schemas.dashboard import DashboardSummaryResponse
from football_data_mcp.api.schemas.health import HealthResponse

__all__ = [
    "DashboardSummaryResponse",
    "ErrorBody",
    "ErrorResponse",
    "HealthResponse",
    "error_json",
    "success_json",
]

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import Response

from football_data_mcp.api.controllers._helpers import api_error_response, headers_for, options_response, route
from football_data_mcp.api.registry import SupportsCustomRoute
from football_data_mcp.api.schemas.common import success_json
from football_data_mcp.api.schemas.health import HealthResponse
from football_data_mcp.core import runtime_state
from football_data_mcp.services.health_service import AutoLearningStateReader, HealthService, LearningCycleStatusReader


_server_start_time = runtime_state.server_start_time
_learning_cycle_status: LearningCycleStatusReader = runtime_state.learning_cycle_status
_auto_learning_state_status: AutoLearningStateReader = runtime_state.auto_learning_state_cycle_status


def configure_health_dependencies(
    *,
    server_start_time,
    learning_cycle_status: LearningCycleStatusReader,
    auto_learning_state_status: AutoLearningStateReader,
) -> None:
    """Inject process-level status readers without coupling the controller to server.py."""
    global _server_start_time, _learning_cycle_status, _auto_learning_state_status
    _server_start_time = server_start_time
    _learning_cycle_status = learning_cycle_status
    _auto_learning_state_status = auto_learning_state_status


def register(mcp: SupportsCustomRoute) -> list[dict[str, object]]:
    path = "/api/health"
    methods = ["GET", "OPTIONS"]
    mcp.custom_route(path, methods=methods, include_in_schema=False)(health_api)
    return [route(path, methods)]


async def health_api(request: Request) -> Response:
    """Lightweight health check endpoint for monitoring and Docker HEALTHCHECK."""
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        service = HealthService(
            server_start_time=_server_start_time(),
            learning_cycle_status=_learning_cycle_status,
            auto_learning_state_status=_auto_learning_state_status,
        )
        return success_json(HealthResponse(**service.health_snapshot()), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import Response

from football_data_mcp.api.controllers._helpers import api_error_response, headers_for, options_response, route
from football_data_mcp.api.registry import SupportsCustomRoute, iter_controller_module_names
from football_data_mcp.api.schemas.common import success_json
from football_data_mcp.api.schemas.project import ProjectResponse
from football_data_mcp.services.project_service import ProjectService


def register(mcp: SupportsCustomRoute) -> list[dict[str, object]]:
    path = "/api/project"
    methods = ["GET", "OPTIONS"]
    mcp.custom_route(path, methods=methods, include_in_schema=False)(project_api)
    return [route(path, methods)]


async def project_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        controller_names = [name.rsplit(".", 1)[-1] for name in iter_controller_module_names()]
        payload = ProjectService().overview(controllers=controller_names)
        return success_json(ProjectResponse.model_validate(payload), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)

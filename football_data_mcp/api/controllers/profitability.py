from __future__ import annotations

from starlette.requests import Request
from starlette.responses import Response

from football_data_mcp.api.controllers._helpers import api_error_response, headers_for, options_response, route
from football_data_mcp.api.registry import SupportsCustomRoute
from football_data_mcp.api.schemas.common import success_json
from football_data_mcp.api.schemas.profitability import ProfitabilityForecastResponse
from football_data_mcp.services.profitability_service import ProfitabilityService


def register(mcp: SupportsCustomRoute) -> list[dict[str, object]]:
    path = "/api/profitability/forecast"
    methods = ["GET", "OPTIONS"]
    mcp.custom_route(path, methods=methods, include_in_schema=False)(profitability_forecast_api)
    return [route(path, methods)]


async def profitability_forecast_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        result = await ProfitabilityService().forecast()
        return success_json(ProfitabilityForecastResponse.model_validate(result), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)

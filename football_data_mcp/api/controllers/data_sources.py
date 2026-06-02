from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import Response

from football_data_mcp.api.controllers._helpers import api_error_response, headers_for, options_response, route
from football_data_mcp.api.registry import SupportsCustomRoute
from football_data_mcp.api.schemas.common import success_json
from football_data_mcp.api.schemas.data_sources import FdoMatchesQuery, FdoMatchesResponse, SourcesProbeResponse
from football_data_mcp.services.data_source_service import DataSourceService


logger = logging.getLogger("football_data_mcp.api.data_sources")


def register(mcp: SupportsCustomRoute) -> list[dict[str, object]]:
    routes = [
        ("/api/fdo/matches", ["GET", "OPTIONS"], fdo_matches_api),
        ("/api/sources/probe", ["GET", "OPTIONS"], sources_probe_api),
    ]
    for path, methods, handler in routes:
        mcp.custom_route(path, methods=methods, include_in_schema=False)(handler)
    return [route(path, methods) for path, methods, _ in routes]


async def fdo_matches_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        query = FdoMatchesQuery(
            date_from=request.query_params.get("date_from") or None,
            date_to=request.query_params.get("date_to") or None,
        )
        result = await DataSourceService().fdo_matches(date_from=query.date_from, date_to=query.date_to)
        return success_json(FdoMatchesResponse.model_validate(result), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)


async def sources_probe_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        result, elapsed = await DataSourceService().source_probe()
        logger.info("sources_probe_api completed in %.2fs (%d available)", elapsed, result.get("available_count", 0))
        return success_json(SourcesProbeResponse.model_validate(result), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)

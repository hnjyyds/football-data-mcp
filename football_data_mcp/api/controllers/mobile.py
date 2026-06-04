from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import Response

from football_data_mcp.api.controllers._helpers import api_error_response, bool_query, headers_for, options_response, route
from football_data_mcp.api.registry import SupportsCustomRoute
from football_data_mcp.api.schemas.common import success_json
from football_data_mcp.api.schemas.mobile import MobileAnalysisResponse, MobileMatchesResponse
from football_data_mcp.services.mobile_service import MobileAnalysisService


logger = logging.getLogger("football_data_mcp.api.mobile")


def register(mcp: SupportsCustomRoute) -> list[dict[str, object]]:
    routes = [
        ("/api/mobile/matches", ["GET", "OPTIONS"], mobile_matches_api),
        ("/api/mobile/analysis", ["GET", "OPTIONS"], mobile_analysis_api),
    ]
    for path, methods, handler in routes:
        mcp.custom_route(path, methods=methods, include_in_schema=False)(handler)
    return [route(path, methods) for path, methods, _ in routes]


async def mobile_matches_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        result = await MobileAnalysisService().matches(
            query=request.query_params.get("query") or "",
            league=request.query_params.get("league") or None,
            as_of=request.query_params.get("as_of") or None,
            timezone_name=request.query_params.get("timezone") or "Asia/Shanghai",
            window_hours=int(request.query_params.get("window_hours") or 24),
            limit=int(request.query_params.get("limit") or 30),
            analysis_ready_only=not bool_query(request.query_params.get("include_unready")),
        )
        return success_json(MobileMatchesResponse.model_validate(result), headers=headers)
    except Exception as exc:
        logger.error("mobile_matches error: %s", exc)
        return api_error_response(exc, headers=headers)


async def mobile_analysis_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        query = request.query_params.get("query") or ""
        if not query:
            home = request.query_params.get("home_team") or "主队"
            away = request.query_params.get("away_team") or "客队"
            query = f"{home} vs {away}"
        result = await MobileAnalysisService().analysis(
            query=query,
            home_team=request.query_params.get("home_team") or None,
            away_team=request.query_params.get("away_team") or None,
            league=request.query_params.get("league") or None,
            as_of=request.query_params.get("as_of") or None,
            timezone_name=request.query_params.get("timezone") or "Asia/Shanghai",
            window_hours=int(request.query_params.get("window_hours") or 24),
            include_raw=bool_query(request.query_params.get("include_raw")),
        )
        return success_json(MobileAnalysisResponse.model_validate(result), headers=headers)
    except Exception as exc:
        logger.error("mobile_analysis error: %s", exc)
        return api_error_response(exc, headers=headers)

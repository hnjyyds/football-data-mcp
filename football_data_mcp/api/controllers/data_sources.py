from __future__ import annotations

import json
import logging

from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import Response

from football_data_mcp.api.controllers._helpers import api_error_response, headers_for, options_response, route
from football_data_mcp.api.registry import SupportsCustomRoute
from football_data_mcp.api.schemas.common import success_json
from football_data_mcp.api.schemas.data_sources import (
    BetExplorerSyncRequest,
    BetExplorerSyncResponse,
    FdoMatchesQuery,
    FdoMatchesResponse,
    LeisuSessionRefreshRequest,
    LeisuSessionRefreshResponse,
    OddsPortalSyncRequest,
    OddsPortalSyncResponse,
    OddsSourceStatusResponse,
    SourcesProbeResponse,
)
from football_data_mcp.core.errors import RequestValidationAppError
from football_data_mcp.services.data_source_service import DataSourceService


logger = logging.getLogger("football_data_mcp.api.data_sources")


def register(mcp: SupportsCustomRoute) -> list[dict[str, object]]:
    routes = [
        ("/api/fdo/matches", ["GET", "OPTIONS"], fdo_matches_api),
        ("/api/sources/probe", ["GET", "OPTIONS"], sources_probe_api),
        ("/api/sources/odds/status", ["GET", "OPTIONS"], odds_source_status_api),
        ("/api/sources/odds/oddsportal/sync", ["POST", "OPTIONS"], oddsportal_sync_api),
        ("/api/sources/odds/betexplorer/sync", ["POST", "OPTIONS"], betexplorer_sync_api),
        ("/api/sources/odds/leisu/session/refresh", ["POST", "OPTIONS"], leisu_session_refresh_api),
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


async def odds_source_status_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        result = DataSourceService().odds_source_status()
        return success_json(OddsSourceStatusResponse.model_validate(result), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)


async def oddsportal_sync_api(request: Request) -> Response:
    headers = headers_for(request, allow_methods="POST, OPTIONS")
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        try:
            payload = await request.json()
        except json.JSONDecodeError as exc:
            raise RequestValidationAppError(
                code="invalid_json_body",
                message="Request body must be valid JSON.",
                details={"reason": str(exc)},
            ) from exc
        try:
            parsed = OddsPortalSyncRequest.model_validate(payload or {})
        except ValidationError as exc:
            raise RequestValidationAppError(
                code="request_validation_failed",
                message="Request body did not match the OddsPortal sync schema.",
                details={"errors": exc.errors()},
            ) from exc
        result = await DataSourceService().start_oddsportal_sync(
            event_urls=parsed.event_urls,
            markets=parsed.markets,
            limit=parsed.limit,
            force=parsed.force,
            resume_failed=parsed.resume_failed,
            resume_statuses=parsed.resume_statuses,
            auto_discover=parsed.auto_discover,
            discovery_urls=parsed.discovery_urls,
            target_limit=parsed.target_limit,
            start_background=parsed.start,
        )
        return success_json(OddsPortalSyncResponse.model_validate(result), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)


async def betexplorer_sync_api(request: Request) -> Response:
    headers = headers_for(request, allow_methods="POST, OPTIONS")
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        try:
            payload = await request.json()
        except json.JSONDecodeError as exc:
            raise RequestValidationAppError(
                code="invalid_json_body",
                message="Request body must be valid JSON.",
                details={"reason": str(exc)},
            ) from exc
        try:
            parsed = BetExplorerSyncRequest.model_validate(payload or {})
        except ValidationError as exc:
            raise RequestValidationAppError(
                code="request_validation_failed",
                message="Request body did not match the BetExplorer sync schema.",
                details={"errors": exc.errors()},
            ) from exc
        result = await DataSourceService().start_betexplorer_sync(
            event_urls=parsed.event_urls,
            markets=parsed.markets,
            limit=parsed.limit,
            force=parsed.force,
        )
        return success_json(BetExplorerSyncResponse.model_validate(result), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)


async def leisu_session_refresh_api(request: Request) -> Response:
    headers = headers_for(request, allow_methods="POST, OPTIONS")
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        try:
            payload = await request.json()
        except json.JSONDecodeError as exc:
            raise RequestValidationAppError(
                code="invalid_json_body",
                message="Request body must be valid JSON.",
                details={"reason": str(exc)},
            ) from exc
        try:
            parsed = LeisuSessionRefreshRequest.model_validate(payload or {})
        except ValidationError as exc:
            raise RequestValidationAppError(
                code="request_validation_failed",
                message="Request body did not match the Leisu session refresh schema.",
                details={"errors": exc.errors()},
            ) from exc
        result = await DataSourceService().start_leisu_session_refresh(
            match_id=parsed.match_id,
            url=parsed.url,
            profile_dir=parsed.profile_dir,
            headless=parsed.headless,
            start_background=parsed.start,
        )
        return success_json(LeisuSessionRefreshResponse.model_validate(result), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)

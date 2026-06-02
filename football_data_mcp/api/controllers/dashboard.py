from __future__ import annotations

import logging
import time
from collections.abc import Callable
from urllib.parse import unquote

from starlette.requests import Request
from starlette.responses import Response

from football_data_mcp.api.controllers._helpers import api_error_response, headers_for, options_response, route
from football_data_mcp.api.registry import SupportsCustomRoute
from football_data_mcp.api.schemas.common import success_json
from football_data_mcp.api.schemas.dashboard import (
    DashboardMatchResponse,
    DashboardLarkPredictionResponse,
    DashboardRecordResponse,
    DashboardSnapshotResponse,
    DashboardSummaryResponse,
)
from football_data_mcp.services.dashboard_service import DashboardReadService
from football_data_mcp.services.lark_notification_service import LarkNotificationService


logger = logging.getLogger("football_data_mcp.api.dashboard")
LarkNotificationServiceFactory = Callable[[], LarkNotificationService]
_lark_notification_service_factory: LarkNotificationServiceFactory = LarkNotificationService


def configure_dashboard_dependencies(
    *,
    lark_notification_service_factory: LarkNotificationServiceFactory | None = None,
) -> None:
    """Inject optional dashboard side-effect services for tests and alternate runtimes."""
    global _lark_notification_service_factory
    _lark_notification_service_factory = lark_notification_service_factory or LarkNotificationService


def _truthy_query_flag(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def register(mcp: SupportsCustomRoute) -> list[dict[str, object]]:
    routes = [
        ("/api/dashboard/summary", ["GET", "OPTIONS"], dashboard_summary_api),
        ("/api/dashboard", ["GET", "OPTIONS"], dashboard_api),
        ("/api/dashboard/record/{record_id}", ["GET", "OPTIONS"], dashboard_record_api),
        ("/api/dashboard/match/{ledger_id}", ["GET", "OPTIONS"], dashboard_match_api),
        ("/api/dashboard/match/{ledger_id}/lark", ["POST", "OPTIONS"], dashboard_match_lark_api),
    ]
    for path, methods, handler in routes:
        mcp.custom_route(path, methods=methods, include_in_schema=False)(handler)
    return [route(path, methods) for path, methods, _ in routes]


async def dashboard_summary_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        summary = await DashboardReadService().summary()
        return success_json(DashboardSummaryResponse(**summary), headers=headers)
    except Exception as exc:
        logger.error("dashboard_summary error: %s", exc)
        return api_error_response(exc, headers=headers)


async def dashboard_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        start = time.time()
        snapshot = await DashboardReadService().snapshot(
            force_refresh=_truthy_query_flag(request.query_params.get("refresh"))
        )
        logger.info("dashboard_api completed in %.2fs", time.time() - start)
        return success_json(DashboardSnapshotResponse.model_validate(snapshot), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)


async def dashboard_record_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        record_id = unquote(request.path_params.get("record_id", ""))
        detail = await DashboardReadService().record_detail(record_id)
        return success_json(DashboardRecordResponse.model_validate(detail), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)


async def dashboard_match_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        ledger_id = unquote(request.path_params.get("ledger_id", ""))
        detail = await DashboardReadService().match_detail(ledger_id)
        return success_json(DashboardMatchResponse.model_validate(detail), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)


async def dashboard_match_lark_api(request: Request) -> Response:
    headers = headers_for(request, allow_methods="POST, OPTIONS")
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        ledger_id = unquote(request.path_params.get("ledger_id", ""))
        result = await _lark_notification_service_factory().send_prediction(ledger_id)
        return success_json(DashboardLarkPredictionResponse.model_validate(result), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)

from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import Response

from football_data_mcp.api.controllers._helpers import api_error_response, bool_query, headers_for, options_response, route
from football_data_mcp.api.registry import SupportsCustomRoute
from football_data_mcp.api.schemas.common import success_json
from football_data_mcp.api.schemas.maintenance import DbJanitorQuery, DbJanitorResponse
from football_data_mcp.services.maintenance_service import MaintenanceService


logger = logging.getLogger("football_data_mcp.api.maintenance")


def register(mcp: SupportsCustomRoute) -> list[dict[str, object]]:
    path = "/api/db/janitor"
    methods = ["GET", "POST", "OPTIONS"]
    mcp.custom_route(path, methods=methods, include_in_schema=False)(db_janitor_api)
    return [route(path, methods)]


async def db_janitor_api(request: Request) -> Response:
    headers = headers_for(request, allow_methods="GET, POST, OPTIONS")
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        query = DbJanitorQuery(
            execute=request.method == "POST" and bool_query(request.query_params.get("execute")),
        )
        report = await MaintenanceService().run_db_janitor(
            execute=query.execute,
            provided_admin_token=request.headers.get("x-admin-token", ""),
        )
        totals = report.get("totals") or {}
        logger.info(
            "db_janitor_api: dry_run=%s deleted=%d marked=%d",
            not query.execute,
            totals.get("deleted", 0),
            totals.get("marked", 0),
        )
        return success_json(DbJanitorResponse.model_validate(report), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)

from __future__ import annotations

from urllib.parse import unquote

from starlette.requests import Request
from starlette.responses import Response

from football_data_mcp.api.controllers._helpers import api_error_response, bool_query, headers_for, options_response, route
from football_data_mcp.api.registry import SupportsCustomRoute
from football_data_mcp.api.schemas.ai_analysis import (
    AIMatchAnalysisResponse,
    AIMatchLiveResponse,
    AIMatchOddsResponse,
    AIMatchesWindowResponse,
    AIOddsSourceStatusResponse,
    AIReviewMatchResponse,
    AIReviewSummaryResponse,
    AIShortlistResponse,
)
from football_data_mcp.api.schemas.common import success_json
from football_data_mcp.services.ai_analysis_service import AIAnalysisService


def register(mcp: SupportsCustomRoute) -> list[dict[str, object]]:
    routes = [
        ("/api/ai/matches/window", ["GET", "OPTIONS"], ai_matches_window_api),
        ("/api/ai/shortlist", ["GET", "OPTIONS"], ai_shortlist_api),
        ("/api/ai/match/analysis", ["GET", "OPTIONS"], ai_match_analysis_api),
        ("/api/ai/match/odds", ["GET", "OPTIONS"], ai_match_odds_api),
        ("/api/ai/match/live", ["GET", "OPTIONS"], ai_match_live_api),
        ("/api/ai/review/summary", ["GET", "OPTIONS"], ai_review_summary_api),
        ("/api/ai/review/match/{ledger_id}", ["GET", "OPTIONS"], ai_review_match_api),
        ("/api/ai/odds-source-status", ["GET", "OPTIONS"], ai_odds_source_status_api),
    ]
    for path, methods, handler in routes:
        mcp.custom_route(path, methods=methods, include_in_schema=False)(handler)
    return [route(path, methods) for path, methods, _ in routes]


async def ai_matches_window_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        result = await AIAnalysisService().matches_window(
            query=request.query_params.get("query") or "",
            league=request.query_params.get("league") or None,
            as_of=request.query_params.get("as_of") or None,
            timezone_name=request.query_params.get("timezone_name") or "Asia/Shanghai",
            window_hours=int(request.query_params.get("window_hours") or 6),
            limit=int(request.query_params.get("limit") or 24),
            analysis_ready_only=((request.query_params.get("analysis_ready_only") or "").strip().lower() not in {"0", "false", "no", "off"}),
        )
        return success_json(AIMatchesWindowResponse.model_validate(result), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)


async def ai_shortlist_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        result = await AIAnalysisService().shortlist(
            query=request.query_params.get("query") or "",
            league=request.query_params.get("league") or None,
            as_of=request.query_params.get("as_of") or None,
            timezone_name=request.query_params.get("timezone_name") or "Asia/Shanghai",
            window_minutes=int(request.query_params.get("window_minutes") or 360),
            top_n=int(request.query_params.get("top_n") or 5),
            limit=int(request.query_params.get("limit") or 40),
            mode=request.query_params.get("mode") or "confidence",
            target_market=request.query_params.get("target_market") or "1x2",
            min_calibrated_probability=float(request.query_params.get("min_calibrated_probability") or 0.58),
            min_decimal_odds=float(request.query_params.get("min_decimal_odds") or 1.65),
            max_decimal_odds=float(request.query_params.get("max_decimal_odds") or 2.05),
            min_value_edge=float(request.query_params.get("min_value_edge") or 0.02),
            analysis_candidate_limit=int(request.query_params.get("analysis_candidate_limit") or 40),
            analysis_concurrency=int(request.query_params.get("analysis_concurrency") or 8),
            analysis_timeout_seconds=float(request.query_params.get("analysis_timeout_seconds") or 45.0),
            use_learning_policy=((request.query_params.get("use_learning_policy") or "").strip().lower() not in {"0", "false", "no", "off"}),
            require_core_markets=((request.query_params.get("require_core_markets") or "").strip().lower() not in {"0", "false", "no", "off"}),
        )
        return success_json(AIShortlistResponse.model_validate(result), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)


async def ai_match_analysis_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        result = await AIAnalysisService().match_analysis(
            query=request.query_params.get("query") or "",
            home_team=request.query_params.get("home_team") or None,
            away_team=request.query_params.get("away_team") or None,
            league=request.query_params.get("league") or None,
            as_of=request.query_params.get("as_of") or None,
            timezone_name=request.query_params.get("timezone_name") or "Asia/Shanghai",
            window_hours=int(request.query_params.get("window_hours") or 24),
            include_source_probe=bool_query(request.query_params.get("include_source_probe")),
        )
        return success_json(AIMatchAnalysisResponse.model_validate(result), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)


async def ai_match_odds_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        result = await AIAnalysisService().match_odds(
            query=request.query_params.get("query") or "",
            home_team=request.query_params.get("home_team") or None,
            away_team=request.query_params.get("away_team") or None,
            league=request.query_params.get("league") or None,
            as_of=request.query_params.get("as_of") or None,
            timezone_name=request.query_params.get("timezone_name") or "Asia/Shanghai",
            window_hours=int(request.query_params.get("window_hours") or 24),
        )
        return success_json(AIMatchOddsResponse.model_validate(result), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)


async def ai_match_live_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        result = await AIAnalysisService().match_live(
            query=request.query_params.get("query") or "",
            home_team=request.query_params.get("home_team") or None,
            away_team=request.query_params.get("away_team") or None,
            league=request.query_params.get("league") or None,
            as_of=request.query_params.get("as_of") or None,
            timezone_name=request.query_params.get("timezone_name") or "Asia/Shanghai",
            lookback_hours=float(request.query_params.get("lookback_hours") or 4),
            window_hours=float(request.query_params.get("window_hours") or 8),
            leisu_match_id=request.query_params.get("leisu_match_id") or None,
            include_odds=(
                (request.query_params.get("include_odds") or "").strip().lower()
                not in {"0", "false", "no", "off"}
            ),
        )
        return success_json(AIMatchLiveResponse.model_validate(result), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)


async def ai_review_summary_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        result = await AIAnalysisService().review_summary(refresh=bool_query(request.query_params.get("refresh")))
        return success_json(AIReviewSummaryResponse.model_validate(result), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)


async def ai_review_match_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        ledger_id = unquote(request.path_params.get("ledger_id", ""))
        result = await AIAnalysisService().review_match(ledger_id=ledger_id)
        return success_json(AIReviewMatchResponse.model_validate(result), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)


async def ai_odds_source_status_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        result = await AIAnalysisService().odds_source_status()
        return success_json(AIOddsSourceStatusResponse.model_validate(result), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)

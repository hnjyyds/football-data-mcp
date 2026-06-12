from __future__ import annotations

from typing import Any

from football_data_mcp import sources
from football_data_mcp.services.dashboard_service import DashboardReadService
from football_data_mcp.services.data_source_service import DataSourceService


class AIAnalysisService:
    """Thin orchestration layer for AI-facing analysis routes.

    The goal is not to invent new domain logic here. It packages existing
    source, dashboard, and health capabilities into a stable HTTP surface that
    an analysis agent can call repeatedly without reconstructing payloads.
    """

    def __init__(
        self,
        *,
        dashboard_service: DashboardReadService | None = None,
        data_source_service: DataSourceService | None = None,
    ) -> None:
        self._dashboard_service = dashboard_service or DashboardReadService()
        self._data_source_service = data_source_service or DataSourceService()

    async def matches_window(
        self,
        *,
        query: str = "",
        league: str | None = None,
        as_of: str | None = None,
        timezone_name: str = "Asia/Shanghai",
        window_hours: int = 6,
        limit: int = 24,
        analysis_ready_only: bool = True,
    ) -> dict[str, Any]:
        matches = await sources.list_matches(
            query=query or "",
            league=league or None,
            as_of=as_of or None,
            timezone_name=timezone_name or "Asia/Shanghai",
            window_hours=window_hours or 6,
            limit=limit or 24,
            analysis_ready_only=analysis_ready_only,
        )
        odds_status = self._data_source_service.odds_source_status()
        closure = odds_status.get("closure") if isinstance(odds_status, dict) else {}
        return {
            "status": "ok",
            "tool": "ai_matches_window",
            "query": query or "",
            "league": league or "",
            "timezone_name": timezone_name or "Asia/Shanghai",
            "window_hours": window_hours or 6,
            "analysis_ready_only": analysis_ready_only,
            "matches": matches,
            "odds_source_closure": {
                "active_source": closure.get("active_source"),
                "production_ready": closure.get("production_ready"),
                "reason": closure.get("reason"),
                "checked_at_utc": closure.get("checked_at_utc"),
            },
        }

    async def shortlist(
        self,
        *,
        query: str = "",
        league: str | None = None,
        as_of: str | None = None,
        timezone_name: str = "Asia/Shanghai",
        window_minutes: int = 360,
        top_n: int = 5,
        limit: int = 40,
        mode: str = "balanced",
        target_market: str = "asian_handicap",
        min_calibrated_probability: float = 0.58,
        min_decimal_odds: float = 1.65,
        max_decimal_odds: float = 2.05,
        min_value_edge: float = 0.02,
        analysis_candidate_limit: int = 40,
        analysis_concurrency: int = 8,
        analysis_timeout_seconds: float = 45.0,
        use_learning_policy: bool = True,
        require_core_markets: bool = True,
    ) -> dict[str, Any]:
        result = await sources.shortlist_value_matches(
            query=query or "",
            league=league or None,
            as_of=as_of or None,
            timezone_name=timezone_name or "Asia/Shanghai",
            window_minutes=window_minutes or 360,
            top_n=top_n or 5,
            limit=limit or 40,
            mode=mode or "balanced",
            target_market=target_market or "asian_handicap",
            min_calibrated_probability=min_calibrated_probability,
            min_decimal_odds=min_decimal_odds,
            max_decimal_odds=max_decimal_odds,
            min_value_edge=min_value_edge,
            analysis_candidate_limit=analysis_candidate_limit or 40,
            analysis_concurrency=analysis_concurrency or 8,
            analysis_timeout_seconds=analysis_timeout_seconds or 45.0,
            use_learning_policy=use_learning_policy,
            require_core_markets=require_core_markets,
        )
        return {
            **result,
            "tool": "ai_shortlist",
        }

    async def match_analysis(
        self,
        *,
        query: str,
        home_team: str | None = None,
        away_team: str | None = None,
        league: str | None = None,
        as_of: str | None = None,
        timezone_name: str = "Asia/Shanghai",
        window_hours: int = 24,
        include_source_probe: bool = False,
    ) -> dict[str, Any]:
        result = await sources.analyze_single_match(
            query,
            home_team=home_team or None,
            away_team=away_team or None,
            league=league or None,
            as_of=as_of or None,
            timezone_name=timezone_name or "Asia/Shanghai",
            window_hours=window_hours or 24,
            include_source_probe=include_source_probe,
        )
        result["tool"] = "ai_match_analysis"
        return result

    async def match_odds(
        self,
        *,
        query: str,
        home_team: str | None = None,
        away_team: str | None = None,
        league: str | None = None,
        as_of: str | None = None,
        timezone_name: str = "Asia/Shanghai",
        window_hours: int = 24,
    ) -> dict[str, Any]:
        best, search = await sources.get_best_match(
            query,
            home_team=home_team or None,
            away_team=away_team or None,
            league=league or None,
            as_of=as_of or None,
            timezone_name=timezone_name or "Asia/Shanghai",
            window_hours=window_hours or 24,
        )
        if not best:
            return {"status": "not_found", "tool": "ai_match_odds", "search": search}
        odds = best.get("odds_summary") or {}
        match_context = None
        if best.get("source_name") == "dongqiudi" and best.get("match_id"):
            match_context = await sources.dongqiudi_match_context(str(best["match_id"]))
            odds = sources.merge_odds(odds, ((match_context.get("odds_index") or {}).get("odds") or {}))
        return {
            "status": "ok",
            "tool": "ai_match_odds",
            "match": best,
            "time_window": best.get("time_window"),
            "time_window_policy": search.get("time_window_policy"),
            "odds": odds,
            "match_context_readiness": (match_context or {}).get("readiness") or {},
        }

    async def review_summary(self, *, refresh: bool = False) -> dict[str, Any]:
        snapshot = await self._dashboard_service.snapshot(force_refresh=refresh)
        return {
            "status": "ok",
            "tool": "ai_review_summary",
            "generated_at_utc": snapshot.get("generated_at_utc"),
            "production_readiness": snapshot.get("production_readiness"),
            "recommendation_opportunity": snapshot.get("recommendation_opportunity"),
            "learning_effectiveness": snapshot.get("learning_effectiveness"),
            "prediction_kpis": snapshot.get("prediction_kpis"),
            "strategy_state": snapshot.get("strategy_state"),
            "odds_source_status": snapshot.get("odds_source_status"),
            "dashboard_cache": snapshot.get("dashboard_cache"),
        }

    async def review_match(self, *, ledger_id: str) -> dict[str, Any]:
        detail = await self._dashboard_service.match_detail(ledger_id)
        detail["tool"] = "ai_review_match"
        return detail

    async def odds_source_status(self) -> dict[str, Any]:
        result = self._data_source_service.odds_source_status()
        result["tool"] = "ai_odds_source_status"
        return result

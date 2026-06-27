from __future__ import annotations

import asyncio
import json

from starlette.requests import Request

from football_data_mcp.services.ai_analysis_service import AIAnalysisService
from football_data_mcp.api.controllers import ai_analysis as controller


def _request(
    path: str,
    *,
    method: str = "GET",
    path_params: dict[str, str] | None = None,
    query_string: str = "",
    headers: dict[str, str] | None = None,
) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [
                (name.lower().encode("latin-1"), value.encode("latin-1"))
                for name, value in (headers or {}).items()
            ],
            "query_string": query_string.encode("latin-1"),
            "path_params": path_params or {},
        }
    )


class _FakeService:
    async def matches_window(self, **kwargs):
        return {"status": "ok", "tool": "ai_matches_window", "echo": kwargs}

    async def shortlist(self, **kwargs):
        return {"status": "ok", "tool": "ai_shortlist", "echo": kwargs}

    async def match_analysis(self, **kwargs):
        return {"status": "ok", "tool": "ai_match_analysis", "echo": kwargs}

    async def match_odds(self, **kwargs):
        return {"status": "ok", "tool": "ai_match_odds", "echo": kwargs}

    async def match_live(self, **kwargs):
        return {"status": "ok", "tool": "ai_match_live", "echo": kwargs}

    async def review_summary(self, **kwargs):
        return {"status": "ok", "tool": "ai_review_summary", "echo": kwargs}

    async def review_match(self, **kwargs):
        return {"status": "ok", "tool": "ai_review_match", "echo": kwargs}

    async def odds_source_status(self, **kwargs):
        return {"status": "ok", "tool": "ai_odds_source_status", "echo": kwargs}


def test_ai_analysis_registers_routes():
    class FakeMCP:
        def __init__(self):
            self.routes = {}

        def custom_route(self, path: str, *, methods: list[str], include_in_schema: bool):
            def decorator(func):
                self.routes[path] = {"methods": methods, "handler": func}
                return func

            return decorator

    fake = FakeMCP()
    registered = controller.register(fake)

    assert "/api/ai/matches/window" in fake.routes
    assert "/api/ai/shortlist" in fake.routes
    assert "/api/ai/match/live" in fake.routes
    assert "/api/ai/review/match/{ledger_id}" in fake.routes
    assert len(registered) == 8


def test_ai_matches_window_api_uses_service(monkeypatch):
    monkeypatch.setattr(controller, "AIAnalysisService", lambda: _FakeService())

    response = asyncio.run(
        controller.ai_matches_window_api(
            _request("/api/ai/matches/window", query_string="query=test&window_hours=12&limit=9&analysis_ready_only=false")
        )
    )
    body = json.loads(response.body)

    assert body["tool"] == "ai_matches_window"
    assert body["echo"]["query"] == "test"
    assert body["echo"]["window_hours"] == 12
    assert body["echo"]["limit"] == 9
    assert body["echo"]["analysis_ready_only"] is False


def test_ai_shortlist_api_uses_service(monkeypatch):
    monkeypatch.setattr(controller, "AIAnalysisService", lambda: _FakeService())

    response = asyncio.run(
        controller.ai_shortlist_api(
            _request(
                "/api/ai/shortlist",
                query_string="mode=balanced&target_market=asian_handicap&window_minutes=180&top_n=4",
            )
        )
    )
    body = json.loads(response.body)

    assert body["tool"] == "ai_shortlist"
    assert body["echo"]["mode"] == "balanced"
    assert body["echo"]["target_market"] == "asian_handicap"
    assert body["echo"]["window_minutes"] == 180
    assert body["echo"]["top_n"] == 4


def test_ai_shortlist_api_defaults_to_jingcai_1x2(monkeypatch):
    monkeypatch.setattr(controller, "AIAnalysisService", lambda: _FakeService())

    response = asyncio.run(
        controller.ai_shortlist_api(
            _request("/api/ai/shortlist")
        )
    )
    body = json.loads(response.body)

    assert body["tool"] == "ai_shortlist"
    assert body["echo"]["mode"] == "confidence"
    assert body["echo"]["target_market"] == "1x2"


def test_ai_analysis_service_shortlist_defaults_to_jingcai_1x2(monkeypatch):
    calls = []

    async def fake_shortlist_value_matches(**kwargs):
        calls.append(kwargs)
        return {"status": "ok", "tool": "shortlist_value_matches"}

    from football_data_mcp import sources as sources_module

    monkeypatch.setattr(sources_module, "shortlist_value_matches", fake_shortlist_value_matches)

    result = asyncio.run(AIAnalysisService().shortlist())

    assert result["tool"] == "ai_shortlist"
    assert calls[0]["mode"] == "confidence"
    assert calls[0]["target_market"] == "1x2"


def test_ai_analysis_service_shortlist_rejects_asian_handicap(monkeypatch):
    async def fake_shortlist_value_matches(**kwargs):
        return {
            "status": "unsupported_market",
            "tool": "shortlist_value_matches",
            "target_market": kwargs["target_market"],
            "supported_target_markets": ["1x2", "jingcai_hhad", "over_under", "any"],
            "picks": [],
        }

    from football_data_mcp import sources as sources_module

    monkeypatch.setattr(sources_module, "shortlist_value_matches", fake_shortlist_value_matches)

    result = asyncio.run(AIAnalysisService().shortlist(target_market="asian_handicap"))

    assert result["tool"] == "ai_shortlist"
    assert result["status"] == "unsupported_market"
    assert result["target_market"] == "asian_handicap"
    assert result["picks"] == []


def test_ai_review_match_decodes_ledger_id(monkeypatch):
    monkeypatch.setattr(controller, "AIAnalysisService", lambda: _FakeService())

    response = asyncio.run(
        controller.ai_review_match_api(
            _request(
                "/api/ai/review/match/recommendation%3A1",
                path_params={"ledger_id": "recommendation%3A1"},
            )
        )
    )
    body = json.loads(response.body)

    assert body["tool"] == "ai_review_match"
    assert body["echo"]["ledger_id"] == "recommendation:1"


def test_ai_match_analysis_api_parses_include_source_probe(monkeypatch):
    monkeypatch.setattr(controller, "AIAnalysisService", lambda: _FakeService())

    response = asyncio.run(
        controller.ai_match_analysis_api(
            _request("/api/ai/match/analysis", query_string="query=liverpool&include_source_probe=true")
        )
    )
    body = json.loads(response.body)

    assert body["tool"] == "ai_match_analysis"
    assert body["echo"]["query"] == "liverpool"
    assert body["echo"]["include_source_probe"] is True


def test_ai_match_live_api_uses_service(monkeypatch):
    monkeypatch.setattr(controller, "AIAnalysisService", lambda: _FakeService())

    response = asyncio.run(
        controller.ai_match_live_api(
            _request(
                "/api/ai/match/live",
                query_string=(
                    "query=iran&lookback_hours=3&window_hours=7"
                    "&leisu_match_id=123&include_odds=false"
                ),
            )
        )
    )
    body = json.loads(response.body)

    assert body["tool"] == "ai_match_live"
    assert body["echo"]["query"] == "iran"
    assert body["echo"]["lookback_hours"] == 3
    assert body["echo"]["window_hours"] == 7
    assert body["echo"]["leisu_match_id"] == "123"
    assert body["echo"]["include_odds"] is False

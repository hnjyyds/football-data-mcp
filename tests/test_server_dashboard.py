from __future__ import annotations

import asyncio
import json

from starlette.requests import Request

from football_data_mcp import server


def _request(method: str = "GET", path_params: dict[str, str] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/api/dashboard",
            "headers": [],
            "path_params": path_params or {},
        }
    )


def test_dashboard_routes_read_snapshots_off_event_loop(monkeypatch):
    calls: list[str] = []

    async def fake_to_thread(func, *args, **kwargs):
        calls.append(func.__name__)
        return func(*args, **kwargs)

    monkeypatch.setattr(server.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(server.sources, "dashboard_snapshot", lambda: {"status": "ok", "tool": "dashboard_snapshot"})
    monkeypatch.setattr(
        server.sources,
        "dashboard_match_detail",
        lambda ledger_id: {"status": "ok", "tool": "dashboard_match_detail", "ledger_id": ledger_id},
    )

    snapshot_response = asyncio.run(server.dashboard_api(_request()))
    detail_response = asyncio.run(server.dashboard_match_api(_request(path_params={"ledger_id": "recommendation:1"})))

    assert calls == ["<lambda>", "<lambda>"]
    assert json.loads(snapshot_response.body)["tool"] == "dashboard_snapshot"
    assert json.loads(detail_response.body)["ledger_id"] == "recommendation:1"


def test_dashboard_match_route_decodes_encoded_ledger_id(monkeypatch):
    seen: list[str] = []

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    def fake_detail(ledger_id):
        seen.append(ledger_id)
        return {"status": "ok", "tool": "dashboard_match_detail", "ledger_id": ledger_id}

    monkeypatch.setattr(server.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(server.sources, "dashboard_match_detail", fake_detail)

    detail_response = asyncio.run(server.dashboard_match_api(_request(path_params={"ledger_id": "recommendation%3A106"})))

    assert seen == ["recommendation:106"]
    assert json.loads(detail_response.body)["ledger_id"] == "recommendation:106"

from __future__ import annotations

import asyncio
import json

from starlette.requests import Request

from football_data_mcp import server


def _request(
    method: str = "GET",
    path_params: dict[str, str] | None = None,
    *,
    headers: dict[str, str] | None = None,
    query_string: str = "",
) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/api/dashboard",
            "headers": [
                (name.lower().encode("latin-1"), value.encode("latin-1"))
                for name, value in (headers or {}).items()
            ],
            "query_string": query_string.encode("latin-1"),
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


def test_dashboard_cors_reflects_trusted_origin_only(monkeypatch):
    monkeypatch.delenv("FOOTBALL_DATA_DASHBOARD_CORS_ORIGINS", raising=False)

    trusted = server._dashboard_cors_headers(_request(headers={"Origin": "http://localhost:8920"}))
    untrusted = server._dashboard_cors_headers(_request(headers={"Origin": "https://evil.example"}))

    assert trusted["Access-Control-Allow-Origin"] == "http://localhost:8920"
    assert "Access-Control-Allow-Origin" not in untrusted


def test_dashboard_summary_errors_use_unified_response(monkeypatch):
    def boom():
        raise RuntimeError("db exploded")

    monkeypatch.setattr(server.sources, "dashboard_snapshot", boom)

    response = asyncio.run(server.dashboard_summary_api(_request()))
    body = json.loads(response.body)

    assert response.status_code == 500
    assert body["status"] == "error"
    assert body["error"]["code"] == "dashboard_summary_failed"
    assert "generated_at_utc" in body


def test_dashboard_match_not_found_uses_unified_error(monkeypatch):
    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(server.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(server.sources, "dashboard_match_detail", lambda ledger_id: {"status": "not_found"})

    response = asyncio.run(server.dashboard_match_api(_request(path_params={"ledger_id": "missing"})))
    body = json.loads(response.body)

    assert response.status_code == 404
    assert body["status"] == "error"
    assert body["error"]["code"] == "dashboard_match_not_found"


def test_db_janitor_execute_requires_configured_admin_token(monkeypatch):
    async def fake_to_thread(func, *args, **kwargs):
        return {"totals": {"deleted": 0, "marked": 0}, "dry_run": kwargs.get("dry_run")}

    monkeypatch.setattr(server.asyncio, "to_thread", fake_to_thread)
    monkeypatch.delenv("FOOTBALL_DATA_ADMIN_TOKEN", raising=False)

    response = asyncio.run(server.db_janitor_api(_request(method="POST", query_string="execute=true")))
    body = json.loads(response.body)

    assert response.status_code == 403
    assert body["error"]["code"] == "admin_token_not_configured"


def test_db_janitor_execute_accepts_matching_admin_token(monkeypatch):
    async def fake_to_thread(func, *args, **kwargs):
        return {"totals": {"deleted": 0, "marked": 0}, "dry_run": kwargs.get("dry_run")}

    monkeypatch.setattr(server.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setenv("FOOTBALL_DATA_ADMIN_TOKEN", "secret")

    response = asyncio.run(
        server.db_janitor_api(
            _request(
                method="POST",
                headers={"X-Admin-Token": "secret"},
                query_string="execute=true",
            )
        )
    )
    body = json.loads(response.body)

    assert response.status_code == 200
    assert body["dry_run"] is False

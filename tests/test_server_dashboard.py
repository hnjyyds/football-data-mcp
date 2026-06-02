from __future__ import annotations

import asyncio
import json
import time

from starlette.requests import Request

from football_data_mcp import server
from football_data_mcp.services import dashboard_service
from football_data_mcp.services.dashboard_service import DashboardReadService, clear_dashboard_snapshot_cache


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
    clear_dashboard_snapshot_cache()
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


def test_dashboard_route_reuses_short_lived_snapshot_cache(monkeypatch):
    clear_dashboard_snapshot_cache()
    calls: list[str] = []

    async def fake_to_thread(func, *args, **kwargs):
        calls.append(func.__name__)
        return func(*args, **kwargs)

    monkeypatch.setattr(server.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(server.sources, "dashboard_snapshot", lambda: {"status": "ok", "tool": "dashboard_snapshot"})

    first = asyncio.run(server.dashboard_api(_request()))
    second = asyncio.run(server.dashboard_api(_request()))

    assert calls == ["<lambda>"]
    assert json.loads(first.body)["tool"] == "dashboard_snapshot"
    assert json.loads(second.body)["tool"] == "dashboard_snapshot"
    clear_dashboard_snapshot_cache()


def test_dashboard_route_force_refresh_bypasses_short_lived_snapshot_cache(monkeypatch):
    clear_dashboard_snapshot_cache()
    calls: list[int] = []

    async def fake_to_thread(func, *args, **kwargs):
        calls.append(len(calls) + 1)
        return func(*args, **kwargs)

    def fake_snapshot():
        return {
            "status": "ok",
            "tool": "dashboard_snapshot",
            "generated_at_utc": f"run-{len(calls)}",
        }

    monkeypatch.setattr(server.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(server.sources, "dashboard_snapshot", fake_snapshot)

    first = asyncio.run(server.dashboard_api(_request()))
    forced = asyncio.run(server.dashboard_api(_request(query_string="refresh=true")))

    assert calls == [1, 2]
    assert json.loads(first.body)["generated_at_utc"] == "run-1"
    forced_body = json.loads(forced.body)
    assert forced_body["generated_at_utc"] == "run-2"
    assert forced_body["dashboard_cache"]["status"] == "refreshed"
    clear_dashboard_snapshot_cache()


def test_dashboard_route_coalesces_concurrent_snapshot_builds(monkeypatch):
    clear_dashboard_snapshot_cache()
    calls: list[str] = []

    async def fake_to_thread(func, *args, **kwargs):
        calls.append(func.__name__)
        await asyncio.sleep(0.01)
        return func(*args, **kwargs)

    monkeypatch.setattr(server.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(server.sources, "dashboard_snapshot", lambda: {"status": "ok", "tool": "dashboard_snapshot"})

    async def scenario():
        return await asyncio.gather(server.dashboard_api(_request()), server.dashboard_api(_request()))

    responses = asyncio.run(scenario())

    assert calls == ["<lambda>"]
    assert [json.loads(response.body)["tool"] for response in responses] == ["dashboard_snapshot", "dashboard_snapshot"]
    clear_dashboard_snapshot_cache()


def test_dashboard_snapshot_serves_stale_cache_while_refreshing(monkeypatch):
    clear_dashboard_snapshot_cache()
    monkeypatch.setattr(dashboard_service, "_DASHBOARD_CACHE_TTL_SECONDS", 0.0)
    monkeypatch.setattr(dashboard_service, "_DASHBOARD_CACHE_STALE_SECONDS", 60.0)
    calls: list[int] = []

    def reader():
        calls.append(len(calls) + 1)
        time.sleep(0.03)
        return {
            "status": "ok",
            "tool": "dashboard_snapshot",
            "generated_at_utc": f"run-{calls[-1]}",
        }

    class FakeRepository:
        def snapshot_reader(self):
            return reader

    service = DashboardReadService(FakeRepository())

    async def scenario():
        first = await service.snapshot()
        started = time.perf_counter()
        second = await service.snapshot()
        stale_elapsed = time.perf_counter() - started
        await asyncio.sleep(0.08)
        monkeypatch.setattr(dashboard_service, "_DASHBOARD_CACHE_TTL_SECONDS", 60.0)
        third = await service.snapshot()
        return first, second, third, stale_elapsed

    first, second, third, stale_elapsed = asyncio.run(scenario())

    assert first["generated_at_utc"] == "run-1"
    assert first["dashboard_cache"]["status"] == "fresh"
    assert second["generated_at_utc"] == "run-1"
    assert second["dashboard_cache"]["status"] == "stale_refreshing"
    assert stale_elapsed < 0.02
    assert third["generated_at_utc"] == "run-2"
    assert third["dashboard_cache"]["status"] == "fresh"
    assert calls == [1, 2]
    clear_dashboard_snapshot_cache()


def test_dashboard_force_refresh_wins_over_older_stale_background_refresh(monkeypatch):
    clear_dashboard_snapshot_cache()
    monkeypatch.setattr(dashboard_service, "_DASHBOARD_CACHE_TTL_SECONDS", 0.0)
    monkeypatch.setattr(dashboard_service, "_DASHBOARD_CACHE_STALE_SECONDS", 60.0)
    calls: list[int] = []

    def reader():
        call_id = len(calls) + 1
        calls.append(call_id)
        if call_id == 2:
            time.sleep(0.05)
        return {
            "status": "ok",
            "tool": "dashboard_snapshot",
            "generated_at_utc": f"run-{call_id}",
        }

    class FakeRepository:
        def snapshot_reader(self):
            return reader

    service = DashboardReadService(FakeRepository())

    async def scenario():
        first = await service.snapshot()
        stale = await service.snapshot()
        for _ in range(20):
            if len(calls) >= 2:
                break
            await asyncio.sleep(0.005)
        forced = await service.snapshot(force_refresh=True)
        await asyncio.sleep(0.08)
        monkeypatch.setattr(dashboard_service, "_DASHBOARD_CACHE_TTL_SECONDS", 60.0)
        after_background = await service.snapshot()
        return first, stale, forced, after_background

    first, stale, forced, after_background = asyncio.run(scenario())

    assert first["generated_at_utc"] == "run-1"
    assert stale["generated_at_utc"] == "run-1"
    assert forced["generated_at_utc"] == "run-3"
    assert forced["dashboard_cache"]["status"] == "refreshed"
    assert after_background["generated_at_utc"] == "run-3"
    assert calls == [1, 2, 3]
    clear_dashboard_snapshot_cache()


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


def test_health_api_reports_auto_learning_state_cycle_status(monkeypatch):
    monkeypatch.setattr(server, "learning_cycle_status", lambda: (None, None))
    monkeypatch.setattr(server.sources, "AUTO_LEARNING_STATE", {
        "last_finished_at_utc": "2026-05-29T00:24:24+00:00",
        "last_error": "TimeoutError:",
    })

    response = asyncio.run(server.health_api(_request()))
    body = json.loads(response.body)

    assert body["last_learning_cycle_at"] == "2026-05-29T00:24:24+00:00"
    assert body["last_learning_cycle_error"] == "TimeoutError:"
    assert body["task_queue"]["backend"] in {"thread", "arq"}


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

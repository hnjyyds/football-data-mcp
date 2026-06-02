from __future__ import annotations

import asyncio
import os
import threading
import time
from typing import Any

from football_data_mcp.core.errors import AppError, NotFoundError, ServiceExecutionError
from football_data_mcp.repositories.dashboard_repository import DashboardRepository


_DASHBOARD_CACHE_TTL_SECONDS = max(0.0, float(os.getenv("FOOTBALL_DATA_DASHBOARD_CACHE_TTL_SECONDS", "10") or 0))
_DASHBOARD_CACHE_STALE_SECONDS = max(
    _DASHBOARD_CACHE_TTL_SECONDS,
    float(os.getenv("FOOTBALL_DATA_DASHBOARD_CACHE_STALE_SECONDS", "120") or 0),
)
_DASHBOARD_CACHE_LOCK = threading.Lock()
_DASHBOARD_SNAPSHOT_CACHE: dict[tuple[int], tuple[float, dict[str, Any]]] = {}
_DASHBOARD_SNAPSHOT_INFLIGHT: dict[tuple[int, int], asyncio.Task[dict[str, Any]]] = {}


def clear_dashboard_snapshot_cache() -> None:
    """Clear shared HTTP snapshot cache for tests and explicit refresh flows."""
    with _DASHBOARD_CACHE_LOCK:
        _DASHBOARD_SNAPSHOT_CACHE.clear()
        _DASHBOARD_SNAPSHOT_INFLIGHT.clear()


def _snapshot_with_cache_meta(
    snapshot: dict[str, Any],
    *,
    fetched_at: float,
    status: str,
    now: float | None = None,
) -> dict[str, Any]:
    current = time.monotonic() if now is None else now
    result = dict(snapshot)
    result["dashboard_cache"] = {
        "status": status,
        "age_seconds": round(max(0.0, current - fetched_at), 3),
        "ttl_seconds": _DASHBOARD_CACHE_TTL_SECONDS,
        "stale_seconds": _DASHBOARD_CACHE_STALE_SECONDS,
    }
    return result


def _store_background_snapshot(
    *,
    cache_key: tuple[int],
    inflight_key: tuple[int, int],
    task: asyncio.Task[dict[str, Any]],
) -> None:
    try:
        snapshot = task.result()
    except Exception:
        snapshot = None
    with _DASHBOARD_CACHE_LOCK:
        current = _DASHBOARD_SNAPSHOT_INFLIGHT.get(inflight_key)
        if current is not task:
            return
        _DASHBOARD_SNAPSHOT_INFLIGHT.pop(inflight_key, None)
        if snapshot is not None:
            _DASHBOARD_SNAPSHOT_CACHE[cache_key] = (time.monotonic(), snapshot)


class DashboardReadService:
    def __init__(self, repository: DashboardRepository | None = None) -> None:
        self._repository = repository or DashboardRepository()

    async def summary(self) -> dict[str, Any]:
        """Return the compact dashboard summary used for fast first paint."""
        try:
            snapshot = await self.snapshot()
        except Exception as exc:
            reason = exc.message if isinstance(exc, AppError) else str(exc)
            raise ServiceExecutionError(
                code="dashboard_summary_failed",
                message="Dashboard summary could not be generated.",
                details={"reason": reason},
            ) from exc
        kpis = snapshot.get("kpis") or {}
        prediction_kpis = snapshot.get("prediction_kpis") or {}
        strategy_state = snapshot.get("strategy_state") or {}
        return {
            "status": "ok",
            "generated_at_utc": snapshot.get("generated_at_utc"),
            "kpis": {
                "open_records": kpis.get("open_records"),
                "settled_records": kpis.get("settled_records"),
                "asian_pick_count": kpis.get("asian_pick_count"),
                "live_calibration_active": kpis.get("live_calibration_active"),
            },
            "prediction_kpis": {
                "hit_rate": prediction_kpis.get("hit_rate"),
                "roi": prediction_kpis.get("roi"),
                "settled_count": prediction_kpis.get("settled_count"),
                "recommended_count": prediction_kpis.get("recommended_count"),
            },
            "strategy_status": strategy_state.get("status"),
            "strategy_sample_count": strategy_state.get("sample_count"),
        }

    async def snapshot(self, *, force_refresh: bool = False) -> dict[str, Any]:
        reader = self._repository.snapshot_reader()
        cache_key = (id(reader),)
        now = time.monotonic()
        if force_refresh:
            try:
                snapshot = await asyncio.to_thread(reader)
            except Exception as exc:
                raise ServiceExecutionError(
                    code="dashboard_snapshot_failed",
                    message="Dashboard snapshot could not be generated.",
                    details={"reason": str(exc)},
                ) from exc
            fetched_at = time.monotonic()
            with _DASHBOARD_CACHE_LOCK:
                _DASHBOARD_SNAPSHOT_CACHE[cache_key] = (fetched_at, snapshot)
                loop = asyncio.get_running_loop()
                _DASHBOARD_SNAPSHOT_INFLIGHT.pop((id(reader), id(loop)), None)
            return _snapshot_with_cache_meta(snapshot, fetched_at=fetched_at, status="refreshed")
        with _DASHBOARD_CACHE_LOCK:
            cached = _DASHBOARD_SNAPSHOT_CACHE.get(cache_key)
            loop = asyncio.get_running_loop()
            inflight_key = (id(reader), id(loop))
            task = _DASHBOARD_SNAPSHOT_INFLIGHT.get(inflight_key)
            if cached and now - cached[0] <= _DASHBOARD_CACHE_TTL_SECONDS:
                return _snapshot_with_cache_meta(cached[1], fetched_at=cached[0], status="fresh", now=now)
            if cached and now - cached[0] <= _DASHBOARD_CACHE_STALE_SECONDS:
                if task is None or task.done():
                    task = loop.create_task(asyncio.to_thread(reader))
                    task.add_done_callback(
                        lambda completed: _store_background_snapshot(
                            cache_key=cache_key,
                            inflight_key=inflight_key,
                            task=completed,
                        )
                    )
                    _DASHBOARD_SNAPSHOT_INFLIGHT[inflight_key] = task
                return _snapshot_with_cache_meta(cached[1], fetched_at=cached[0], status="stale_refreshing", now=now)
            if task is None or task.done():
                task = loop.create_task(asyncio.to_thread(reader))
                _DASHBOARD_SNAPSHOT_INFLIGHT[inflight_key] = task
        try:
            snapshot = await task
        except Exception as exc:
            with _DASHBOARD_CACHE_LOCK:
                current = _DASHBOARD_SNAPSHOT_INFLIGHT.get(inflight_key)
                if current is task:
                    _DASHBOARD_SNAPSHOT_INFLIGHT.pop(inflight_key, None)
            raise ServiceExecutionError(
                code="dashboard_snapshot_failed",
                message="Dashboard snapshot could not be generated.",
                details={"reason": str(exc)},
            ) from exc
        with _DASHBOARD_CACHE_LOCK:
            _DASHBOARD_SNAPSHOT_CACHE[cache_key] = (time.monotonic(), snapshot)
            current = _DASHBOARD_SNAPSHOT_INFLIGHT.get(inflight_key)
            if current is task:
                _DASHBOARD_SNAPSHOT_INFLIGHT.pop(inflight_key, None)
            fetched_at = time.monotonic()
        return _snapshot_with_cache_meta(snapshot, fetched_at=fetched_at, status="fresh")

    async def record_detail(self, record_id: str) -> dict[str, Any]:
        detail = await asyncio.to_thread(self._repository.record_detail_reader(), record_id)
        if detail.get("status") == "not_found":
            raise NotFoundError(
                code="dashboard_record_not_found",
                message="Dashboard recommendation record was not found.",
                details={"record_id": record_id},
            )
        return detail

    async def match_detail(self, ledger_id: str) -> dict[str, Any]:
        detail = await asyncio.to_thread(self._repository.match_detail_reader(), ledger_id)
        if detail.get("status") == "not_found":
            raise NotFoundError(
                code="dashboard_match_not_found",
                message="Dashboard prediction sample was not found.",
                details={"ledger_id": ledger_id},
            )
        return detail

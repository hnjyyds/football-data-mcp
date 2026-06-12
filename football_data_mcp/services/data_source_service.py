from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from football_data_mcp import browser_session_runtime
from football_data_mcp import betexplorer_source
from football_data_mcp import crawler_runtime_support
from football_data_mcp import oddsportal_source
from football_data_mcp.repositories.data_source_repository import DataSourceRepository
from football_data_mcp.services.task_queue import (
    OddsSourceSyncJobStarter,
    LeisuSessionRefreshJobStarter,
    build_odds_source_sync_job_starter,
    build_leisu_session_refresh_job_starter,
    leisu_session_refresh_job_start_result,
    odds_source_sync_job_start_result,
)


_SUPPORTED_ODDS_SYNC_MARKETS = frozenset({"h2h", "asian_handicap", "over_under"})
_PRODUCTION_ODDS_SOURCE_FRESH_HOURS = 6.0
_RUNNING_ODDS_SOURCE_JOBS: dict[str, threading.Thread] = {}
_RUNNING_ODDS_SOURCE_JOBS_LOCK = threading.Lock()
_RUNNING_LEISU_SESSION_JOBS: dict[str, threading.Thread] = {}
_RUNNING_LEISU_SESSION_JOBS_LOCK = threading.Lock()


class DataSourceService:
    def __init__(
        self,
        repository: DataSourceRepository | None = None,
        *,
        odds_sync_job_starter: OddsSourceSyncJobStarter | None = None,
        leisu_session_job_starter: LeisuSessionRefreshJobStarter | None = None,
    ) -> None:
        self._repository = repository or DataSourceRepository()
        self._odds_sync_job_starter = odds_sync_job_starter
        self._leisu_session_job_starter = leisu_session_job_starter

    async def fdo_matches(self, *, date_from: str | None, date_to: str | None) -> dict[str, Any]:
        return await self._repository.fetch_fdo_matches(date_from=date_from, date_to=date_to)

    async def source_probe(self) -> tuple[dict[str, Any], float]:
        start = time.time()
        result = await self._repository.probe_all_sources()
        return result, time.time() - start

    def odds_source_status(
        self,
        *,
        db_path: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        data = self._repository.odds_source_status(db_path=db_path)
        checked_at = now or datetime.now(timezone.utc)
        sync_state = data.get("sync_state") or {}
        provider_counts = data.get("provider_counts") or {}
        oddsportal_state = (sync_state.get("by_source") or {}).get("oddsportal_scraper") or {}
        betexplorer_state = (sync_state.get("by_source") or {}).get("betexplorer_scraper") or {}
        leisu_state = (sync_state.get("by_source") or {}).get("leisu") or {}
        oddsportal_readiness = self._oddsportal_discovery_readiness()
        betexplorer_readiness = self._betexplorer_discovery_readiness()
        fresh_after_hours = _odds_source_fresh_hours()
        betexplorer_fields = _betexplorer_operational_fields(
            provider_counts,
            betexplorer_state,
            sync_state,
            now=checked_at,
            fresh_after_hours=fresh_after_hours,
        )
        oddsportal_fields = _oddsportal_operational_fields(
            provider_counts,
            oddsportal_state,
            sync_state,
            readiness=oddsportal_readiness,
            now=checked_at,
            fresh_after_hours=fresh_after_hours,
        )
        leisu_fields = _leisu_operational_fields(
            provider_counts,
            leisu_state,
            now=checked_at,
            fresh_after_hours=fresh_after_hours,
        )
        the_odds_api_fields = _configured_api_operational_fields(
            provider_counts,
            "the_odds_api",
            now=checked_at,
            fresh_after_hours=fresh_after_hours,
        )
        analysis_odds_fields = _analysis_odds_operational_fields(
            provider_counts,
            now=checked_at,
            fresh_after_hours=fresh_after_hours,
        )
        sources = {
            "leisu": {
                "status": leisu_state.get("latest_status") or _snapshot_provider_status(provider_counts, "leisu"),
                "role": "primary gated multi-company odds source when access/proxy is healthy",
                "snapshot_count": (provider_counts.get("leisu") or {}).get("snapshot_count", 0),
                "sync": leisu_state,
                **leisu_fields,
            },
            "oddsportal_scraper": {
                "status": oddsportal_state.get("latest_status")
                or _snapshot_provider_status(provider_counts, "oddsportal_scraper"),
                "role": "experimental fallback odds crawler for 1X2/AH/O-U snapshots",
                "snapshot_count": (provider_counts.get("oddsportal_scraper") or {}).get("snapshot_count", 0),
                "sync": oddsportal_state,
                **oddsportal_readiness,
                **oddsportal_fields,
            },
            "betexplorer_scraper": {
                "status": betexplorer_state.get("latest_status")
                or _snapshot_provider_status(provider_counts, "betexplorer_scraper"),
                "role": "structured fallback odds crawler for sparse 1X2/AH/O-U snapshots",
                "snapshot_count": (provider_counts.get("betexplorer_scraper") or {}).get("snapshot_count", 0),
                "sync": betexplorer_state,
                **betexplorer_readiness,
                **betexplorer_fields,
            },
            "the_odds_api": {
                "status": _snapshot_provider_status(provider_counts, "the_odds_api"),
                "role": "configured API odds source when THE_ODDS_API_KEY is present",
                "snapshot_count": (provider_counts.get("the_odds_api") or {}).get("snapshot_count", 0),
                **the_odds_api_fields,
            },
            "analysis_odds": {
                "status": _snapshot_provider_status(provider_counts, "analysis_odds"),
                "role": "fallback snapshots persisted from already-run match analysis",
                "snapshot_count": (provider_counts.get("analysis_odds") or {}).get("snapshot_count", 0),
                **analysis_odds_fields,
            },
        }
        return {
            "status": "ok",
            "snapshot_summary": data.get("snapshot_summary") or {},
            "provider_counts": provider_counts,
            "sync_state": sync_state,
            "sources": sources,
            "closure": _odds_source_closure(sources, checked_at=checked_at, fresh_after_hours=fresh_after_hours),
            "policy": {
                "read_path": "分析和图表读取统一 market_snapshots；数据源只负责产生标准快照。",
                "fallback_rule": "Leisu 赔率不可用时，可用 betexplorer_scraper / oddsportal_scraper 补充赔率快照；推荐发布仍由质量门控决定。",
                "resume_rule": "按 odds_source_sync_state 的 source/scope_key/external_id/status 续跑失败或未完成项。",
                "freshness_rule": f"独立赔率源最近快照超过 {fresh_after_hours:g} 小时会被标记为 stale，不再视为当前生产主源。",
            },
        }

    def _oddsportal_discovery_readiness(self) -> dict[str, Any]:
        configured_urls = _configured_oddsportal_discovery_urls()
        target_info = self._oddsportal_discovery_targets(limit=100)
        targets = target_info["targets"]
        suggested_urls = oddsportal_source.oddsportal_discovery_urls_for_targets(targets, include_generic=False)
        effective_urls = _oddsportal_discovery_urls(None, targets=targets)
        scraper_enabled = _env_bool("FOOTBALL_DATA_ODDSPORTAL_SCRAPER_ENABLED", False)
        auto_sync_enabled = _env_bool("FOOTBALL_DATA_AUTO_SYNC_ODDSPORTAL_ODDS", False)
        configured_count = len(configured_urls)
        suggested_count = len(suggested_urls)
        effective_count = len(effective_urls)
        discovery_target_count = len(targets)
        discovery_ready = scraper_enabled and effective_count > 0 and discovery_target_count > 0
        return {
            "scraper_enabled": scraper_enabled,
            "auto_sync_enabled": auto_sync_enabled,
            "discovery_ready": discovery_ready,
            "configured_discovery_url_count": configured_count,
            "suggested_discovery_url_count": suggested_count,
            "effective_discovery_url_count": effective_count,
            "discovery_urls": configured_urls[:8],
            "suggested_discovery_urls": suggested_urls[:8],
            "effective_discovery_urls": effective_urls[:8],
            "open_target_count": target_info["open_target_count"],
            "analysis_target_count": target_info["analysis_target_count"],
            "discovery_target_count": discovery_target_count,
            "discovery_target_source": target_info["source"],
        }

    def _betexplorer_discovery_readiness(self) -> dict[str, Any]:
        configured_urls = _configured_betexplorer_discovery_urls()
        target_info = self._oddsportal_discovery_targets(limit=100)
        targets = target_info["targets"]
        effective_urls = _betexplorer_discovery_urls(None, targets=targets)
        configured_count = len(configured_urls)
        effective_count = len(effective_urls)
        discovery_target_count = len(targets)
        discovery_ready = effective_count > 0 and discovery_target_count > 0
        return {
            "scraper_enabled": True,
            "auto_sync_enabled": True,
            "discovery_ready": discovery_ready,
            "configured_discovery_url_count": configured_count,
            "suggested_discovery_url_count": effective_count,
            "effective_discovery_url_count": effective_count,
            "discovery_urls": configured_urls[:8],
            "suggested_discovery_urls": effective_urls[:8],
            "effective_discovery_urls": effective_urls[:8],
            "open_target_count": target_info["open_target_count"],
            "analysis_target_count": target_info["analysis_target_count"],
            "discovery_target_count": discovery_target_count,
            "discovery_target_source": target_info["source"],
        }

    def _oddsportal_discovery_targets(self, *, limit: int) -> dict[str, Any]:
        bounded_limit = max(1, min(int(limit or 50), 500))
        try:
            open_targets = self._repository.open_prediction_odds_targets(limit=bounded_limit)
        except Exception:
            open_targets = []
        if open_targets:
            return {
                "targets": open_targets,
                "source": "open_prediction",
                "open_target_count": len(open_targets),
                "analysis_target_count": 0,
            }

        analysis_targets: list[dict[str, Any]] = []
        recent_analysis_targets = getattr(self._repository, "recent_analysis_odds_targets", None)
        if callable(recent_analysis_targets):
            try:
                raw_analysis_targets = recent_analysis_targets(limit=bounded_limit)
                if isinstance(raw_analysis_targets, list):
                    analysis_targets = [dict(item) for item in raw_analysis_targets if isinstance(item, dict)]
            except Exception:
                analysis_targets = []
        return {
            "targets": analysis_targets,
            "source": "analysis_odds" if analysis_targets else "none",
            "open_target_count": 0,
            "analysis_target_count": len(analysis_targets),
        }

    async def start_oddsportal_sync(
        self,
        *,
        event_urls: list[str] | None = None,
        markets: list[str] | None = None,
        limit: int = 10,
        force: bool = False,
        resume_failed: bool = False,
        resume_statuses: list[str] | None = None,
        auto_discover: bool = False,
        discovery_urls: list[str] | None = None,
        target_limit: int = 50,
        start_background: bool = True,
    ) -> dict[str, Any]:
        payload = await self._oddsportal_sync_payload(
            event_urls=event_urls,
            markets=markets,
            limit=limit,
            force=force,
            resume_failed=resume_failed,
            resume_statuses=resume_statuses,
            auto_discover=auto_discover,
            discovery_urls=discovery_urls,
            target_limit=target_limit,
        )
        if not payload["event_urls"]:
            return {
                "tool": "start_oddsportal_odds_sync",
                "status": "empty",
                "provider": "oddsportal_scraper",
                "job_id": payload["job_id"],
                "payload": payload,
                "message": _oddsportal_empty_sync_message(payload),
                "policy": {
                    "resume_rule": "Pass event_urls explicitly, set resume_failed=true, or set auto_discover=true with discovery_urls.",
                },
            }
        if not payload["markets"]:
            return {
                "tool": "start_oddsportal_odds_sync",
                "status": "empty",
                "provider": "oddsportal_scraper",
                "job_id": payload["job_id"],
                "payload": payload,
                "message": "No supported OddsPortal markets were selected.",
                "supported_markets": sorted(_SUPPORTED_ODDS_SYNC_MARKETS),
            }
        if not start_background:
            return await self.run_oddsportal_sync_inline(payload)
        self._repository.mark_oddsportal_sync_queued(
            event_urls=payload["event_urls"],
            markets=payload["markets"],
            job_id=payload["job_id"],
        )
        starter = self._odds_sync_job_starter or build_odds_source_sync_job_starter(
            thread_starter=self.start_oddsportal_background_runner
        )
        start_result = odds_source_sync_job_start_result(
            await starter.start_oddsportal_snapshot_sync_job(str(payload["job_id"]), payload)
        )
        return {
            "tool": "start_oddsportal_odds_sync",
            "status": "queued",
            "provider": "oddsportal_scraper",
            "job_id": payload["job_id"],
            "backend": start_result.backend,
            "queue_job_id": start_result.queue_job_id,
            "payload": payload,
            "policy": {
                "source_role": "fallback odds snapshot producer when Leisu odds are unstable",
                "resume_rule": "queued/running/failed rows are visible in odds_source_sync_state and can be retried by URL",
                "discovery_rule": "auto_discover reads open prediction targets, matches configured OddsPortal listing pages, then queues only matched event URLs",
            },
        }

    async def start_betexplorer_sync(
        self,
        *,
        event_urls: list[str] | None = None,
        markets: list[str] | None = None,
        limit: int = 10,
        force: bool = False,
        auto_discover: bool = False,
        discovery_urls: list[str] | None = None,
        target_limit: int = 50,
    ) -> dict[str, Any]:
        selected_urls = [str(url).strip() for url in (event_urls or []) if str(url or "").strip()]
        bounded_limit = max(1, min(int(limit or 10), 20))
        discovery_result: dict[str, Any] | None = None
        if not selected_urls and auto_discover:
            target_info = self._oddsportal_discovery_targets(limit=max(1, min(int(target_limit or 50), 500)))
            targets = target_info["targets"]
            selected_discovery_urls = _betexplorer_discovery_urls(discovery_urls, targets=targets)
            discovery_result = await self._repository.discover_betexplorer_event_urls(
                targets=targets,
                discovery_urls=selected_discovery_urls,
                limit=bounded_limit,
            )
            selected_urls = [
                str(url).strip()
                for url in (discovery_result.get("event_urls") or [])
                if str(url or "").strip()
            ]
        result = await self._repository.sync_betexplorer_odds_snapshots(
            event_urls=selected_urls,
            markets=[str(market).strip() for market in (markets or ["h2h"]) if str(market).strip()],
            limit=bounded_limit,
            force=bool(force),
            job_id=f"betexplorer-{uuid.uuid4().hex[:12]}",
            target_map={
                str(item.get("event_url") or ""): dict(item.get("target") or {})
                for item in ((discovery_result or {}).get("matches") or [])
                if str(item.get("event_url") or "").strip()
            } if discovery_result is not None else None,
        )
        if discovery_result is not None:
            result["discovery_result"] = discovery_result
            result["auto_discover"] = True
        return result

    def start_oddsportal_background_runner(self, job_id: str, payload: dict[str, Any]) -> None:
        with _RUNNING_ODDS_SOURCE_JOBS_LOCK:
            current = _RUNNING_ODDS_SOURCE_JOBS.get(job_id)
            if current and current.is_alive():
                return
            thread = threading.Thread(
                target=lambda: asyncio.run(self.run_oddsportal_sync_inline(payload)),
                daemon=True,
            )
            _RUNNING_ODDS_SOURCE_JOBS[job_id] = thread
            thread.start()

    async def run_oddsportal_sync_inline(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._repository.sync_oddsportal_odds_snapshots(
            event_urls=list(payload.get("event_urls") or []),
            markets=list(payload.get("markets") or []),
            limit=int(payload.get("limit") or 10),
            force=bool(payload.get("force")),
            job_id=str(payload.get("job_id") or ""),
        )

    async def start_leisu_session_refresh(
        self,
        *,
        match_id: str = "",
        url: str = "",
        profile_dir: str = "",
        headless: bool = False,
        start_background: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "job_id": f"leisu-session-{uuid.uuid4().hex[:12]}",
            "match_id": str(match_id or "").strip(),
            "url": str(url or "").strip(),
            "profile_dir": str(profile_dir or "").strip(),
            "headless": bool(headless),
        }
        if not start_background:
            return await self.run_leisu_session_refresh_inline(payload)
        starter = self._leisu_session_job_starter or build_leisu_session_refresh_job_starter(
            thread_starter=self.start_leisu_session_background_runner
        )
        start_result = leisu_session_refresh_job_start_result(
            await starter.start_leisu_session_refresh_job(str(payload["job_id"]), payload)
        )
        return {
            "tool": "start_leisu_session_refresh",
            "status": "queued",
            "provider": "leisu",
            "job_id": payload["job_id"],
            "backend": start_result.backend,
            "queue_job_id": start_result.queue_job_id,
            "payload": payload,
            "policy": {
                "mode": "browser_session_bootstrap",
                "note": "后台任务会尝试恢复或刷新 Leisu 浏览器会话；如遇滑块仍需人工验证。",
            },
        }

    def start_leisu_session_background_runner(self, job_id: str, payload: dict[str, Any]) -> None:
        with _RUNNING_LEISU_SESSION_JOBS_LOCK:
            current = _RUNNING_LEISU_SESSION_JOBS.get(job_id)
            if current and current.is_alive():
                return
            thread = threading.Thread(
                target=lambda: asyncio.run(self.run_leisu_session_refresh_inline(payload)),
                daemon=True,
            )
            _RUNNING_LEISU_SESSION_JOBS[job_id] = thread
            thread.start()

    async def run_leisu_session_refresh_inline(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = await crawler_runtime_support.bootstrap_leisu_session(
            match_id=str(payload.get("match_id") or ""),
            url=str(payload.get("url") or ""),
            profile_dir=str(payload.get("profile_dir") or ""),
            headless=bool(payload.get("headless")),
        )
        return {
            **result,
            "tool": "refresh_leisu_session",
            "job_id": str(payload.get("job_id") or ""),
            "execution_backend": "inline",
        }

    async def _oddsportal_sync_payload(
        self,
        *,
        event_urls: list[str] | None,
        markets: list[str] | None,
        limit: int,
        force: bool,
        resume_failed: bool,
        resume_statuses: list[str] | None,
        auto_discover: bool,
        discovery_urls: list[str] | None,
        target_limit: int,
    ) -> dict[str, Any]:
        selected_urls = [str(url).strip() for url in (event_urls or []) if str(url or "").strip()]
        selected_markets = [
            str(market).strip()
            for market in (markets or ["asian_handicap"])
            if str(market).strip() in _SUPPORTED_ODDS_SYNC_MARKETS
        ]
        bounded_limit = max(1, min(int(limit or 10), 20))
        selected_resume_statuses = [
            str(status).strip()
            for status in (resume_statuses or ["failed", "empty"])
            if str(status).strip()
        ]
        if not selected_urls and resume_failed:
            selected_urls = self._repository.retryable_oddsportal_event_urls(
                statuses=selected_resume_statuses,
                limit=bounded_limit,
            )
        bounded_target_limit = max(1, min(int(target_limit or 50), 500))
        selected_discovery_urls = _oddsportal_discovery_urls(discovery_urls)
        discovery_result: dict[str, Any] | None = None
        discovery_target_count = 0
        discovery_target_source = "none"
        open_target_count = 0
        analysis_target_count = 0
        if not selected_urls and auto_discover:
            target_info = self._oddsportal_discovery_targets(limit=bounded_target_limit)
            targets = target_info["targets"]
            discovery_target_count = len(targets)
            discovery_target_source = str(target_info["source"])
            open_target_count = int(target_info["open_target_count"])
            analysis_target_count = int(target_info["analysis_target_count"])
            selected_discovery_urls = _oddsportal_discovery_urls(discovery_urls, targets=targets)
            discovery_result = await self._repository.discover_oddsportal_event_urls(
                targets=targets,
                discovery_urls=selected_discovery_urls,
                limit=bounded_limit,
            )
            selected_urls = [
                str(url).strip()
                for url in (discovery_result.get("event_urls") or [])
                if str(url or "").strip()
            ]
        return {
            "job_id": f"oddsportal-{uuid.uuid4().hex[:12]}",
            "event_urls": selected_urls[:bounded_limit],
            "markets": selected_markets,
            "limit": bounded_limit,
            "force": bool(force),
            "resume_failed": bool(resume_failed),
            "resume_statuses": selected_resume_statuses,
            "auto_discover": bool(auto_discover),
            "discovery_urls": selected_discovery_urls,
            "target_limit": bounded_target_limit,
            "discovery_target_count": discovery_target_count,
            "discovery_target_source": discovery_target_source,
            "open_target_count": open_target_count,
            "analysis_target_count": analysis_target_count,
            "discovery_result": discovery_result,
        }


def _snapshot_provider_status(provider_counts: dict[str, Any], provider: str) -> str:
    item = provider_counts.get(provider) or {}
    return "snapshot_available" if int(item.get("snapshot_count") or 0) > 0 else "no_snapshots"


def _snapshot_count(provider_counts: dict[str, Any], provider: str) -> int:
    return int((provider_counts.get(provider) or {}).get("snapshot_count") or 0)


def _provider_latest_fetched_at(provider_counts: dict[str, Any], provider: str) -> str | None:
    raw_value = (provider_counts.get(provider) or {}).get("latest_fetched_at_utc")
    value = str(raw_value or "").strip()
    return value or None


def _parse_utc_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _odds_source_fresh_hours() -> float:
    raw = os.getenv("FOOTBALL_DATA_ODDS_SOURCE_FRESH_HOURS", "").strip()
    if not raw:
        return _PRODUCTION_ODDS_SOURCE_FRESH_HOURS
    try:
        return max(0.25, float(raw))
    except ValueError:
        return _PRODUCTION_ODDS_SOURCE_FRESH_HOURS


def _freshness_fields(
    provider_counts: dict[str, Any],
    provider: str,
    *,
    now: datetime,
    fresh_after_hours: float,
) -> dict[str, Any]:
    snapshot_count = _snapshot_count(provider_counts, provider)
    latest_fetched_at = _provider_latest_fetched_at(provider_counts, provider)
    parsed = _parse_utc_datetime(latest_fetched_at)
    if snapshot_count <= 0:
        freshness_status = "no_snapshots"
        age_seconds = None
        age_hours = None
    elif not parsed:
        freshness_status = "unknown"
        age_seconds = None
        age_hours = None
    else:
        age_seconds = max(0.0, (now.astimezone(timezone.utc) - parsed).total_seconds())
        age_hours = round(age_seconds / 3600, 3)
        freshness_status = "fresh" if age_hours <= fresh_after_hours else "stale"
    return {
        "latest_fetched_at_utc": latest_fetched_at,
        "fresh_after_hours": fresh_after_hours,
        "freshness_status": freshness_status,
        "age_hours": age_hours,
        "age_seconds": round(age_seconds, 3) if isinstance(age_seconds, float) else None,
    }


def _freshness_age_text(fields: dict[str, Any]) -> str:
    age_hours = fields.get("age_hours")
    if not isinstance(age_hours, int | float):
        return "未知"
    if age_hours >= 48:
        return f"{age_hours / 24:.1f} 天"
    if age_hours >= 1:
        return f"{age_hours:.1f} 小时"
    return f"{age_hours * 60:.0f} 分钟"


def _source_status_count(source_state: dict[str, Any], status: str) -> int:
    return int(((source_state.get("by_status") or {}).get(status)) or 0)


def _latest_source_error(sync_state: dict[str, Any], source: str) -> str | None:
    for row in sync_state.get("recent") or []:
        if str(row.get("source") or "") == source and str(row.get("error") or "").strip():
            return str(row.get("error") or "").strip()
    return None


def _oddsportal_operational_fields(
    provider_counts: dict[str, Any],
    oddsportal_state: dict[str, Any],
    sync_state: dict[str, Any],
    *,
    readiness: dict[str, Any] | None = None,
    now: datetime,
    fresh_after_hours: float,
) -> dict[str, Any]:
    readiness = readiness or {}
    failed_count = _source_status_count(oddsportal_state, "failed")
    empty_count = _source_status_count(oddsportal_state, "empty")
    queued_count = _source_status_count(oddsportal_state, "queued")
    running_count = _source_status_count(oddsportal_state, "running")
    retryable_count = failed_count + empty_count
    snapshot_count = _snapshot_count(provider_counts, "oddsportal_scraper")
    last_error = _latest_source_error(sync_state, "oddsportal_scraper")
    freshness = _freshness_fields(
        provider_counts,
        "oddsportal_scraper",
        now=now,
        fresh_after_hours=fresh_after_hours,
    )
    is_fresh = freshness["freshness_status"] == "fresh"

    if queued_count or running_count:
        operational_status = "running"
        next_action = "等待后台队列完成；worker 会将状态转为 succeeded/failed。"
    elif retryable_count:
        operational_status = "retryable"
        next_action = "调用 /api/sources/odds/oddsportal/sync resume_failed=true 续跑失败/空结果 URL。"
    elif snapshot_count > 0 and is_fresh:
        operational_status = "available"
        next_action = "已有 fallback 快照；继续按需补充新比赛 URL。"
    elif snapshot_count > 0:
        operational_status = "stale"
        next_action = f"OddsPortal 兜底快照已过期（最近 {_freshness_age_text(freshness)} 前）；需要补采新比赛。"
    elif bool(readiness.get("discovery_ready")):
        operational_status = "ready"
        if str(readiness.get("discovery_target_source") or "") == "analysis_odds":
            if bool(readiness.get("auto_sync_enabled")):
                next_action = "自动发现已就绪；daemon 会按最近分析快照种子匹配 OddsPortal listing 并入队。"
            else:
                next_action = "自动发现已就绪；可调用 auto_discover=true，用最近分析快照种子匹配 OddsPortal listing。"
        elif bool(readiness.get("auto_sync_enabled")):
            next_action = "自动发现已就绪；daemon 会按 open 台账匹配 OddsPortal listing 并入队。"
        else:
            next_action = "自动发现已就绪；可调用 auto_discover=true，或打开 FOOTBALL_DATA_AUTO_SYNC_ODDSPORTAL_ODDS。"
    else:
        operational_status = "needs_input"
        if not bool(readiness.get("scraper_enabled")):
            next_action = "先启用 FOOTBALL_DATA_ODDSPORTAL_SCRAPER_ENABLED，再配置 listing URL 或手动提供 event_urls。"
        elif int(readiness.get("effective_discovery_url_count") or 0) <= 0:
            next_action = "配置 FOOTBALL_DATA_ODDSPORTAL_DISCOVERY_URLS，或等待内置联赛覆盖命中 open 目标。"
        elif int(readiness.get("discovery_target_count") or 0) <= 0:
            next_action = "等待 open 预测台账或最近分析快照产生补采目标，或手动提供 OddsPortal event_urls。"
        elif str(readiness.get("discovery_target_source") or "") == "analysis_odds":
            next_action = "open 台账为空，已使用最近分析快照作为补采种子；可调用 auto_discover=true 启动独立源匹配。"
        else:
            next_action = "提供 OddsPortal event_urls，或调用 auto_discover=true 从配置的 listing URL 匹配后入队。"

    return {
        "operational_status": operational_status,
        "retryable_url_count": retryable_count,
        "queued_count": queued_count,
        "running_count": running_count,
        "failed_count": failed_count,
        "empty_count": empty_count,
        "usable_for_analysis": bool(snapshot_count > 0 and is_fresh),
        **freshness,
        "last_error": last_error,
        "next_action": next_action,
    }


def _betexplorer_operational_fields(
    provider_counts: dict[str, Any],
    betexplorer_state: dict[str, Any],
    sync_state: dict[str, Any],
    *,
    now: datetime,
    fresh_after_hours: float,
) -> dict[str, Any]:
    failed_count = _source_status_count(betexplorer_state, "failed")
    empty_count = _source_status_count(betexplorer_state, "empty")
    queued_count = _source_status_count(betexplorer_state, "queued")
    running_count = _source_status_count(betexplorer_state, "running")
    retryable_count = failed_count + empty_count
    snapshot_count = _snapshot_count(provider_counts, "betexplorer_scraper")
    last_error = _latest_source_error(sync_state, "betexplorer_scraper")
    freshness = _freshness_fields(
        provider_counts,
        "betexplorer_scraper",
        now=now,
        fresh_after_hours=fresh_after_hours,
    )
    is_fresh = freshness["freshness_status"] == "fresh"

    if queued_count or running_count:
        operational_status = "running"
        next_action = "等待 BetExplorer 补采完成；当前按低频显式 event URL 运行。"
    elif retryable_count:
        operational_status = "retryable"
        next_action = "重试失败/空结果的 BetExplorer event URL，优先保留显式小批量补采。"
    elif snapshot_count > 0 and is_fresh:
        operational_status = "available"
        next_action = "BetExplorer 稀疏快照可用；继续按需补充目标比赛。"
    elif snapshot_count > 0:
        operational_status = "stale"
        next_action = f"BetExplorer 稀疏快照已过期（最近 {_freshness_age_text(freshness)} 前）；需要补采新比赛。"
    else:
        operational_status = "needs_input"
        next_action = "提供 BetExplorer event_urls 后可开始显式补采；当前未启用自动发现/主链路。"

    return {
        "operational_status": operational_status,
        "retryable_url_count": retryable_count,
        "queued_count": queued_count,
        "running_count": running_count,
        "failed_count": failed_count,
        "empty_count": empty_count,
        "usable_for_analysis": bool(snapshot_count > 0 and is_fresh),
        **freshness,
        "last_error": last_error,
        "next_action": next_action,
    }


def _oddsportal_discovery_urls(
    discovery_urls: list[str] | None,
    *,
    targets: list[dict[str, Any]] | None = None,
) -> list[str]:
    configured = _configured_oddsportal_discovery_urls()
    selected = [str(url).strip() for url in (discovery_urls or configured) if str(url or "").strip()]
    if not selected and targets:
        selected = oddsportal_source.oddsportal_discovery_urls_for_targets(targets, include_generic=False)
    if not selected:
        selected = ["https://www.oddsportal.com/football/"]
    deduped: list[str] = []
    seen: set[str] = set()
    for url in selected:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped[:20]


def _configured_oddsportal_discovery_urls() -> list[str]:
    return [
        value.strip()
        for value in os.getenv("FOOTBALL_DATA_ODDSPORTAL_DISCOVERY_URLS", "").split(",")
        if value.strip()
    ]


def _betexplorer_discovery_urls(
    discovery_urls: list[str] | None,
    *,
    targets: list[dict[str, Any]] | None = None,
) -> list[str]:
    configured = _configured_betexplorer_discovery_urls()
    selected = [str(url).strip() for url in (discovery_urls or configured) if str(url or "").strip()]
    if not selected and targets:
        selected = betexplorer_source.betexplorer_discovery_urls_for_targets(targets)
    if not selected:
        selected = ["https://www.betexplorer.com/football/"]
    deduped: list[str] = []
    seen: set[str] = set()
    for url in selected:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped[:20]


def _configured_betexplorer_discovery_urls() -> list[str]:
    return [
        value.strip()
        for value in os.getenv("FOOTBALL_DATA_BETEXPLORER_DISCOVERY_URLS", "").split(",")
        if value.strip()
    ]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "true" if default else "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _oddsportal_empty_sync_message(payload: dict[str, Any]) -> str:
    discovery_result = payload.get("discovery_result") if isinstance(payload.get("discovery_result"), dict) else None
    if discovery_result:
        status = str(discovery_result.get("status") or "unknown")
        target_count = int(payload.get("discovery_target_count") or 0)
        return f"Auto discovery returned no OddsPortal event URLs (status={status}, targets={target_count})."
    if payload.get("resume_failed"):
        return "No failed/empty OddsPortal event URLs were available to resume."
    return "No OddsPortal event URLs were provided."


def _configured_api_operational_fields(
    provider_counts: dict[str, Any],
    provider: str,
    *,
    now: datetime,
    fresh_after_hours: float,
) -> dict[str, Any]:
    snapshot_count = _snapshot_count(provider_counts, provider)
    freshness = _freshness_fields(provider_counts, provider, now=now, fresh_after_hours=fresh_after_hours)
    is_fresh = freshness["freshness_status"] == "fresh"
    if snapshot_count > 0 and is_fresh:
        operational_status = "available"
        next_action = "已存在新鲜 API 赔率快照；可作为独立补充源。"
    elif snapshot_count > 0:
        operational_status = "stale"
        next_action = f"API 赔率快照已过期（最近 {_freshness_age_text(freshness)} 前）；需要重新同步。"
    else:
        operational_status = "needs_config"
        next_action = "配置 THE_ODDS_API_KEY 后可作为额外赔率源；已有快照时只作为补充证据。"
    return {
        "operational_status": operational_status,
        "usable_for_analysis": bool(snapshot_count > 0 and is_fresh),
        **freshness,
        "next_action": next_action,
    }


def _analysis_odds_operational_fields(
    provider_counts: dict[str, Any],
    *,
    now: datetime,
    fresh_after_hours: float,
) -> dict[str, Any]:
    snapshot_count = _snapshot_count(provider_counts, "analysis_odds")
    freshness = _freshness_fields(provider_counts, "analysis_odds", now=now, fresh_after_hours=fresh_after_hours)
    is_fresh = freshness["freshness_status"] == "fresh"
    if snapshot_count > 0 and is_fresh:
        operational_status = "derived_fallback"
        next_action = "这是分析过程沉淀的快照，可临时兜底图表/复盘；生产赔率仍应优先来自独立数据源。"
    elif snapshot_count > 0:
        operational_status = "stale_derived"
        next_action = f"分析沉淀快照也已过期（最近 {_freshness_age_text(freshness)} 前）；当前需要重新分析或补采独立源。"
    else:
        operational_status = "derived_only"
        next_action = "这是分析过程沉淀的快照，只能兜底复盘；生产赔率仍应优先来自独立数据源。"
    return {
        "operational_status": operational_status,
        "usable_for_analysis": bool(snapshot_count > 0 and is_fresh),
        **freshness,
        "next_action": next_action,
    }


def _leisu_operational_fields(
    provider_counts: dict[str, Any],
    leisu_state: dict[str, Any],
    *,
    now: datetime,
    fresh_after_hours: float,
) -> dict[str, Any]:
    snapshot_count = _snapshot_count(provider_counts, "leisu")
    failed_count = _source_status_count(leisu_state, "failed")
    queued_count = _source_status_count(leisu_state, "queued")
    running_count = _source_status_count(leisu_state, "running")
    browser_session = _leisu_browser_session_status()
    browser_session_status = str(browser_session.get("status") or "")
    freshness = _freshness_fields(provider_counts, "leisu", now=now, fresh_after_hours=fresh_after_hours)
    is_fresh = freshness["freshness_status"] == "fresh"
    if snapshot_count > 0 and is_fresh:
        operational_status = "available"
        next_action = "雷速赔率快照可用；继续监控代理、Cookie 和访问稳定性。"
    elif snapshot_count > 0:
        operational_status = "stale"
        if browser_session_status == "ready":
            next_action = (
                f"雷速赔率快照已过期（最近 {_freshness_age_text(freshness)} 前）；"
                "但浏览器辅助会话已就绪，可立即重跑雷速同步。"
            )
        elif browser_session_status == "auth_required":
            next_action = (
                f"雷速赔率快照已过期（最近 {_freshness_age_text(freshness)} 前）；"
                "浏览器会话仍需人工验证后才能恢复抓取。"
            )
        else:
            next_action = f"雷速赔率快照已过期（最近 {_freshness_age_text(freshness)} 前）；应启用爬虫/API 兜底并检查雷速访问。"
    elif browser_session_status == "ready":
        operational_status = "session_ready"
        next_action = "雷速浏览器辅助会话已就绪；可调用 /api/sources/odds/leisu/session/refresh 或直接重跑下一次同步。"
    elif browser_session_status == "auth_required":
        operational_status = "needs_auth"
        next_action = "检测到雷速浏览器会话需要人工验证；先完成滑块，再调用 /api/sources/odds/leisu/session/refresh 或重试同步。"
    elif queued_count or running_count:
        operational_status = "running"
        next_action = "雷速赔率同步仍在执行；若长期停滞，检查代理和访问凭据。"
    else:
        operational_status = "needs_access"
        next_action = "雷速无可用赔率快照；配置 LEISU_ODDS_PROXY_URL/COOKIE，或继续由 betexplorer_scraper / oddsportal_scraper 补位。"
    return {
        "operational_status": operational_status,
        "failed_count": failed_count,
        "queued_count": queued_count,
        "running_count": running_count,
        "retryable_url_count": failed_count,
        "usable_for_analysis": bool(snapshot_count > 0 and is_fresh),
        "browser_session": browser_session,
        "browser_session_status": browser_session_status or "unknown",
        "runtime_support": crawler_runtime_support.leisu_crawlee_runtime_plan(),
        **freshness,
        "next_action": next_action,
    }


def _leisu_browser_session_status() -> dict[str, Any]:
    entry = _probe_leisu_browser_session_http() or browser_session_runtime.provider_status("leisu")
    if not entry:
        return {}
    return {
        "status": str(entry.get("status") or "unknown"),
        "mode": str(entry.get("mode") or ""),
        "browser": str(entry.get("browser") or ""),
        "message": str(entry.get("message") or ""),
        "updated_at_utc": str(entry.get("updated_at_utc") or ""),
        "last_ready_at_utc": str(entry.get("last_ready_at_utc") or ""),
        "last_fetch_at_utc": str(entry.get("last_fetch_at_utc") or ""),
        "last_verification_url": str(entry.get("last_verification_url") or ""),
        "last_error": str(entry.get("last_error") or ""),
        "connect_cdp": bool(entry.get("connect_cdp")),
        "headless": bool(entry.get("headless")),
        "profile_dir": str(entry.get("profile_dir") or ""),
    }


def _probe_leisu_browser_session_http() -> dict[str, Any]:
    status_url = os.getenv("LEISU_BROWSER_PROXY_STATUS_URL", "").strip()
    if not status_url:
        proxy_url = os.getenv("LEISU_ODDS_PROXY_URL", "").strip()
        if "/leisu/odds" in proxy_url:
            status_url = f"{proxy_url.split('/leisu/odds', 1)[0]}/leisu/session"
    if not status_url:
        return {}
    try:
        with urllib_request.urlopen(status_url, timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib_error.URLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _odds_source_closure(
    sources: dict[str, dict[str, Any]],
    *,
    checked_at: datetime,
    fresh_after_hours: float,
) -> dict[str, Any]:
    # 这里把“源是否有历史数据”翻译成产品可理解的当前可用性。
    ordered_names = ["leisu", "betexplorer_scraper", "oddsportal_scraper", "the_odds_api", "analysis_odds"]
    ordered_sources = []
    for name in ordered_names:
        item = sources.get(name) or {}
        ordered_sources.append(
            {
                "source": name,
                "operational_status": item.get("operational_status"),
                "freshness_status": item.get("freshness_status"),
                "snapshot_count": int(item.get("snapshot_count") or 0),
                "latest_fetched_at_utc": item.get("latest_fetched_at_utc"),
                "usable_for_analysis": bool(item.get("usable_for_analysis")),
            }
        )
    if bool((sources.get("leisu") or {}).get("usable_for_analysis")):
        active_source = "leisu"
        production_ready = True
        reason = "雷速主赔率源新鲜可用。"
    elif bool((sources.get("betexplorer_scraper") or {}).get("usable_for_analysis")):
        active_source = "betexplorer_scraper"
        production_ready = True
        reason = "雷速不可用或过期，当前优先使用 BetExplorer 稀疏快照兜底。"
    elif bool((sources.get("oddsportal_scraper") or {}).get("usable_for_analysis")):
        active_source = "oddsportal_scraper"
        production_ready = True
        reason = "雷速不可用或过期，当前使用独立爬虫赔率源兜底。"
    elif bool((sources.get("the_odds_api") or {}).get("usable_for_analysis")):
        active_source = "the_odds_api"
        production_ready = True
        reason = "雷速不可用或过期，当前使用配置的赔率 API 兜底。"
    elif bool((sources.get("analysis_odds") or {}).get("usable_for_analysis")):
        active_source = "analysis_odds"
        production_ready = False
        reason = "主赔率源已过期，当前只能使用分析过程沉淀的快照兜底。"
    else:
        active_source = None
        production_ready = False
        reason = "当前没有新鲜赔率快照，需要恢复雷速或启动独立爬虫/API 补采。"
    return {
        "active_source": active_source,
        "production_ready": production_ready,
        "reason": reason,
        "checked_at_utc": checked_at.astimezone(timezone.utc).isoformat(),
        "fresh_after_hours": fresh_after_hours,
        "ordered_sources": ordered_sources,
    }

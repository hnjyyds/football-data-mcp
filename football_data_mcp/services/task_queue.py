from __future__ import annotations

import inspect
import logging
import importlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol, cast

from football_data_mcp.config import TaskQueueSettings, load_task_queue_settings
from football_data_mcp.core.errors import ServiceExecutionError


logger = logging.getLogger("football_data_mcp.services.task_queue")

ArqCreatePool = Callable[[Any, str], Awaitable[Any]]


class ValidationJobStarter(Protocol):
    async def start_holdout_validation_job(self, job_id: str) -> ValidationJobStartResult | str:
        """Start a persisted validation job and return the execution backend name."""
        ...


class OddsSourceSyncJobStarter(Protocol):
    async def start_oddsportal_snapshot_sync_job(
        self,
        job_id: str,
        payload: dict[str, Any],
    ) -> OddsSourceSyncJobStartResult | str:
        """Start an OddsPortal snapshot sync job and return the execution backend name."""
        ...


class LeisuSessionRefreshJobStarter(Protocol):
    async def start_leisu_session_refresh_job(
        self,
        job_id: str,
        payload: dict[str, Any],
    ) -> LeisuSessionRefreshJobStartResult | str:
        """Start a Leisu session refresh/bootstrap job and return the execution backend name."""
        ...


@dataclass(slots=True)
class ValidationJobStartResult:
    backend: str
    queue_job_id: str | None = None


@dataclass(slots=True)
class OddsSourceSyncJobStartResult:
    backend: str
    queue_job_id: str | None = None


@dataclass(slots=True)
class LeisuSessionRefreshJobStartResult:
    backend: str
    queue_job_id: str | None = None


def validation_job_start_result(value: ValidationJobStartResult | str) -> ValidationJobStartResult:
    if isinstance(value, ValidationJobStartResult):
        return value
    return ValidationJobStartResult(backend=str(value), queue_job_id=None)


def odds_source_sync_job_start_result(
    value: OddsSourceSyncJobStartResult | str,
) -> OddsSourceSyncJobStartResult:
    if isinstance(value, OddsSourceSyncJobStartResult):
        return value
    return OddsSourceSyncJobStartResult(backend=str(value), queue_job_id=None)


def leisu_session_refresh_job_start_result(
    value: LeisuSessionRefreshJobStartResult | str,
) -> LeisuSessionRefreshJobStartResult:
    if isinstance(value, LeisuSessionRefreshJobStartResult):
        return value
    return LeisuSessionRefreshJobStartResult(backend=str(value), queue_job_id=None)


@dataclass(slots=True)
class ThreadValidationJobStarter:
    thread_starter: Callable[[str], None]

    async def start_holdout_validation_job(self, job_id: str) -> ValidationJobStartResult:
        self.thread_starter(job_id)
        return ValidationJobStartResult(backend="thread", queue_job_id=None)


@dataclass(slots=True)
class ThreadOddsSourceSyncJobStarter:
    thread_starter: Callable[[str, dict[str, Any]], None]

    async def start_oddsportal_snapshot_sync_job(
        self,
        job_id: str,
        payload: dict[str, Any],
    ) -> OddsSourceSyncJobStartResult:
        self.thread_starter(job_id, _payload_with_job_id(payload, job_id))
        return OddsSourceSyncJobStartResult(backend="thread", queue_job_id=None)


@dataclass(slots=True)
class ThreadLeisuSessionRefreshJobStarter:
    thread_starter: Callable[[str, dict[str, Any]], None]

    async def start_leisu_session_refresh_job(
        self,
        job_id: str,
        payload: dict[str, Any],
    ) -> LeisuSessionRefreshJobStartResult:
        self.thread_starter(job_id, _payload_with_job_id(payload, job_id))
        return LeisuSessionRefreshJobStartResult(backend="thread", queue_job_id=None)


@dataclass(slots=True)
class ArqValidationJobStarter:
    settings: TaskQueueSettings
    create_pool: ArqCreatePool | None = None

    async def start_holdout_validation_job(self, job_id: str) -> ValidationJobStartResult:
        redis = await self._create_pool()
        queue_job_id = f"holdout-validation:{job_id}"
        try:
            await redis.enqueue_job(
                "run_holdout_validation_job",
                job_id,
                _job_id=queue_job_id,
                _queue_name=self.settings.arq_queue_name,
            )
        finally:
            await _close_redis_pool(redis)
        return ValidationJobStartResult(backend="arq", queue_job_id=queue_job_id)

    async def _create_pool(self) -> Any:
        if self.create_pool:
            return await self.create_pool(redis_settings_from_task_queue(self.settings), self.settings.arq_queue_name)
        return await _create_arq_pool(redis_settings_from_task_queue(self.settings), self.settings.arq_queue_name)


@dataclass(slots=True)
class ArqOddsSourceSyncJobStarter:
    settings: TaskQueueSettings
    create_pool: ArqCreatePool | None = None

    async def start_oddsportal_snapshot_sync_job(
        self,
        job_id: str,
        payload: dict[str, Any],
    ) -> OddsSourceSyncJobStartResult:
        redis = await self._create_pool()
        queue_job_id = f"oddsportal-sync:{job_id}"
        try:
            await redis.enqueue_job(
                "run_oddsportal_snapshot_sync_job",
                _payload_with_job_id(payload, job_id),
                _job_id=queue_job_id,
                _queue_name=self.settings.arq_queue_name,
            )
        finally:
            await _close_redis_pool(redis)
        return OddsSourceSyncJobStartResult(backend="arq", queue_job_id=queue_job_id)

    async def _create_pool(self) -> Any:
        if self.create_pool:
            return await self.create_pool(redis_settings_from_task_queue(self.settings), self.settings.arq_queue_name)
        return await _create_arq_pool(redis_settings_from_task_queue(self.settings), self.settings.arq_queue_name)


@dataclass(slots=True)
class ArqLeisuSessionRefreshJobStarter:
    settings: TaskQueueSettings
    create_pool: ArqCreatePool | None = None

    async def start_leisu_session_refresh_job(
        self,
        job_id: str,
        payload: dict[str, Any],
    ) -> LeisuSessionRefreshJobStartResult:
        redis = await self._create_pool()
        queue_job_id = f"leisu-session-refresh:{job_id}"
        try:
            await redis.enqueue_job(
                "run_leisu_session_refresh_job",
                _payload_with_job_id(payload, job_id),
                _job_id=queue_job_id,
                _queue_name=self.settings.arq_queue_name,
            )
        finally:
            await _close_redis_pool(redis)
        return LeisuSessionRefreshJobStartResult(backend="arq", queue_job_id=queue_job_id)

    async def _create_pool(self) -> Any:
        if self.create_pool:
            return await self.create_pool(redis_settings_from_task_queue(self.settings), self.settings.arq_queue_name)
        return await _create_arq_pool(redis_settings_from_task_queue(self.settings), self.settings.arq_queue_name)


@dataclass(slots=True)
class FallbackValidationJobStarter:
    primary: ValidationJobStarter
    fallback: ValidationJobStarter

    async def start_holdout_validation_job(self, job_id: str) -> ValidationJobStartResult:
        try:
            return validation_job_start_result(await self.primary.start_holdout_validation_job(job_id))
        except Exception as exc:
            logger.warning("ARQ enqueue failed for validation job %s; falling back to thread: %s", job_id, exc)
            return validation_job_start_result(await self.fallback.start_holdout_validation_job(job_id))


@dataclass(slots=True)
class FallbackOddsSourceSyncJobStarter:
    primary: OddsSourceSyncJobStarter
    fallback: OddsSourceSyncJobStarter

    async def start_oddsportal_snapshot_sync_job(
        self,
        job_id: str,
        payload: dict[str, Any],
    ) -> OddsSourceSyncJobStartResult:
        try:
            return odds_source_sync_job_start_result(
                await self.primary.start_oddsportal_snapshot_sync_job(job_id, payload)
            )
        except Exception as exc:
            logger.warning("ARQ enqueue failed for OddsPortal sync job %s; falling back to thread: %s", job_id, exc)
            return odds_source_sync_job_start_result(
                await self.fallback.start_oddsportal_snapshot_sync_job(job_id, _payload_with_job_id(payload, job_id))
            )


@dataclass(slots=True)
class FallbackLeisuSessionRefreshJobStarter:
    primary: LeisuSessionRefreshJobStarter
    fallback: LeisuSessionRefreshJobStarter

    async def start_leisu_session_refresh_job(
        self,
        job_id: str,
        payload: dict[str, Any],
    ) -> LeisuSessionRefreshJobStartResult:
        try:
            return leisu_session_refresh_job_start_result(
                await self.primary.start_leisu_session_refresh_job(job_id, payload)
            )
        except Exception as exc:
            logger.warning("ARQ enqueue failed for Leisu session refresh job %s; falling back to thread: %s", job_id, exc)
            return leisu_session_refresh_job_start_result(
                await self.fallback.start_leisu_session_refresh_job(job_id, _payload_with_job_id(payload, job_id))
            )


def build_validation_job_starter(*, thread_starter: Callable[[str], None]) -> ValidationJobStarter:
    settings = load_task_queue_settings()
    thread = ThreadValidationJobStarter(thread_starter=thread_starter)
    if settings.backend == "thread":
        return thread
    arq_starter = ArqValidationJobStarter(settings=settings)
    if settings.fallback_to_thread:
        return FallbackValidationJobStarter(primary=arq_starter, fallback=thread)
    return arq_starter


def build_odds_source_sync_job_starter(
    *,
    thread_starter: Callable[[str, dict[str, Any]], None],
) -> OddsSourceSyncJobStarter:
    settings = load_task_queue_settings()
    thread = ThreadOddsSourceSyncJobStarter(thread_starter=thread_starter)
    if settings.backend == "thread":
        return thread
    arq_starter = ArqOddsSourceSyncJobStarter(settings=settings)
    if settings.fallback_to_thread:
        return FallbackOddsSourceSyncJobStarter(primary=arq_starter, fallback=thread)
    return arq_starter


def build_leisu_session_refresh_job_starter(
    *,
    thread_starter: Callable[[str, dict[str, Any]], None],
) -> LeisuSessionRefreshJobStarter:
    settings = load_task_queue_settings()
    thread = ThreadLeisuSessionRefreshJobStarter(thread_starter=thread_starter)
    if settings.backend == "thread":
        return thread
    arq_starter = ArqLeisuSessionRefreshJobStarter(settings=settings)
    if settings.fallback_to_thread:
        return FallbackLeisuSessionRefreshJobStarter(primary=arq_starter, fallback=thread)
    return arq_starter


def task_queue_health_snapshot(
    settings: TaskQueueSettings | None = None,
    *,
    redis_client_factory: Callable[[TaskQueueSettings], Any] | None = None,
) -> dict[str, Any]:
    """Return queue infrastructure health without requiring a running worker in-process.

    主要阶段：
    - thread 后端直接报告本进程后台线程模式；
    - ARQ 后端检查 Redis ping、队列积压和 worker health-check key；
    - 任意连接失败都转成结构化 degraded/error 状态，避免健康接口抛 500。
    """
    queue_settings = settings or load_task_queue_settings()
    if queue_settings.backend == "thread":
        return {
            "backend": "thread",
            "status": "ok",
            "redis_reachable": None,
            "queue_name": None,
            "queued_jobs": None,
            "worker_healthy": None,
            "detail": "使用本进程线程执行后台任务。",
        }

    try:
        client = redis_client_factory(queue_settings) if redis_client_factory else _create_sync_redis_client(queue_settings)
        try:
            ping_ok = bool(client.ping())
            queued_jobs = int(client.zcard(queue_settings.arq_queue_name))
            health_key = f"{queue_settings.arq_queue_name}:health-check"
            worker_health = _decode_redis_value(client.get(health_key))
            worker_health_ttl_seconds = _redis_ttl_seconds(client, health_key)
            worker_healthy = bool(worker_health) and (
                worker_health_ttl_seconds is None or worker_health_ttl_seconds > 0
            )
            status = "ok" if ping_ok and worker_healthy else "degraded"
            if worker_healthy:
                detail = "ARQ worker 已上报健康检查。"
            elif worker_health and worker_health_ttl_seconds == -1:
                detail = "Redis 中存在 ARQ worker 健康检查，但 key 没有过期时间；请重启 worker 以恢复可验证心跳。"
            else:
                detail = "Redis 可达，但暂未看到 ARQ worker 健康检查；请确认 worker 已启动。"
            return {
                "backend": "arq",
                "status": status,
                "redis_reachable": ping_ok,
                "redis_host": queue_settings.arq_redis_host,
                "redis_port": queue_settings.arq_redis_port,
                "redis_database": queue_settings.arq_redis_database,
                "queue_name": queue_settings.arq_queue_name,
                "queued_jobs": queued_jobs,
                "worker_healthy": worker_healthy,
                "worker_health": worker_health,
                "worker_health_ttl_seconds": worker_health_ttl_seconds,
                "max_jobs": queue_settings.arq_max_jobs,
                "job_timeout_seconds": queue_settings.arq_job_timeout_seconds,
                "validation_job_stale_after_seconds": queue_settings.validation_job_stale_after_seconds,
                "detail": detail,
            }
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()
    except Exception as exc:
        return {
            "backend": "arq",
            "status": "error",
            "redis_reachable": False,
            "redis_host": queue_settings.arq_redis_host,
            "redis_port": queue_settings.arq_redis_port,
            "redis_database": queue_settings.arq_redis_database,
            "queue_name": queue_settings.arq_queue_name,
            "queued_jobs": None,
            "worker_healthy": False,
            "worker_health_ttl_seconds": None,
            "validation_job_stale_after_seconds": queue_settings.validation_job_stale_after_seconds,
            "detail": f"{type(exc).__name__}: {exc}",
        }


def redis_settings_from_task_queue(settings: TaskQueueSettings) -> Any:
    try:
        RedisSettings = getattr(importlib.import_module("arq.connections"), "RedisSettings")
    except ImportError as exc:
        raise ServiceExecutionError(
            code="arq_not_installed",
            message="ARQ is configured as the task queue backend but the arq package is not installed.",
        ) from exc
    return RedisSettings(
        host=settings.arq_redis_host,
        port=settings.arq_redis_port,
        database=settings.arq_redis_database,
        username=settings.arq_redis_username,
        password=settings.arq_redis_password,
    )


def _create_sync_redis_client(settings: TaskQueueSettings) -> Any:
    try:
        Redis = getattr(importlib.import_module("redis"), "Redis")
    except ImportError as exc:
        raise ServiceExecutionError(
            code="redis_not_installed",
            message="ARQ health checks require the redis package.",
        ) from exc
    return Redis(
        host=settings.arq_redis_host,
        port=settings.arq_redis_port,
        db=settings.arq_redis_database,
        username=settings.arq_redis_username,
        password=settings.arq_redis_password,
        socket_connect_timeout=1,
        socket_timeout=1,
    )


def _decode_redis_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _redis_ttl_seconds(client: Any, key: str) -> int | None:
    ttl = getattr(client, "ttl", None)
    if not callable(ttl):
        return None
    ttl_func = cast(Callable[[str], Any], ttl)
    try:
        return int(ttl_func(key))
    except (TypeError, ValueError):
        return None


async def _create_arq_pool(redis_settings: Any, queue_name: str) -> Any:
    try:
        create_pool = getattr(importlib.import_module("arq"), "create_pool")
    except ImportError as exc:
        raise ServiceExecutionError(
            code="arq_not_installed",
            message="ARQ is configured as the task queue backend but the arq package is not installed.",
        ) from exc
    return await create_pool(redis_settings, default_queue_name=queue_name)


def _payload_with_job_id(payload: dict[str, Any], job_id: str) -> dict[str, Any]:
    return {**payload, "job_id": job_id}


async def _close_redis_pool(redis: Any) -> None:
    for method_name in ("aclose", "close"):
        method = getattr(redis, method_name, None)
        if not callable(method):
            continue
        result = method()
        if inspect.isawaitable(result):
            await result
        return

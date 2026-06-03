from __future__ import annotations

import logging
from typing import Any

from football_data_mcp.config import load_task_queue_settings
from football_data_mcp import sources
from football_data_mcp.services.task_queue import redis_settings_from_task_queue
from football_data_mcp.services.validation_service import ValidationJobService


logger = logging.getLogger("football_data_mcp.workers.arq")
_settings = load_task_queue_settings()


async def run_holdout_validation_job(ctx: dict[str, Any], job_id: str) -> dict[str, Any]:
    """ARQ entrypoint: run one persisted holdout job and let the service persist progress."""
    logger.info("arq run_holdout_validation_job: job_id=%s", job_id)
    queue_job_id = str(ctx.get("job_id") or f"holdout-validation:{job_id}")
    worker_instance_id = str(ctx.get("worker_id") or ctx.get("worker_name") or "") or None
    return await ValidationJobService().run_holdout_job_inline(
        job_id,
        execution_backend="arq",
        queue_job_id=queue_job_id,
        worker_instance_id=worker_instance_id,
    )


async def run_oddsportal_snapshot_sync_job(ctx: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """ARQ entrypoint: fetch fallback odds snapshots and persist source sync state."""
    job_id = str(payload.get("job_id") or ctx.get("job_id") or "")
    queue_job_id = str(ctx.get("job_id") or f"oddsportal-sync:{job_id}")
    logger.info("arq run_oddsportal_snapshot_sync_job: job_id=%s", job_id or "<missing>")
    allowed = {
        "event_urls",
        "markets",
        "limit",
        "force",
        "job_id",
    }
    kwargs = {key: value for key, value in payload.items() if key in allowed}
    result = await sources.sync_oddsportal_odds_snapshots(**kwargs)
    return {
        **result,
        "job_id": job_id or kwargs.get("job_id"),
        "queue_job_id": queue_job_id,
        "execution_backend": "arq",
    }


class WorkerSettings:
    functions = [run_holdout_validation_job, run_oddsportal_snapshot_sync_job]
    redis_settings = redis_settings_from_task_queue(_settings)
    queue_name = _settings.arq_queue_name
    job_timeout = _settings.arq_job_timeout_seconds
    max_jobs = _settings.arq_max_jobs

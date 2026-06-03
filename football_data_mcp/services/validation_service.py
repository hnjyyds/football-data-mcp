from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from dataclasses import dataclass, field
from typing import Any

from football_data_mcp import backtest, validation_store
from football_data_mcp.config import load_task_queue_settings
from football_data_mcp.services.task_queue import (
    ValidationJobStarter,
    build_validation_job_starter,
    validation_job_start_result,
)
from football_data_mcp.validation_diagnostics import build_validation_verdict


_RUNNING_JOBS: dict[str, threading.Thread] = {}
_RUNNING_JOBS_LOCK = threading.Lock()


@dataclass(frozen=True)
class HoldoutValidationJobConfig:
    divisions: list[str] = field(default_factory=lambda: ["E0", "SP1", "I1", "D1", "F1"])
    training_seasons: list[str] = field(default_factory=lambda: ["2122", "2223", "2324", "2425"])
    validation_seasons: list[str] = field(default_factory=lambda: ["2526"])
    edge_thresholds: list[float] = field(default_factory=lambda: [0.01, 0.02, 0.03, 0.04, 0.05])
    min_training_samples_options: list[int] = field(default_factory=lambda: [20, 40, 80, 120])
    max_samples: int | None = None
    min_selection_bets: int = 30
    min_selection_evaluated: int = 100
    min_validation_bets: int = 50
    min_validation_evaluated: int = 100
    historical_rho_min_samples: int = 20
    use_cache: bool = True

    def normalized(self) -> "HoldoutValidationJobConfig":
        return HoldoutValidationJobConfig(
            divisions=[str(item).strip() for item in self.divisions if str(item).strip()],
            training_seasons=[str(item).strip() for item in self.training_seasons if str(item).strip()],
            validation_seasons=[str(item).strip() for item in self.validation_seasons if str(item).strip()],
            edge_thresholds=[float(item) for item in self.edge_thresholds],
            min_training_samples_options=[int(item) for item in self.min_training_samples_options],
            max_samples=int(self.max_samples) if self.max_samples is not None else None,
            min_selection_bets=int(self.min_selection_bets),
            min_selection_evaluated=int(self.min_selection_evaluated),
            min_validation_bets=int(self.min_validation_bets),
            min_validation_evaluated=int(self.min_validation_evaluated),
            historical_rho_min_samples=int(self.historical_rho_min_samples),
            use_cache=bool(self.use_cache),
        )

    def to_store_config(self) -> dict[str, Any]:
        normalized = self.normalized()
        cache_keys = {division: normalized.cache_key_for_division(division) for division in normalized.divisions}
        return {
            "edge_thresholds": normalized.edge_thresholds,
            "min_training_samples_options": normalized.min_training_samples_options,
            "max_samples": normalized.max_samples,
            "min_selection_bets": normalized.min_selection_bets,
            "min_selection_evaluated": normalized.min_selection_evaluated,
            "min_validation_bets": normalized.min_validation_bets,
            "min_validation_evaluated": normalized.min_validation_evaluated,
            "historical_rho_min_samples": normalized.historical_rho_min_samples,
            "use_cache": normalized.use_cache,
            "cache_keys": cache_keys,
        }

    def cache_key_for_division(self, division: str) -> str:
        normalized = self.normalized()
        payload = {
            "method": "holdout_validation_league_v2_asian_handicap_validation",
            "division": division,
            "training_seasons": normalized.training_seasons,
            "validation_seasons": normalized.validation_seasons,
            "edge_thresholds": normalized.edge_thresholds,
            "min_training_samples_options": normalized.min_training_samples_options,
            "max_samples": normalized.max_samples,
            "min_selection_bets": normalized.min_selection_bets,
            "min_selection_evaluated": normalized.min_selection_evaluated,
            "min_validation_bets": normalized.min_validation_bets,
            "min_validation_evaluated": normalized.min_validation_evaluated,
            "historical_rho_min_samples": normalized.historical_rho_min_samples,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        ).hexdigest()


class ValidationJobService:
    def __init__(
        self,
        *,
        db_path: str | None = None,
        job_starter: ValidationJobStarter | None = None,
        running_job_stale_after_seconds: int | None = None,
        running_job_heartbeat_interval_seconds: float | None = None,
    ) -> None:
        self._db_path = db_path
        self._job_starter = job_starter
        self._running_job_stale_after_seconds = (
            int(running_job_stale_after_seconds)
            if running_job_stale_after_seconds is not None
            else _default_running_job_stale_after_seconds()
        )
        self._running_job_heartbeat_interval_seconds = (
            float(running_job_heartbeat_interval_seconds)
            if running_job_heartbeat_interval_seconds is not None
            else _default_running_job_heartbeat_interval_seconds(self._running_job_stale_after_seconds)
        )

    def create_or_resume_holdout_job(
        self,
        config: HoldoutValidationJobConfig | None = None,
        *,
        start_background: bool = False,
        resume: bool = True,
    ) -> dict[str, Any]:
        normalized = (config or HoldoutValidationJobConfig()).normalized()
        job = validation_store.create_validation_job(
            method="holdout_validation_job_v1",
            divisions=normalized.divisions,
            training_seasons=normalized.training_seasons,
            validation_seasons=normalized.validation_seasons,
            config=normalized.to_store_config(),
            resume=resume,
            db_path=self._db_path,
        )
        if start_background:
            validation_store.mark_validation_job_queued(
                str(job["job_id"]),
                backend="thread",
                message=_queue_status_message("thread"),
                db_path=self._db_path,
            )
            self.start_background_runner(str(job["job_id"]))
            job = validation_store.get_validation_job(str(job["job_id"]), db_path=self._db_path) or job
        return job

    async def create_or_resume_holdout_job_async(
        self,
        config: HoldoutValidationJobConfig | None = None,
        *,
        start_background: bool = True,
        resume: bool = True,
    ) -> dict[str, Any]:
        job = self.create_or_resume_holdout_job(config, start_background=False, resume=resume)
        if start_background:
            starter = self._job_starter or build_validation_job_starter(thread_starter=self.start_background_runner)
            start_result = validation_job_start_result(
                await starter.start_holdout_validation_job(str(job["job_id"]))
            )
            validation_store.mark_validation_job_queued(
                str(job["job_id"]),
                backend=start_result.backend,
                queue_job_id=start_result.queue_job_id,
                message=_queue_status_message(start_result.backend),
                db_path=self._db_path,
            )
            job = validation_store.get_validation_job(str(job["job_id"]), db_path=self._db_path) or job
        return job

    def latest_job(self) -> dict[str, Any] | None:
        return validation_store.get_latest_validation_job(db_path=self._db_path)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return validation_store.get_validation_job(job_id, db_path=self._db_path)

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        job = validation_store.cancel_validation_job(job_id, db_path=self._db_path)
        if not job:
            raise ValueError(f"validation job not found: {job_id}")
        return job

    async def retry_job_async(self, job_id: str, *, start_background: bool = True) -> dict[str, Any]:
        job = validation_store.reset_validation_job_for_retry(job_id, db_path=self._db_path)
        if not job:
            raise ValueError(f"validation job not found: {job_id}")
        if start_background:
            starter = self._job_starter or build_validation_job_starter(thread_starter=self.start_background_runner)
            start_result = validation_job_start_result(await starter.start_holdout_validation_job(job_id))
            validation_store.mark_validation_job_queued(
                job_id,
                backend=start_result.backend,
                queue_job_id=start_result.queue_job_id,
                message=_queue_status_message(start_result.backend),
                db_path=self._db_path,
            )
            job = validation_store.get_validation_job(job_id, db_path=self._db_path) or job
        return job

    def start_background_runner(self, job_id: str) -> None:
        with _RUNNING_JOBS_LOCK:
            current = _RUNNING_JOBS.get(job_id)
            if current and current.is_alive():
                return
            thread = threading.Thread(target=lambda: asyncio.run(self.run_holdout_job_inline(job_id)), daemon=True)
            _RUNNING_JOBS[job_id] = thread
            thread.start()

    async def run_holdout_job_inline(
        self,
        job_id: str,
        *,
        execution_backend: str | None = None,
        queue_job_id: str | None = None,
        worker_instance_id: str | None = None,
    ) -> dict[str, Any]:
        job = validation_store.get_validation_job(job_id, db_path=self._db_path)
        if not job:
            raise ValueError(f"validation job not found: {job_id}")
        if job.get("status") in {"cancelled", "completed"}:
            return job
        if execution_backend or queue_job_id or worker_instance_id:
            validation_store.mark_validation_worker_started(
                job_id,
                backend=execution_backend or str(job.get("queue_backend") or "thread"),
                queue_job_id=queue_job_id,
                worker_instance_id=worker_instance_id,
                db_path=self._db_path,
            )
        config = self._config_from_job(job)
        claim = validation_store.claim_validation_job_run(
            job_id,
            stale_after_seconds=self._running_job_stale_after_seconds,
            db_path=self._db_path,
        )
        if not claim.get("claimed"):
            current_job = claim.get("job")
            return current_job if isinstance(current_job, dict) else job
        runner_id = str(claim.get("runner_id") or "")
        if not runner_id:
            raise RuntimeError(f"validation job claim did not return a runner id: {job_id}")
        for division in config.divisions:
            current = validation_store.get_validation_job(job_id, db_path=self._db_path)
            if current and current.get("status") == "cancelled":
                return current
            existing = _league_by_division(current, division) if current else None
            if existing and existing.get("status") == "succeeded":
                continue
            cache_key = config.cache_key_for_division(division)
            cached = (
                validation_store.get_validation_league_cache(cache_key=cache_key, db_path=self._db_path)
                if config.use_cache
                else None
            )
            if cached and isinstance(cached.get("result"), dict):
                if not self._is_current_runner(job_id, runner_id):
                    return validation_store.get_validation_job(job_id, db_path=self._db_path) or {}
                result = dict(cached["result"])
                validation_store.upsert_validation_league_result(
                    job_id,
                    division=division,
                    league=str(result.get("league") or division),
                    status="succeeded",
                    cache_key=cache_key,
                    result=result,
                    cache_hit=True,
                    runner_id=runner_id,
                    db_path=self._db_path,
                )
                continue
            try:
                validation_store.mark_validation_league_running(
                    job_id,
                    division=division,
                    runner_id=runner_id,
                    db_path=self._db_path,
                )
            except RuntimeError:
                return validation_store.get_validation_job(job_id, db_path=self._db_path) or {}
            try:
                heartbeat_stop = threading.Event()
                heartbeat = threading.Thread(
                    target=self._heartbeat_running_division,
                    args=(job_id, division, runner_id, heartbeat_stop),
                    daemon=True,
                )
                heartbeat.start()
                try:
                    result = await self._run_one_division(config, division)
                finally:
                    heartbeat_stop.set()
                    heartbeat.join(timeout=1)
                if self._is_cancelled(job_id):
                    return validation_store.get_validation_job(job_id, db_path=self._db_path) or {}
                if not self._is_current_runner(job_id, runner_id):
                    return validation_store.get_validation_job(job_id, db_path=self._db_path) or {}
                league = str(result.get("league") or division)
                if config.use_cache:
                    validation_store.save_validation_league_cache(
                        cache_key=cache_key,
                        division=division,
                        league=league,
                        result=result,
                        db_path=self._db_path,
                    )
                validation_store.upsert_validation_league_result(
                    job_id,
                    division=division,
                    league=league,
                    status="succeeded",
                    cache_key=cache_key,
                    result=result,
                    runner_id=runner_id,
                    db_path=self._db_path,
                )
            except Exception as exc:
                if self._is_cancelled(job_id):
                    return validation_store.get_validation_job(job_id, db_path=self._db_path) or {}
                if not self._is_current_runner(job_id, runner_id):
                    return validation_store.get_validation_job(job_id, db_path=self._db_path) or {}
                validation_store.upsert_validation_league_result(
                    job_id,
                    division=division,
                    status="failed",
                    cache_key=cache_key,
                    error=f"{type(exc).__name__}: {exc}",
                    runner_id=runner_id,
                    db_path=self._db_path,
                )
        final_job = validation_store.get_validation_job(job_id, db_path=self._db_path)
        if final_job and final_job.get("status") == "cancelled":
            return final_job
        if not self._is_current_runner(job_id, runner_id):
            return final_job or {}
        summary = _aggregate_job_summary(final_job or {})
        status = "completed" if summary.get("failed_leagues", 0) == 0 else "failed"
        validation_store.mark_validation_job_finished(
            job_id,
            status=status,
            result_summary=summary,
            error=None if status == "completed" else "One or more league validations failed.",
            runner_id=runner_id,
            db_path=self._db_path,
        )
        completed = validation_store.get_validation_job(job_id, db_path=self._db_path) or {}
        if status == "completed":
            validation_store.save_validation_result(
                result={
                    "run_id": job_id,
                    "automation_readiness": _automation_readiness(summary),
                    "aggregated": summary,
                    "best_config": _best_config(completed),
                    "job_id": job_id,
                    "method": "holdout_validation_job_v1",
                },
                method="holdout_validation_job_v1",
                divisions=config.divisions,
                training_seasons=config.training_seasons,
                validation_seasons=config.validation_seasons,
                db_path=self._db_path,
            )
        return completed

    def _is_cancelled(self, job_id: str) -> bool:
        job = validation_store.get_validation_job(job_id, db_path=self._db_path)
        return bool(job and job.get("status") == "cancelled")

    def _is_current_runner(self, job_id: str, runner_id: str) -> bool:
        return validation_store.is_validation_job_runner_current(
            job_id,
            runner_id=runner_id,
            db_path=self._db_path,
        )

    def _heartbeat_running_division(
        self,
        job_id: str,
        division: str,
        runner_id: str,
        stop_event: threading.Event,
    ) -> None:
        interval = max(0.01, self._running_job_heartbeat_interval_seconds)
        while not stop_event.wait(interval):
            touched = validation_store.touch_validation_job_run(
                job_id,
                division=division,
                runner_id=runner_id,
                db_path=self._db_path,
            )
            if not touched:
                return

    async def _run_one_division(self, config: HoldoutValidationJobConfig, division: str) -> dict[str, Any]:
        result = await backtest.run_holdout_validation(
            divisions=[division],
            training_seasons=config.training_seasons,
            validation_seasons=config.validation_seasons,
            edge_thresholds=config.edge_thresholds,
            min_training_samples_options=config.min_training_samples_options,
            max_samples=config.max_samples,
            min_selection_bets=config.min_selection_bets,
            min_selection_evaluated=config.min_selection_evaluated,
            min_validation_bets=config.min_validation_bets,
            min_validation_evaluated=config.min_validation_evaluated,
            historical_rho_min_samples=config.historical_rho_min_samples,
        )
        item = (result.get("division_results") or [{}])[0]
        selected = item.get("selected_config") or {}
        validation = item.get("validation_result") or {}
        calibrated = item.get("calibrated_validation_result") or validation
        return {
            "division": division,
            "league": item.get("league") or division,
            "selected_config": selected,
            "validation_result": validation,
            "calibrated_validation_result": calibrated,
            "holdout_readiness": result.get("holdout_readiness") or {},
            "errors": result.get("errors") or [],
        }

    def _config_from_job(self, job: dict[str, Any]) -> HoldoutValidationJobConfig:
        config_value = job.get("config")
        config: dict[str, Any] = config_value if isinstance(config_value, dict) else {}
        return HoldoutValidationJobConfig(
            divisions=[str(item) for item in (job.get("divisions") or [])],
            training_seasons=[str(item) for item in (job.get("training_seasons") or [])],
            validation_seasons=[str(item) for item in (job.get("validation_seasons") or [])],
            edge_thresholds=[float(item) for item in (config.get("edge_thresholds") or [0.03])],
            min_training_samples_options=[int(item) for item in (config.get("min_training_samples_options") or [20])],
            max_samples=config.get("max_samples"),
            min_selection_bets=int(config.get("min_selection_bets") or 30),
            min_selection_evaluated=int(config.get("min_selection_evaluated") or 100),
            min_validation_bets=int(config.get("min_validation_bets") or 50),
            min_validation_evaluated=int(config.get("min_validation_evaluated") or 100),
            historical_rho_min_samples=int(config.get("historical_rho_min_samples") or 20),
            use_cache=bool(config.get("use_cache", True)),
        ).normalized()


def _league_by_division(job: dict[str, Any] | None, division: str) -> dict[str, Any] | None:
    for item in (job or {}).get("league_results") or []:
        if item.get("division") == division:
            return item
    return None


def _default_running_job_stale_after_seconds() -> int:
    try:
        return max(60, int(load_task_queue_settings().validation_job_stale_after_seconds))
    except Exception:
        return 3900


def _default_running_job_heartbeat_interval_seconds(stale_after_seconds: int) -> float:
    return float(max(5, min(15, int(stale_after_seconds / 10))))


def _queue_status_message(backend: str) -> str:
    if backend == "arq":
        return "Holdout validation was queued in ARQ and will be executed by the worker."
    if backend == "thread":
        return "Holdout validation is running in a local background thread."
    return f"Holdout validation was queued via {backend}."


def _metric(result: dict[str, Any], key: str) -> float | None:
    value = result.get(key)
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _aggregate_asian_handicap_validation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summaries: list[dict[str, Any]] = []
    for row in rows:
        summary = row.get("asian_handicap_validation")
        if isinstance(summary, dict):
            summaries.append(summary)
    available_count = sum(int(summary.get("available_count") or 0) for summary in summaries)
    evaluated_count = sum(int(summary.get("evaluated_count") or 0) for summary in summaries)
    bet_count = sum(int(summary.get("bet_count") or 0) for summary in summaries)
    hit_count = sum(int(summary.get("hit_count") or 0) for summary in summaries)
    push_count = sum(int(summary.get("push_count") or 0) for summary in summaries)
    loss_count = sum(int(summary.get("loss_count") or 0) for summary in summaries)
    profit = round(sum(float(summary.get("profit") or 0.0) for summary in summaries), 6)
    result_counts: dict[str, int] = {}
    for summary in summaries:
        for result, count in (summary.get("result_counts") or {}).items():
            result_counts[str(result)] = result_counts.get(str(result), 0) + int(count or 0)
    if bet_count >= 50:
        status = "sample_ready"
    elif bet_count > 0:
        status = "insufficient_sample"
    elif available_count > 0:
        status = "available_but_no_recommendations"
    else:
        status = "missing"
    return {
        "market": "asian_handicap",
        "status": status,
        "available_count": available_count,
        "evaluated_count": evaluated_count,
        "bet_count": bet_count,
        "hit_count": hit_count,
        "push_count": push_count,
        "loss_count": loss_count,
        "profit": profit,
        "roi": round(profit / bet_count, 6) if bet_count else None,
        "result_counts": result_counts,
        "sample_gate": {
            "min_bets_for_validation": 50,
            "passed": bet_count >= 50,
        },
        "policy": "亚盘验证独立于 1X2 Log Loss/Brier；样本不足时不能证明 asian_handicap 准确。",
    }


def _aggregate_job_summary(job: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for item in job.get("league_results") or []:
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        row = result.get("calibrated_validation_result") or result.get("validation_result") or {}
        if isinstance(row, dict):
            rows.append(row)
    evaluated = sum(int(row.get("evaluated_count") or 0) for row in rows)
    bet_count = sum(int(row.get("bet_count") or 0) for row in rows)
    profit = round(sum(float(row.get("profit") or 0.0) for row in rows), 6)

    def weighted(key: str) -> float | None:
        total = 0.0
        weight = 0
        for row in rows:
            value = _metric(row, key)
            row_weight = int(row.get("evaluated_count") or 0)
            if value is None or row_weight <= 0:
                continue
            total += value * row_weight
            weight += row_weight
        return round(total / weight, 6) if weight else None

    model_ll = weighted("model_log_loss_1x2")
    market_ll = weighted("market_log_loss_1x2")
    model_brier = weighted("model_brier_score_1x2")
    market_brier = weighted("market_brier_score_1x2")
    progress = job.get("progress") or {}
    asian_handicap_validation = _aggregate_asian_handicap_validation(rows)
    metric_scope = {
        "probability_market": "moneyline_1x2",
        "probability_market_label": "胜平负/1X2",
        "log_loss_market": "moneyline_1x2",
        "brier_market": "moneyline_1x2",
        "asian_handicap_specific": False,
        "asian_handicap_evaluated_count": asian_handicap_validation["evaluated_count"],
        "asian_handicap_bet_count": asian_handicap_validation["bet_count"],
        "warning": (
            "当前 Holdout 的 Log Loss/Brier 是胜平负/1X2 概率校验，不是亚盘专属验证；"
            "亚盘准确性仍需看 asian_handicap 结算样本、CLV 和盘口结果。"
        ),
    }
    summary = {
        "evaluated_count": evaluated,
        "bet_count": bet_count,
        "profit": profit,
        "roi": round(profit / bet_count, 6) if bet_count else None,
        "log_loss_model": model_ll,
        "log_loss_market": market_ll,
        "log_loss_diff": round(model_ll - market_ll, 6) if model_ll is not None and market_ll is not None else None,
        "brier_model": model_brier,
        "brier_market": market_brier,
        "brier_diff": round(model_brier - market_brier, 6) if model_brier is not None and market_brier is not None else None,
        "total_leagues": progress.get("total_leagues", 0),
        "completed_leagues": progress.get("completed_leagues", 0),
        "failed_leagues": progress.get("failed_leagues", 0),
        "metric_scope": metric_scope,
        "asian_handicap_validation": asian_handicap_validation,
    }
    summary["verdict"] = build_validation_verdict(summary)
    return summary


def _automation_readiness(summary: dict[str, Any]) -> str:
    log_loss_diff = summary.get("log_loss_diff")
    roi = summary.get("roi")
    if isinstance(log_loss_diff, (int, float)) and log_loss_diff < 0 and isinstance(roi, (int, float)) and roi > 0:
        return "watchlist"
    return "not_ready"


def _best_config(job: dict[str, Any]) -> dict[str, Any]:
    for item in job.get("league_results") or []:
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        config = result.get("selected_config")
        if isinstance(config, dict) and config:
            return config
    return {}

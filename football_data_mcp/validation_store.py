"""
Persist holdout validation results so dashboard can show "last verification status".

Schema: model_validation_history table stores each holdout run with summary
metrics. Used by frontend Model section to display the most recent diagnostic.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from football_data_mcp import learning_store
from football_data_mcp.validation_diagnostics import build_validation_verdict

logger = logging.getLogger(__name__)
_VALIDATION_JOB_STALE_AFTER_SECONDS = 3900


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or learning_store.learning_db_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS model_validation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            method TEXT NOT NULL,
            divisions_json TEXT NOT NULL,
            training_seasons_json TEXT NOT NULL,
            validation_seasons_json TEXT NOT NULL,
            log_loss_model REAL,
            log_loss_market REAL,
            log_loss_diff REAL,
            brier_model REAL,
            brier_market REAL,
            brier_diff REAL,
            roi REAL,
            bet_count INTEGER,
            evaluated_count INTEGER,
            automation_readiness TEXT,
            beats_market INTEGER,
            best_config_json TEXT,
            raw_json TEXT NOT NULL,
            created_at_utc TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_validation_history_created
        ON model_validation_history(created_at_utc DESC)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS model_validation_jobs (
            job_id TEXT PRIMARY KEY,
            scope_hash TEXT NOT NULL,
            method TEXT NOT NULL,
            status TEXT NOT NULL,
            runner_id TEXT,
            divisions_json TEXT NOT NULL,
            training_seasons_json TEXT NOT NULL,
            validation_seasons_json TEXT NOT NULL,
            config_json TEXT NOT NULL,
            result_summary_json TEXT NOT NULL DEFAULT '{}',
            last_error TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            retry_count INTEGER NOT NULL DEFAULT 0,
            last_claim_reason TEXT,
            last_retry_at_utc TEXT,
            runner_heartbeat_at_utc TEXT,
            recovered_at_utc TEXT,
            queue_backend TEXT,
            queue_job_id TEXT,
            queued_at_utc TEXT,
            queue_status_message TEXT,
            created_at_utc TEXT NOT NULL,
            started_at_utc TEXT,
            updated_at_utc TEXT NOT NULL,
            finished_at_utc TEXT
        )
        """
    )
    _ensure_column(conn, "model_validation_jobs", "runner_id", "TEXT")
    _ensure_column(conn, "model_validation_jobs", "attempt_count", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "model_validation_jobs", "retry_count", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "model_validation_jobs", "last_claim_reason", "TEXT")
    _ensure_column(conn, "model_validation_jobs", "last_retry_at_utc", "TEXT")
    _ensure_column(conn, "model_validation_jobs", "runner_heartbeat_at_utc", "TEXT")
    _ensure_column(conn, "model_validation_jobs", "recovered_at_utc", "TEXT")
    _ensure_column(conn, "model_validation_jobs", "queue_backend", "TEXT")
    _ensure_column(conn, "model_validation_jobs", "queue_job_id", "TEXT")
    _ensure_column(conn, "model_validation_jobs", "queued_at_utc", "TEXT")
    _ensure_column(conn, "model_validation_jobs", "queue_status_message", "TEXT")
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_validation_jobs_scope_updated
        ON model_validation_jobs(scope_hash, updated_at_utc DESC)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS model_validation_league_results (
            job_id TEXT NOT NULL,
            division TEXT NOT NULL,
            league TEXT,
            status TEXT NOT NULL,
            runner_id TEXT,
            cache_key TEXT NOT NULL,
            cache_hit INTEGER NOT NULL DEFAULT 0,
            result_json TEXT NOT NULL DEFAULT '{}',
            error TEXT,
            started_at_utc TEXT,
            updated_at_utc TEXT NOT NULL,
            finished_at_utc TEXT,
            PRIMARY KEY (job_id, division)
        )
        """
    )
    _ensure_column(conn, "model_validation_league_results", "runner_id", "TEXT")
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_validation_league_results_cache
        ON model_validation_league_results(cache_key, status, updated_at_utc DESC)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS model_validation_league_cache (
            cache_key TEXT PRIMARY KEY,
            division TEXT NOT NULL,
            league TEXT,
            result_json TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS model_validation_job_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            message TEXT NOT NULL,
            division TEXT,
            runner_id TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at_utc TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_validation_job_events_job_created
        ON model_validation_job_events(job_id, created_at_utc ASC, id ASC)
        """
    )
    conn.commit()


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
    columns = {
        str(row["name"])
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _insert_validation_job_event(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    event_type: str,
    message: str,
    severity: str = "info",
    division: str | None = None,
    runner_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    created_at_utc: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO model_validation_job_events (
            job_id, event_type, severity, message, division, runner_id,
            metadata_json, created_at_utc
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            event_type,
            severity,
            message,
            division,
            runner_id,
            json.dumps(metadata or {}, sort_keys=True, default=str),
            created_at_utc or learning_store.now_utc_iso(),
        ),
    )


def save_validation_result(
    *,
    result: dict[str, Any],
    method: str,
    divisions: list[str],
    training_seasons: list[str],
    validation_seasons: list[str],
    db_path: str | None = None,
) -> dict[str, Any]:
    """Persist one holdout validation run."""
    run_id = result.get("run_id") or f"validation-{int(time.time())}"
    summary = result.get("aggregated") or result.get("summary") or {}
    best_config = result.get("best_config") or result.get("selected_config") or {}

    log_loss_model = _safe_float(summary.get("log_loss_model"))
    log_loss_market = _safe_float(summary.get("log_loss_market"))
    log_loss_diff = (
        log_loss_model - log_loss_market
        if log_loss_model is not None and log_loss_market is not None
        else None
    )
    brier_model = _safe_float(summary.get("brier_model"))
    brier_market = _safe_float(summary.get("brier_market"))
    brier_diff = (
        brier_model - brier_market
        if brier_model is not None and brier_market is not None
        else None
    )

    automation_readiness = str(result.get("automation_readiness") or "not_ready")
    beats_market = (
        1 if log_loss_diff is not None and log_loss_diff < 0 else 0
    )

    with _connect(db_path) as conn:
        ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO model_validation_history (
                run_id, method, divisions_json, training_seasons_json,
                validation_seasons_json, log_loss_model, log_loss_market,
                log_loss_diff, brier_model, brier_market, brier_diff,
                roi, bet_count, evaluated_count, automation_readiness,
                beats_market, best_config_json, raw_json, created_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                method,
                json.dumps(divisions),
                json.dumps(training_seasons),
                json.dumps(validation_seasons),
                log_loss_model,
                log_loss_market,
                log_loss_diff,
                brier_model,
                brier_market,
                brier_diff,
                _safe_float(summary.get("roi")),
                int(summary.get("bet_count") or 0),
                int(summary.get("evaluated_count") or summary.get("samples_evaluated") or 0),
                automation_readiness,
                beats_market,
                json.dumps(best_config),
                json.dumps(result, default=str),
                learning_store.now_utc_iso(),
            ),
        )
        conn.commit()

    return {
        "status": "ok",
        "run_id": run_id,
        "log_loss_diff": log_loss_diff,
        "beats_market": bool(beats_market),
        "automation_readiness": automation_readiness,
    }


def get_latest_validation(*, db_path: str | None = None) -> dict[str, Any] | None:
    """Fetch the most recent validation run for dashboard display."""
    with _connect(db_path) as conn:
        ensure_schema(conn)
        row = conn.execute(
            """
            SELECT * FROM model_validation_history
            ORDER BY created_at_utc DESC
            LIMIT 1
            """
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    try:
        item["divisions"] = json.loads(item.pop("divisions_json") or "[]")
        item["training_seasons"] = json.loads(item.pop("training_seasons_json") or "[]")
        item["validation_seasons"] = json.loads(item.pop("validation_seasons_json") or "[]")
        item["best_config"] = json.loads(item.pop("best_config_json") or "{}")
    except (json.JSONDecodeError, TypeError):
        pass
    item.pop("raw_json", None)
    return item


def validation_scope_hash(
    *,
    method: str,
    divisions: list[str],
    training_seasons: list[str],
    validation_seasons: list[str],
    config: dict[str, Any],
) -> str:
    payload = {
        "method": method,
        "divisions": divisions,
        "training_seasons": training_seasons,
        "validation_seasons": validation_seasons,
        "config": config,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def create_validation_job(
    *,
    method: str,
    divisions: list[str],
    training_seasons: list[str],
    validation_seasons: list[str],
    config: dict[str, Any],
    resume: bool = True,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Create or resume a persisted holdout-validation job."""
    scope_hash = validation_scope_hash(
        method=method,
        divisions=divisions,
        training_seasons=training_seasons,
        validation_seasons=validation_seasons,
        config=config,
    )
    with _connect(db_path) as conn:
        ensure_schema(conn)
        if resume:
            row = conn.execute(
                """
                SELECT job_id FROM model_validation_jobs
                WHERE scope_hash = ?
                  AND status NOT IN ('completed', 'cancelled')
                ORDER BY updated_at_utc DESC
                LIMIT 1
                """,
                (scope_hash,),
            ).fetchone()
            if row:
                job = get_validation_job(str(row["job_id"]), db_path=db_path)
                if job:
                    return job
        now = learning_store.now_utc_iso()
        job_id = f"holdout-{int(time.time())}-{scope_hash[:10]}-{uuid.uuid4().hex[:8]}"
        conn.execute(
            """
            INSERT INTO model_validation_jobs (
                job_id, scope_hash, method, status, divisions_json,
                training_seasons_json, validation_seasons_json, config_json,
                created_at_utc, updated_at_utc
            )
            VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                scope_hash,
                method,
                json.dumps(divisions),
                json.dumps(training_seasons),
                json.dumps(validation_seasons),
                json.dumps(config, sort_keys=True, default=str),
                now,
                now,
            ),
        )
        for division in divisions:
            conn.execute(
                """
                INSERT INTO model_validation_league_results (
                    job_id, division, league, status, cache_key, updated_at_utc
                )
                VALUES (?, ?, '', 'pending', ?, ?)
                """,
                (job_id, division, str(config.get("cache_keys", {}).get(division) or ""), now),
            )
        _insert_validation_job_event(
            conn,
            job_id=job_id,
            event_type="job_created",
            message=f"Created holdout validation job for {len(divisions)} leagues.",
            metadata={
                "method": method,
                "division_count": len(divisions),
                "training_seasons": training_seasons,
                "validation_seasons": validation_seasons,
            },
            created_at_utc=now,
        )
        conn.commit()
    job = get_validation_job(job_id, db_path=db_path)
    if job is None:
        raise RuntimeError("validation job was not created")
    return job


def mark_validation_job_running(job_id: str, *, db_path: str | None = None) -> None:
    now = learning_store.now_utc_iso()
    with _connect(db_path) as conn:
        ensure_schema(conn)
        conn.execute(
            """
            UPDATE model_validation_jobs
            SET status = 'running',
                started_at_utc = COALESCE(started_at_utc, ?),
                updated_at_utc = ?,
                last_error = NULL
            WHERE job_id = ? AND status NOT IN ('completed', 'cancelled')
            """,
            (now, now, job_id),
        )
        conn.execute(
            """
            UPDATE model_validation_league_results
            SET status = 'pending', updated_at_utc = ?
            WHERE job_id = ?
              AND status = 'running'
              AND EXISTS (
                  SELECT 1 FROM model_validation_jobs
                  WHERE job_id = ? AND status = 'running'
              )
            """,
            (now, job_id, job_id),
        )
        conn.commit()


def mark_validation_job_queued(
    job_id: str,
    *,
    backend: str,
    queue_job_id: str | None = None,
    message: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any] | None:
    """Record queue handoff metadata so UI can explain how a validation job will run."""
    now = learning_store.now_utc_iso()
    queue_message = message or f"Validation job was queued via {backend}."
    with _connect(db_path) as conn:
        ensure_schema(conn)
        conn.execute(
            """
            UPDATE model_validation_jobs
            SET queue_backend = ?,
                queue_job_id = COALESCE(?, queue_job_id),
                queued_at_utc = ?,
                queue_status_message = ?,
                updated_at_utc = ?
            WHERE job_id = ?
              AND status NOT IN ('completed', 'cancelled')
            """,
            (backend, queue_job_id, now, queue_message, now, job_id),
        )
        _insert_validation_job_event(
            conn,
            job_id=job_id,
            event_type="job_queued",
            message=queue_message,
            metadata={"backend": backend, "queue_job_id": queue_job_id},
            created_at_utc=now,
        )
        conn.commit()
    return get_validation_job(job_id, db_path=db_path)


def mark_validation_worker_started(
    job_id: str,
    *,
    backend: str,
    queue_job_id: str | None = None,
    worker_instance_id: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any] | None:
    """Record the concrete worker execution context for a queued validation job."""
    now = learning_store.now_utc_iso()
    with _connect(db_path) as conn:
        ensure_schema(conn)
        conn.execute(
            """
            UPDATE model_validation_jobs
            SET queue_backend = COALESCE(queue_backend, ?),
                queue_job_id = COALESCE(?, queue_job_id),
                updated_at_utc = ?
            WHERE job_id = ?
              AND status NOT IN ('completed', 'cancelled')
            """,
            (backend, queue_job_id, now, job_id),
        )
        _insert_validation_job_event(
            conn,
            job_id=job_id,
            event_type="worker_started",
            message=(
                f"{backend.upper()} worker started validation job"
                f"{f' ({queue_job_id})' if queue_job_id else ''}."
            ),
            metadata={
                "backend": backend,
                "queue_job_id": queue_job_id,
                "worker_instance_id": worker_instance_id,
            },
            created_at_utc=now,
        )
        conn.commit()
    return get_validation_job(job_id, db_path=db_path)


def claim_validation_job_run(
    job_id: str,
    *,
    stale_after_seconds: int,
    runner_id: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Claim a validation job for one runner and recover stale running state.

    业务规则：
    - completed/cancelled 不再执行；
    - active running 说明已有 worker 在跑，当前 runner 直接退出，避免重复算同一联赛；
    - running 超过阈值视为 worker 断联，把 running 联赛退回 pending 后继续执行。
    """
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    stale_after = max(0, int(stale_after_seconds))
    active_runner_id = runner_id or uuid.uuid4().hex
    recovered = False
    reason = "claimed"
    with _connect(db_path) as conn:
        ensure_schema(conn)
        row = conn.execute("SELECT * FROM model_validation_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            return {
                "claimed": False,
                "reason": "missing",
                "recovered": False,
                "runner_id": None,
                "job": None,
            }

        status = str(row["status"])
        if status in {"completed", "cancelled"}:
            conn.commit()
            return {
                "claimed": False,
                "reason": status,
                "recovered": False,
                "runner_id": row["runner_id"],
                "job": get_validation_job(job_id, db_path=db_path),
            }

        if status == "running":
            updated_at = _parse_iso_datetime(row["updated_at_utc"])
            is_stale = updated_at is None or (now_dt - updated_at).total_seconds() > stale_after
            if not is_stale:
                conn.commit()
                return {
                    "claimed": False,
                    "reason": "already_running",
                    "recovered": False,
                    "runner_id": row["runner_id"],
                    "job": get_validation_job(job_id, db_path=db_path),
                }
            recovered = True
            reason = "recovered_stale_runner"
            recovery_message = (
                f"Previous validation runner exceeded heartbeat window ({stale_after}s); "
                "released for retry."
            )
            conn.execute(
                """
                UPDATE model_validation_league_results
                SET status = 'pending',
                    runner_id = NULL,
                    error = ?,
                    updated_at_utc = ?,
                    finished_at_utc = NULL
                WHERE job_id = ? AND status = 'running'
                """,
                (recovery_message, now, job_id),
            )
            _insert_validation_job_event(
                conn,
                job_id=job_id,
                event_type="stale_runner_recovered",
                severity="warning",
                message=recovery_message,
                runner_id=row["runner_id"],
                metadata={"stale_after_seconds": stale_after},
                created_at_utc=now,
            )

        conn.execute(
            """
            UPDATE model_validation_jobs
            SET status = 'running',
                runner_id = ?,
                attempt_count = COALESCE(attempt_count, 0) + 1,
                last_claim_reason = ?,
                started_at_utc = COALESCE(started_at_utc, ?),
                updated_at_utc = ?,
                runner_heartbeat_at_utc = ?,
                recovered_at_utc = ?,
                finished_at_utc = NULL,
                last_error = ?
            WHERE job_id = ? AND status NOT IN ('completed', 'cancelled')
            """,
            (
                active_runner_id,
                reason,
                now,
                now,
                now,
                now if recovered else row["recovered_at_utc"],
                (
                    f"Recovered stale validation runner after {stale_after}s; continuing unfinished leagues."
                    if recovered
                    else None
                ),
                job_id,
            ),
        )
        _insert_validation_job_event(
            conn,
            job_id=job_id,
            event_type="job_claimed",
            message=(
                "Worker recovered and claimed the validation job."
                if recovered
                else "Worker claimed the validation job."
            ),
            runner_id=active_runner_id,
            metadata={"claim_reason": reason, "recovered": recovered},
            created_at_utc=now,
        )
        conn.commit()

    return {
        "claimed": True,
        "reason": reason,
        "recovered": recovered,
        "runner_id": active_runner_id,
        "job": get_validation_job(job_id, db_path=db_path),
    }


def touch_validation_job_run(
    job_id: str,
    *,
    division: str | None = None,
    runner_id: str | None = None,
    db_path: str | None = None,
) -> bool:
    """Refresh running job timestamps so active workers are not mistaken for stale jobs."""
    now = learning_store.now_utc_iso()
    with _connect(db_path) as conn:
        ensure_schema(conn)
        if runner_id:
            cursor = conn.execute(
                """
                UPDATE model_validation_jobs
                SET updated_at_utc = ?,
                    runner_heartbeat_at_utc = ?
                WHERE job_id = ? AND status = 'running' AND runner_id = ?
                """,
                (now, now, job_id, runner_id),
            )
        else:
            cursor = conn.execute(
                """
                UPDATE model_validation_jobs
                SET updated_at_utc = ?,
                    runner_heartbeat_at_utc = ?
                WHERE job_id = ? AND status = 'running'
                """,
                (now, now, job_id),
            )
        touched = cursor.rowcount > 0
        if division and touched:
            if runner_id:
                conn.execute(
                    """
                    UPDATE model_validation_league_results
                    SET updated_at_utc = ?
                    WHERE job_id = ? AND division = ? AND status = 'running' AND runner_id = ?
                    """,
                    (now, job_id, division, runner_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE model_validation_league_results
                    SET updated_at_utc = ?
                    WHERE job_id = ? AND division = ? AND status = 'running'
                    """,
                    (now, job_id, division),
                )
        conn.commit()
    return touched


def is_validation_job_runner_current(
    job_id: str,
    *,
    runner_id: str | None,
    db_path: str | None = None,
) -> bool:
    if not runner_id:
        return True
    with _connect(db_path) as conn:
        ensure_schema(conn)
        row = conn.execute(
            """
            SELECT 1
            FROM model_validation_jobs
            WHERE job_id = ? AND status = 'running' AND runner_id = ?
            """,
            (job_id, runner_id),
        ).fetchone()
    return row is not None


def mark_validation_job_finished(
    job_id: str,
    *,
    status: str,
    result_summary: dict[str, Any] | None = None,
    error: str | None = None,
    runner_id: str | None = None,
    db_path: str | None = None,
) -> None:
    now = learning_store.now_utc_iso()
    with _connect(db_path) as conn:
        ensure_schema(conn)
        params = (
            status,
            json.dumps(result_summary or {}, sort_keys=True, default=str),
            error,
            now,
            now if status in {"completed", "failed", "cancelled"} else None,
            job_id,
        )
        if runner_id:
            cursor = conn.execute(
                """
                UPDATE model_validation_jobs
                SET status = ?,
                    result_summary_json = ?,
                    last_error = ?,
                    updated_at_utc = ?,
                    finished_at_utc = ?
                WHERE job_id = ? AND runner_id = ?
                """,
                (*params, runner_id),
            )
            if cursor.rowcount == 0:
                raise RuntimeError(f"stale validation runner cannot finish job {job_id}")
        else:
            conn.execute(
                """
                UPDATE model_validation_jobs
                SET status = ?,
                    result_summary_json = ?,
                    last_error = ?,
                    updated_at_utc = ?,
                    finished_at_utc = ?
                WHERE job_id = ?
                """,
                params,
            )
        _insert_validation_job_event(
            conn,
            job_id=job_id,
            event_type=f"job_{status}",
            severity="error" if status == "failed" else "warning" if status == "cancelled" else "info",
            message=error or f"Validation job {status}.",
            runner_id=runner_id,
            metadata={"status": status, "summary": result_summary or {}},
            created_at_utc=now,
        )
        conn.commit()


def cancel_validation_job(job_id: str, *, db_path: str | None = None) -> dict[str, Any] | None:
    """Cooperatively cancel a validation job and mark unfinished leagues cancelled."""
    now = learning_store.now_utc_iso()
    with _connect(db_path) as conn:
        ensure_schema(conn)
        row = conn.execute("SELECT status FROM model_validation_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            return None
        if str(row["status"]) in {"completed", "cancelled"}:
            conn.commit()
            return get_validation_job(job_id, db_path=db_path)
        conn.execute(
            """
            UPDATE model_validation_jobs
            SET status = 'cancelled',
                runner_id = NULL,
                last_error = 'Cancelled by user.',
                updated_at_utc = ?,
                finished_at_utc = ?
            WHERE job_id = ?
            """,
            (now, now, job_id),
        )
        conn.execute(
            """
            UPDATE model_validation_league_results
            SET status = 'cancelled',
                runner_id = NULL,
                error = COALESCE(error, 'Cancelled by user.'),
                updated_at_utc = ?,
                finished_at_utc = ?
            WHERE job_id = ? AND status IN ('pending', 'running', 'failed')
            """,
            (now, now, job_id),
        )
        _insert_validation_job_event(
            conn,
            job_id=job_id,
            event_type="job_cancelled",
            severity="warning",
            message="Cancelled by user.",
            created_at_utc=now,
        )
        conn.commit()
    return get_validation_job(job_id, db_path=db_path)


def reset_validation_job_for_retry(job_id: str, *, db_path: str | None = None) -> dict[str, Any] | None:
    """Prepare a failed/cancelled validation job to continue from unfinished leagues."""
    now = learning_store.now_utc_iso()
    with _connect(db_path) as conn:
        ensure_schema(conn)
        row = conn.execute("SELECT status FROM model_validation_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            return None
        conn.execute(
            """
            UPDATE model_validation_jobs
            SET status = 'pending',
                runner_id = NULL,
                retry_count = COALESCE(retry_count, 0) + 1,
                last_retry_at_utc = ?,
                result_summary_json = '{}',
                last_error = NULL,
                updated_at_utc = ?,
                finished_at_utc = NULL
            WHERE job_id = ? AND status IN ('failed', 'cancelled', 'running', 'pending')
            """,
            (now, now, job_id),
        )
        conn.execute(
            """
            UPDATE model_validation_league_results
            SET status = 'pending',
                runner_id = NULL,
                error = NULL,
                updated_at_utc = ?,
                finished_at_utc = NULL
            WHERE job_id = ? AND status IN ('failed', 'cancelled', 'running', 'pending')
            """,
            (now, job_id),
        )
        _insert_validation_job_event(
            conn,
            job_id=job_id,
            event_type="job_retry_requested",
            severity="warning",
            message="Retry requested; unfinished leagues were reset to pending.",
            created_at_utc=now,
        )
        conn.commit()
    return get_validation_job(job_id, db_path=db_path)


def mark_validation_league_running(
    job_id: str,
    *,
    division: str,
    runner_id: str | None = None,
    db_path: str | None = None,
) -> None:
    now = learning_store.now_utc_iso()
    with _connect(db_path) as conn:
        ensure_schema(conn)
        if runner_id:
            cursor = conn.execute(
                """
                UPDATE model_validation_league_results
                SET status = 'running',
                    runner_id = ?,
                    started_at_utc = COALESCE(started_at_utc, ?),
                    updated_at_utc = ?,
                    error = NULL
                WHERE job_id = ? AND division = ? AND (runner_id IS NULL OR runner_id = ?)
                """,
                (runner_id, now, now, job_id, division, runner_id),
            )
            if cursor.rowcount == 0:
                raise RuntimeError(f"stale validation runner cannot start league {division}")
        else:
            cursor = conn.execute(
                """
                UPDATE model_validation_league_results
                SET status = 'running',
                    started_at_utc = COALESCE(started_at_utc, ?),
                    updated_at_utc = ?,
                    error = NULL
                WHERE job_id = ? AND division = ?
                """,
                (now, now, job_id, division),
            )
        if cursor.rowcount > 0:
            _insert_validation_job_event(
                conn,
                job_id=job_id,
                event_type="league_started",
                message=f"{division} validation started.",
                division=division,
                runner_id=runner_id,
                created_at_utc=now,
            )
        conn.commit()


def upsert_validation_league_result(
    job_id: str,
    *,
    division: str,
    league: str = "",
    status: str,
    cache_key: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    cache_hit: bool = False,
    runner_id: str | None = None,
    db_path: str | None = None,
) -> None:
    now = learning_store.now_utc_iso()
    with _connect(db_path) as conn:
        ensure_schema(conn)
        if runner_id:
            cursor = conn.execute(
                """
                UPDATE model_validation_league_results
                SET league = ?,
                    status = ?,
                    runner_id = ?,
                    cache_key = ?,
                    cache_hit = ?,
                    result_json = ?,
                    error = ?,
                    started_at_utc = COALESCE(started_at_utc, ?),
                    updated_at_utc = ?,
                    finished_at_utc = ?
                WHERE job_id = ? AND division = ? AND (runner_id IS NULL OR runner_id = ?)
                """,
                (
                    league,
                    status,
                    runner_id,
                    cache_key,
                    1 if cache_hit else 0,
                    json.dumps(result or {}, sort_keys=True, default=str),
                    error,
                    now,
                    now,
                    now if status in {"succeeded", "failed", "skipped", "cancelled"} else None,
                    job_id,
                    division,
                    runner_id,
                ),
            )
            if cursor.rowcount == 0:
                raise RuntimeError(f"stale validation runner cannot write league {division}")
            _insert_validation_job_event(
                conn,
                job_id=job_id,
                event_type=_league_result_event_type(status),
                severity=_league_result_event_severity(status),
                message=_league_result_event_message(
                    division=division,
                    league=league,
                    status=status,
                    error=error,
                    cache_hit=cache_hit,
                ),
                division=division,
                runner_id=runner_id,
                metadata={"status": status, "cache_hit": cache_hit},
                created_at_utc=now,
            )
            conn.commit()
            return
        conn.execute(
            """
            INSERT INTO model_validation_league_results (
                job_id, division, league, status, cache_key, cache_hit,
                result_json, error, started_at_utc, updated_at_utc, finished_at_utc, runner_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id, division) DO UPDATE SET
                league = excluded.league,
                status = excluded.status,
                cache_key = excluded.cache_key,
                cache_hit = excluded.cache_hit,
                result_json = excluded.result_json,
                error = excluded.error,
                updated_at_utc = excluded.updated_at_utc,
                finished_at_utc = excluded.finished_at_utc,
                runner_id = excluded.runner_id
            """,
            (
                job_id,
                division,
                league,
                status,
                cache_key,
                1 if cache_hit else 0,
                json.dumps(result or {}, sort_keys=True, default=str),
                error,
                now,
                now,
                now if status in {"succeeded", "failed", "skipped", "cancelled"} else None,
                runner_id,
            ),
        )
        _insert_validation_job_event(
            conn,
            job_id=job_id,
            event_type=_league_result_event_type(status),
            severity=_league_result_event_severity(status),
            message=_league_result_event_message(
                division=division,
                league=league,
                status=status,
                error=error,
                cache_hit=cache_hit,
            ),
            division=division,
            runner_id=runner_id,
            metadata={"status": status, "cache_hit": cache_hit},
            created_at_utc=now,
        )
        conn.commit()


def save_validation_league_cache(
    *,
    cache_key: str,
    division: str,
    league: str = "",
    result: dict[str, Any],
    db_path: str | None = None,
) -> None:
    now = learning_store.now_utc_iso()
    with _connect(db_path) as conn:
        ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO model_validation_league_cache (
                cache_key, division, league, result_json, created_at_utc, updated_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                league = excluded.league,
                result_json = excluded.result_json,
                updated_at_utc = excluded.updated_at_utc
            """,
            (cache_key, division, league, json.dumps(result, sort_keys=True, default=str), now, now),
        )
        conn.commit()


def get_validation_league_cache(*, cache_key: str, db_path: str | None = None) -> dict[str, Any] | None:
    if not cache_key:
        return None
    with _connect(db_path) as conn:
        ensure_schema(conn)
        row = conn.execute(
            "SELECT * FROM model_validation_league_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["result"] = _json_dict(item.pop("result_json", "{}"))
    return item


def get_validation_job(job_id: str, *, db_path: str | None = None) -> dict[str, Any] | None:
    with _connect(db_path) as conn:
        ensure_schema(conn)
        row = conn.execute("SELECT * FROM model_validation_jobs WHERE job_id = ?", (job_id,)).fetchone()
        league_rows = conn.execute(
            """
            SELECT * FROM model_validation_league_results
            WHERE job_id = ?
            ORDER BY rowid ASC
            """,
            (job_id,),
        ).fetchall()
        event_rows = conn.execute(
            """
            SELECT * FROM model_validation_job_events
            WHERE job_id = ?
            ORDER BY created_at_utc ASC, id ASC
            """,
            (job_id,),
        ).fetchall()
    if not row:
        return None
    return _job_from_rows(
        dict(row),
        [dict(item) for item in league_rows],
        [dict(item) for item in event_rows],
    )


def get_latest_validation_job(*, db_path: str | None = None) -> dict[str, Any] | None:
    with _connect(db_path) as conn:
        ensure_schema(conn)
        row = conn.execute(
            """
            SELECT job_id FROM model_validation_jobs
            ORDER BY updated_at_utc DESC
            LIMIT 1
            """
        ).fetchone()
    if not row:
        return None
    return get_validation_job(str(row["job_id"]), db_path=db_path)


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_float(value: Any) -> float | None:
    try:
        f = float(value)
        if f != f or f == float("inf") or f == float("-inf"):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value:
        return {}
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _default_validation_metric_scope() -> dict[str, Any]:
    return {
        "probability_market": "moneyline_1x2",
        "probability_market_label": "胜平负/1X2",
        "log_loss_market": "moneyline_1x2",
        "brier_market": "moneyline_1x2",
        "asian_handicap_specific": False,
        "asian_handicap_evaluated_count": 0,
        "warning": (
            "当前 Holdout 的 Log Loss/Brier 是胜平负/1X2 概率校验，不是亚盘专属验证；"
            "亚盘准确性仍需看 asian_handicap 结算样本、CLV 和盘口结果。"
        ),
    }


def _default_asian_handicap_validation() -> dict[str, Any]:
    return {
        "market": "asian_handicap",
        "status": "missing",
        "available_count": 0,
        "evaluated_count": 0,
        "bet_count": 0,
        "hit_count": 0,
        "push_count": 0,
        "loss_count": 0,
        "profit": 0.0,
        "roi": None,
        "result_counts": {},
        "sample_gate": {
            "min_bets_for_validation": 50,
            "passed": False,
        },
        "policy": "存量 Holdout 结果没有亚盘专属验证；需要重跑新版验证后才会形成 asian_handicap 样本指标。",
    }


def _ensure_validation_metric_scope(summary: dict[str, Any]) -> dict[str, Any]:
    if not summary:
        return summary
    enriched = dict(summary)
    if not isinstance(enriched.get("metric_scope"), dict):
        enriched["metric_scope"] = _default_validation_metric_scope()
    if not isinstance(enriched.get("asian_handicap_validation"), dict):
        enriched["asian_handicap_validation"] = _default_asian_handicap_validation()

    # 存量任务没有口径字段；读取时补齐，避免前端把 1X2 验证误读成亚盘验证。
    verdict = enriched.get("verdict")
    if isinstance(verdict, dict):
        evidence = verdict.get("evidence")
        if isinstance(evidence, dict):
            verdict = dict(verdict)
            verdict["evidence"] = {
                **evidence,
                "metric_scope": enriched["metric_scope"],
                "asian_handicap_validation": enriched["asian_handicap_validation"],
            }
            enriched["verdict"] = verdict
    return enriched


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value:
        return []
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return []
    return decoded if isinstance(decoded, list) else []


def _league_result_event_type(status: str) -> str:
    normalized = str(status or "updated").strip() or "updated"
    if normalized in {"succeeded", "failed", "skipped", "cancelled"}:
        return f"league_{normalized}"
    return "league_updated"


def _league_result_event_severity(status: str) -> str:
    normalized = str(status or "")
    if normalized == "failed":
        return "error"
    if normalized in {"cancelled", "skipped"}:
        return "warning"
    return "info"


def _league_result_event_message(
    *,
    division: str,
    league: str,
    status: str,
    error: str | None,
    cache_hit: bool,
) -> str:
    name = league or division
    normalized = str(status or "")
    if normalized == "failed":
        return f"{name} failed: {error}" if error else f"{name} failed."
    if normalized == "succeeded":
        return f"{name} completed from cache." if cache_hit else f"{name} completed."
    if normalized == "cancelled":
        return f"{name} was cancelled."
    if normalized == "skipped":
        return f"{name} was skipped."
    return f"{name} updated to {normalized or 'unknown'}."


def _event_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "job_id": row.get("job_id"),
        "event_type": row.get("event_type"),
        "severity": row.get("severity"),
        "message": row.get("message"),
        "division": row.get("division"),
        "runner_id": row.get("runner_id"),
        "metadata": _json_dict(row.get("metadata_json")),
        "created_at_utc": row.get("created_at_utc"),
    }


def _job_from_rows(
    job: dict[str, Any],
    league_rows: list[dict[str, Any]],
    event_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    job_heartbeat_at = _parse_iso_datetime(job.get("runner_heartbeat_at_utc"))
    league_results = []
    for row in league_rows:
        item = {
            "job_id": row.get("job_id"),
            "division": row.get("division"),
            "league": row.get("league") or row.get("division"),
            "status": row.get("status"),
            "cache_key": row.get("cache_key"),
            "cache_hit": bool(row.get("cache_hit")),
            "result": _json_dict(row.get("result_json")),
            "error": row.get("error"),
            "started_at_utc": row.get("started_at_utc"),
            "updated_at_utc": row.get("updated_at_utc"),
            "finished_at_utc": row.get("finished_at_utc"),
            "runtime": _league_runtime_diagnostics(row, now=now, job_heartbeat_at=job_heartbeat_at),
        }
        league_results.append(item)
    total = len(league_results)
    completed = sum(1 for item in league_results if item.get("status") == "succeeded")
    failed = sum(1 for item in league_results if item.get("status") == "failed")
    running = sum(1 for item in league_results if item.get("status") == "running")
    cancelled = sum(1 for item in league_results if item.get("status") == "cancelled")
    pending = max(0, total - completed - failed - running - cancelled)
    processed = completed + failed + cancelled
    result_summary = _ensure_validation_metric_scope(_json_dict(job.get("result_summary_json")))
    if result_summary and not isinstance(result_summary.get("verdict"), dict):
        result_summary["verdict"] = build_validation_verdict(result_summary)
    failure_summary = _validation_failure_summary(job, league_results)
    execution_health = _validation_execution_health(job)
    return {
        "job_id": job.get("job_id"),
        "scope_hash": job.get("scope_hash"),
        "method": job.get("method"),
        "status": job.get("status"),
        "divisions": _json_list(job.get("divisions_json")),
        "training_seasons": _json_list(job.get("training_seasons_json")),
        "validation_seasons": _json_list(job.get("validation_seasons_json")),
        "config": _json_dict(job.get("config_json")),
        "result_summary": result_summary,
        "last_error": job.get("last_error"),
        "current_runner_id": job.get("runner_id"),
        "attempt_count": _safe_int(job.get("attempt_count")),
        "retry_count": _safe_int(job.get("retry_count")),
        "last_claim_reason": job.get("last_claim_reason"),
        "last_retry_at_utc": job.get("last_retry_at_utc"),
        "runner_heartbeat_at_utc": job.get("runner_heartbeat_at_utc"),
        "recovered_at_utc": job.get("recovered_at_utc"),
        "failure_summary": failure_summary,
        "execution_health": execution_health,
        "queue_backend": job.get("queue_backend"),
        "queue_job_id": job.get("queue_job_id"),
        "queued_at_utc": job.get("queued_at_utc"),
        "queue_status_message": job.get("queue_status_message"),
        "created_at_utc": job.get("created_at_utc"),
        "started_at_utc": job.get("started_at_utc"),
        "updated_at_utc": job.get("updated_at_utc"),
        "finished_at_utc": job.get("finished_at_utc"),
        "progress": {
            "total_leagues": total,
            "completed_leagues": completed,
            "failed_leagues": failed,
            "running_leagues": running,
            "pending_leagues": pending,
            "cancelled_leagues": cancelled,
            # 执行进度表示“已经有明确结果”的联赛，失败/取消也算处理完，
            # 否则用户会误以为任务还卡在运行中。
            "processed_leagues": processed,
            "progress_ratio": round(processed / total, 6) if total else 0.0,
            "success_ratio": round(completed / total, 6) if total else 0.0,
        },
        "league_results": league_results,
        "events": [_event_from_row(row) for row in event_rows],
    }


def _league_runtime_diagnostics(
    row: dict[str, Any],
    *,
    now: datetime,
    job_heartbeat_at: datetime | None,
) -> dict[str, Any]:
    """Expose per-league progress facts so the UI can explain long-running validation work."""
    status = str(row.get("status") or "")
    started_at = _parse_iso_datetime(row.get("started_at_utc"))
    updated_at = _parse_iso_datetime(row.get("updated_at_utc"))
    finished_at = _parse_iso_datetime(row.get("finished_at_utc"))
    is_running = status == "running"
    return {
        "state": status or "unknown",
        "is_running": is_running,
        "run_seconds": _seconds_between(finished_at or now, started_at),
        "updated_age_seconds": _seconds_between(now, updated_at),
        "heartbeat_age_seconds": _seconds_between(now, job_heartbeat_at) if is_running else None,
        "started_at_utc": row.get("started_at_utc"),
        "updated_at_utc": row.get("updated_at_utc"),
        "finished_at_utc": row.get("finished_at_utc"),
    }


def _seconds_between(later: datetime | None, earlier: datetime | None) -> int | None:
    if later is None or earlier is None:
        return None
    return max(0, int((later - earlier).total_seconds()))


def _validation_execution_health(job: dict[str, Any]) -> dict[str, Any]:
    """Turn raw timestamps into a user-facing answer to "is this job stuck?"."""
    now = datetime.now(timezone.utc)
    status = str(job.get("status") or "")
    created_at = _parse_iso_datetime(job.get("created_at_utc"))
    queued_at = _parse_iso_datetime(job.get("queued_at_utc"))
    started_at = _parse_iso_datetime(job.get("started_at_utc"))
    updated_at = _parse_iso_datetime(job.get("updated_at_utc"))
    finished_at = _parse_iso_datetime(job.get("finished_at_utc"))
    heartbeat_at = _parse_iso_datetime(job.get("runner_heartbeat_at_utc"))
    heartbeat_age = _seconds_between(now, heartbeat_at)
    updated_age = _seconds_between(now, updated_at)
    stale_after = _VALIDATION_JOB_STALE_AFTER_SECONDS
    is_running = status == "running"
    is_stale = bool(is_running and (heartbeat_age is None or heartbeat_age > stale_after))
    age_seconds = _seconds_between(now, created_at)
    queue_end = started_at or finished_at or now
    run_end = finished_at or now

    base = {
        "age_seconds": age_seconds,
        "queue_wait_seconds": _seconds_between(queue_end, queued_at),
        "run_seconds": _seconds_between(run_end, started_at),
        "updated_age_seconds": updated_age,
        "heartbeat_age_seconds": heartbeat_age,
        "stale_after_seconds": stale_after,
        "is_stale": is_stale,
    }
    if status == "completed":
        return {
            **base,
            "state": "completed",
            "severity": "ok",
            "title": "验证已完成",
            "detail": "所有可处理联赛已经形成结果。",
            "next_action": "查看验证结论和指标；需要复核时可重跑验证。",
        }
    if status == "failed":
        return {
            **base,
            "state": "failed",
            "severity": "error",
            "title": "验证失败",
            "detail": "至少一个联赛或任务阶段失败。",
            "next_action": "查看失败诊断和时间线，修复后点击重试。",
        }
    if status == "cancelled":
        return {
            **base,
            "state": "cancelled",
            "severity": "warning",
            "title": "验证已取消",
            "detail": "任务已停止执行。",
            "next_action": "需要继续时点击重试；系统会从未成功联赛继续。",
        }
    if is_stale:
        return {
            **base,
            "state": "stale",
            "severity": "error",
            "title": "Worker 心跳超时",
            "detail": f"当前 runner 超过 {stale_after} 秒没有刷新心跳，可能已经卡住或断联。",
            "next_action": "检查 worker 日志和队列健康；触发重试会从未成功联赛继续。",
        }
    if status == "running":
        return {
            **base,
            "state": "running",
            "severity": "info",
            "title": "Worker 正在执行",
            "detail": "runner 心跳正常。",
            "next_action": "继续观察联赛进度和时间线。",
        }
    if status == "pending" and queued_at is not None:
        return {
            **base,
            "state": "queued",
            "severity": "info",
            "title": "已入队等待执行",
            "detail": "任务已经交给后台队列，等待 worker 接管。",
            "next_action": "若长时间未接管，检查 ARQ worker 健康和队列积压。",
        }
    return {
        **base,
        "state": "pending",
        "severity": "warning",
        "title": "等待入队",
        "detail": "任务已创建，但尚未记录队列交接。",
        "next_action": "点击启动验证或检查 API 是否成功提交后台任务。",
    }


def _validation_failure_summary(
    job: dict[str, Any],
    league_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a compact user-facing failure summary from league execution rows."""
    failed_leagues = [
        {
            "division": item.get("division"),
            "league": item.get("league") or item.get("division"),
            "status": item.get("status"),
            "error": item.get("error"),
        }
        for item in league_results
        if item.get("status") == "failed"
    ]
    recoverable_count = sum(
        1
        for item in league_results
        if str(item.get("status") or "") in {"pending", "running", "failed", "cancelled", "skipped"}
    )
    latest_error = None
    for item in reversed(league_results):
        message = str(item.get("error") or "").strip()
        if message:
            latest_error = message
            break
    if latest_error is None:
        latest_error = str(job.get("last_error") or "").strip() or None
    diagnosis = _validation_failure_diagnosis(
        latest_error=latest_error,
        failed_count=len(failed_leagues),
        recoverable_count=recoverable_count,
        job_status=str(job.get("status") or ""),
    )
    return {
        "failed_count": len(failed_leagues),
        "recoverable": recoverable_count > 0,
        "recoverable_count": recoverable_count,
        "latest_error": latest_error,
        "failed_leagues": failed_leagues[:8],
        **diagnosis,
    }


def _validation_failure_diagnosis(
    *,
    latest_error: str | None,
    failed_count: int,
    recoverable_count: int,
    job_status: str,
) -> dict[str, Any]:
    message = str(latest_error or "").strip()
    lowered = message.lower()
    if "previous validation runner exceeded heartbeat window" in lowered or "recovered stale validation runner" in lowered:
        return {
            "category": "worker_recovered",
            "stage": "worker_heartbeat",
            "severity": "warning",
            "title": "Worker 断联后已接管续跑",
            "detail": "上一次 runner 超过心跳窗口，系统已把未完成联赛释放回队列。",
            "next_action": "无需人工处理；继续观察队列和时间线，确认后续 runner 是否完成这些联赛。",
        }
    if "timeout" in lowered or "timed out" in lowered or "exceeded" in lowered:
        return {
            "category": "timeout",
            "stage": "league_validation",
            "severity": "error",
            "title": "验证计算超时",
            "detail": "至少一个联赛在 holdout 验证阶段耗时过长。",
            "next_action": "检查数据量、缓存命中和 worker 超时配置；必要时降低 max_samples 后重试。",
        }
    if any(token in lowered for token in ("source", "unavailable", "http", "redis", "fetch", "fixture", "odds", "data")):
        return {
            "category": "data_source",
            "stage": "league_validation",
            "severity": "error",
            "title": "数据源或样本读取失败",
            "detail": "验证阶段无法稳定读取比赛、赔率或样本数据。",
            "next_action": "检查数据源健康、赔率/赛程快照和缓存；修复后点重试，已成功联赛会保留结果。",
        }
    if job_status == "cancelled" or "cancelled" in lowered:
        return {
            "category": "cancelled",
            "stage": "user_control",
            "severity": "warning",
            "title": "任务已取消",
            "detail": "验证任务被用户或控制流程取消。",
            "next_action": "需要继续验证时点击重试；系统会从未成功联赛继续。",
        }
    if failed_count > 0:
        return {
            "category": "model_validation",
            "stage": "league_validation",
            "severity": "error",
            "title": "联赛验证失败",
            "detail": "至少一个联赛在模型验证阶段失败。",
            "next_action": "查看失败联赛错误和执行时间线，修复后重试。",
        }
    if recoverable_count > 0:
        return {
            "category": "pending",
            "stage": "queue_wait",
            "severity": "info",
            "title": "仍有联赛待执行",
            "detail": "任务还有未完成联赛，但暂未发现明确失败。",
            "next_action": "等待 worker 执行；若长期不动，检查队列健康和 runner 心跳。",
        }
    return {
        "category": "none",
        "stage": "none",
        "severity": "info",
        "title": "暂无失败",
        "detail": "当前任务没有可诊断的失败。",
        "next_action": "无需处理。",
    }

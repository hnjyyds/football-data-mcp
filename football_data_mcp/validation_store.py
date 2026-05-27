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
from typing import Any

from football_data_mcp import learning_store

logger = logging.getLogger(__name__)


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
    conn.commit()


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


def _safe_float(value: Any) -> float | None:
    try:
        f = float(value)
        if f != f or f == float("inf") or f == float("-inf"):
            return None
        return f
    except (TypeError, ValueError):
        return None

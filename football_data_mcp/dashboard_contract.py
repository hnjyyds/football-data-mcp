"""Frontend-facing dashboard contract normalizer.

The dashboard JSON has accreted aliases (``calibration_band`` vs
``probability_bucket``; ``label`` vs ``title``; ``timestamp`` vs ``at_utc``;
``dongqiudi_schedule`` vs ``dongqiudi``; etc.) because the frontend grew
ahead of the backend's response shape. Rather than chase ``as any`` casts
through the React code, we apply a single normalization step here so the
frontend has one stable contract to validate against.

This module is intentionally additive: ``normalize_dashboard_snapshot``
returns a shallow copy plus normalized sub-trees. Unknown top-level keys
are preserved so callers (tests, internal tooling) that read the raw
backend response continue to work.
"""
from __future__ import annotations

from typing import Any, TypedDict


# ─── TypedDicts that the frontend mirrors via .d.ts (informational only) ────


class LastResultSummary(TypedDict, total=False):
    run_id: str | None
    saved_record_count: int | None
    saved_shadow_prediction_count: int | None
    asian_record_count: int | None
    asian_shadow_prediction_record_count: int | None
    asian_total_candidates: int | None
    asian_analyzed_count: int | None
    asian_eligible_count: int | None
    asian_returned_count: int | None
    asian_rejected_count: int | None
    asian_rejection_reasons: dict[str, int]
    parlay_record_count: int | None
    market_snapshot_sync: dict[str, Any]
    snapshot_reanalysis: dict[str, Any]
    settled_count: int | None
    shadow_settled_count: int | None


class AutoLearningState(TypedDict, total=False):
    enabled: bool
    run_count: int
    last_error: str | None
    last_started_at_utc: str | None
    last_finished_at_utc: str | None
    current_step: str | None
    consecutive_empty_cycles: int
    interval_seconds: int | None
    effective_window_minutes: int | None
    last_result_summary: LastResultSummary | None


class LatestValidation(TypedDict, total=False):
    method: str | None
    automation_readiness: str | None
    beats_market: bool
    log_loss_model: float | None
    log_loss_market: float | None
    log_loss_diff: float | None
    brier_model: float | None
    brier_market: float | None
    brier_diff: float | None
    roi: float | None
    bet_count: int | None
    evaluated_count: int | None
    created_at_utc: str | None


class CalibrationBucketRow(TypedDict, total=False):
    band: str
    market: str | None
    sample_count: int
    hit_count: int
    hit_rate: float | None
    roi: float | None
    avg_model_probability: float | None


class LearningEvent(TypedDict, total=False):
    title: str
    detail: str
    at_utc: str
    severity: str


class LineupPlayer(TypedDict, total=False):
    number: int | str | None
    name: str
    position: str | None


class LineupSide(TypedDict, total=False):
    formation: str | None
    starter_count_text: str | None
    players: list[LineupPlayer]


class Lineup(TypedDict, total=False):
    available: bool
    basis: str | None
    status_text: str | None
    home: LineupSide
    away: LineupSide
    warnings: list[str]


class OddsTrendPoint(TypedDict, total=False):
    label: str
    home: float | None
    draw: float | None
    away: float | None


class BacktestCurvePoint(TypedDict, total=False):
    label: str
    roi: float


class SourceHealthEntry(TypedDict, total=False):
    status: str | None
    error: str | None
    checked_at_utc: str | None


DashboardSourceHealth = dict[str, SourceHealthEntry]


# ─── Coercion helpers ───────────────────────────────────────────────────────


def _as_str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        return s if s else None
    return str(value)


def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return default
    return default


def _as_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return None
    return None


def _as_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("true", "1", "yes", "on"):
            return True
        if s in ("false", "0", "no", "off", ""):
            return False
    return default


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


# ─── Sub-tree normalizers ───────────────────────────────────────────────────


def normalize_auto_learning_state(raw: Any) -> AutoLearningState:
    state = _as_dict(raw)
    summary_raw = _as_dict(state.get("last_result_summary"))
    summary: LastResultSummary = {
        "run_id": _as_str_or_none(summary_raw.get("run_id")),
        "saved_record_count": _as_int_or_none(summary_raw.get("saved_record_count")),
        "saved_shadow_prediction_count": _as_int_or_none(summary_raw.get("saved_shadow_prediction_count")),
        "asian_record_count": _as_int_or_none(summary_raw.get("asian_record_count")),
        "asian_shadow_prediction_record_count": _as_int_or_none(
            summary_raw.get("asian_shadow_prediction_record_count")
        ),
        "asian_total_candidates": _as_int_or_none(summary_raw.get("asian_total_candidates")),
        "asian_analyzed_count": _as_int_or_none(summary_raw.get("asian_analyzed_count")),
        "asian_eligible_count": _as_int_or_none(summary_raw.get("asian_eligible_count")),
        "asian_returned_count": _as_int_or_none(summary_raw.get("asian_returned_count")),
        "asian_rejected_count": _as_int_or_none(summary_raw.get("asian_rejected_count")),
        "asian_rejection_reasons": _as_dict(summary_raw.get("asian_rejection_reasons")),
        "parlay_record_count": _as_int_or_none(summary_raw.get("parlay_record_count")),
        "market_snapshot_sync": _as_dict(summary_raw.get("market_snapshot_sync")),
        "snapshot_reanalysis": _as_dict(summary_raw.get("snapshot_reanalysis")),
        "settled_count": _as_int_or_none(summary_raw.get("settled_count")),
        "shadow_settled_count": _as_int_or_none(summary_raw.get("shadow_settled_count")),
    }
    return {
        "enabled": _as_bool(state.get("enabled"), default=False),
        "run_count": _as_int(state.get("run_count")),
        "last_error": _as_str_or_none(state.get("last_error")),
        "last_started_at_utc": _as_str_or_none(state.get("last_started_at_utc")),
        "last_finished_at_utc": _as_str_or_none(state.get("last_finished_at_utc")),
        "current_step": _as_str_or_none(state.get("current_step")),
        "consecutive_empty_cycles": _as_int(state.get("consecutive_empty_cycles")),
        "interval_seconds": _as_int_or_none(state.get("interval_seconds")),
        "effective_window_minutes": _as_int_or_none(state.get("effective_window_minutes")),
        "last_result_summary": summary if summary_raw else None,
    }


def normalize_latest_validation(raw: Any) -> LatestValidation | None:
    if not raw or not isinstance(raw, dict):
        return None
    return {
        "method": _as_str_or_none(raw.get("method")),
        "automation_readiness": _as_str_or_none(raw.get("automation_readiness")),
        "beats_market": _as_bool(raw.get("beats_market")),
        "log_loss_model": _as_float_or_none(raw.get("log_loss_model")),
        "log_loss_market": _as_float_or_none(raw.get("log_loss_market")),
        "log_loss_diff": _as_float_or_none(raw.get("log_loss_diff")),
        "brier_model": _as_float_or_none(raw.get("brier_model")),
        "brier_market": _as_float_or_none(raw.get("brier_market")),
        "brier_diff": _as_float_or_none(raw.get("brier_diff")),
        "roi": _as_float_or_none(raw.get("roi")),
        "bet_count": _as_int_or_none(raw.get("bet_count")),
        "evaluated_count": _as_int_or_none(raw.get("evaluated_count")),
        "created_at_utc": _as_str_or_none(raw.get("created_at_utc")),
    }


def normalize_calibration_buckets(raw: Any) -> list[CalibrationBucketRow]:
    if not isinstance(raw, list):
        return []
    out: list[CalibrationBucketRow] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        band = _as_str_or_none(item.get("calibration_band")) or _as_str_or_none(item.get("probability_bucket")) or _as_str_or_none(item.get("band"))
        if not band:
            continue
        out.append(
            {
                "band": band,
                "market": _as_str_or_none(item.get("market")),
                "sample_count": _as_int(item.get("sample_count")),
                "hit_count": _as_int(item.get("hit_count")),
                "hit_rate": _as_float_or_none(item.get("hit_rate")),
                "roi": _as_float_or_none(item.get("roi")),
                "avg_model_probability": _as_float_or_none(item.get("avg_model_probability")),
            }
        )
    return out


def normalize_learning_events(raw: Any) -> list[LearningEvent]:
    if not isinstance(raw, list):
        return []
    out: list[LearningEvent] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = _as_str_or_none(item.get("title")) or _as_str_or_none(item.get("label"))
        detail = _as_str_or_none(item.get("detail")) or _as_str_or_none(item.get("description"))
        at_utc = _as_str_or_none(item.get("at_utc")) or _as_str_or_none(item.get("timestamp"))
        if not (title or detail or at_utc):
            continue
        # Preserve all original fields (kind, severity, etc.) and overlay canonical names.
        entry: dict[str, Any] = dict(item)
        if title:
            entry["title"] = title
        if detail:
            entry["detail"] = detail
        if at_utc:
            entry["at_utc"] = at_utc
        # Drop legacy alias keys to keep the contract narrow on the canonical side
        entry.pop("label", None)
        entry.pop("description", None)
        entry.pop("timestamp", None)
        out.append(entry)  # type: ignore[arg-type]
    return out


def _normalize_lineup_side(raw: Any) -> LineupSide:
    side = _as_dict(raw)
    players: list[LineupPlayer] = []
    for p in side.get("players") or []:
        if not isinstance(p, dict):
            continue
        players.append(
            {
                "number": p.get("number"),
                "name": _as_str_or_none(p.get("name")) or "",
                "position": _as_str_or_none(p.get("position")),
            }
        )
    return {
        "formation": _as_str_or_none(side.get("formation")),
        "starter_count_text": _as_str_or_none(side.get("starter_count_text")) or _as_str_or_none(side.get("starterCountText")),
        "players": players,
    }


def normalize_lineup(raw: Any) -> Lineup | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return None
    warnings_raw = raw.get("warnings")
    warnings = [str(w) for w in warnings_raw] if isinstance(warnings_raw, list) else []
    return {
        "available": _as_bool(raw.get("available")),
        "basis": _as_str_or_none(raw.get("basis")),
        "status_text": _as_str_or_none(raw.get("status_text")) or _as_str_or_none(raw.get("statusText")),
        "home": _normalize_lineup_side(raw.get("home")),
        "away": _normalize_lineup_side(raw.get("away")),
        "warnings": warnings,
    }


def normalize_odds_trend_points(raw: Any) -> list[OddsTrendPoint]:
    if not isinstance(raw, list):
        return []
    out: list[OddsTrendPoint] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = _as_str_or_none(item.get("label")) or _as_str_or_none(item.get("x"))
        if not label:
            continue
        entry: OddsTrendPoint = {"label": label}
        for key in ("home", "draw", "away"):
            v = _as_float_or_none(item.get(key))
            if v is not None:
                entry[key] = v  # type: ignore[literal-required]
        out.append(entry)
    return out


def normalize_backtest_curve(raw: Any) -> dict[str, Any]:
    """Preserve the existing backtest_curve shape, and append canonical
    ``label``/``roi`` fields onto each point so the chart code can rely on them
    without falling back to ``x`` / ``index`` / ``y`` aliases.
    """
    if not isinstance(raw, dict):
        return {"points": []}
    out: dict[str, Any] = dict(raw)
    points_raw = raw.get("points")
    if not isinstance(points_raw, list):
        out["points"] = []
        return out
    normalized_points: list[dict[str, Any]] = []
    for item in points_raw:
        if not isinstance(item, dict):
            continue
        # Keep all original fields (index, profit_units, cumulative_profit, …)
        entry: dict[str, Any] = dict(item)
        label = _as_str_or_none(item.get("label"))
        if label is None:
            x = item.get("x")
            if x is None:
                x = item.get("index")
            if x is not None:
                label = str(x)
        if label is not None:
            entry["label"] = label
        # Canonical roi field: prefer roi, fall back to y
        if "roi" not in item or item.get("roi") is None:
            y = _as_float_or_none(item.get("y"))
            if y is not None:
                entry["roi"] = y
        normalized_points.append(entry)
    out["points"] = normalized_points
    return out


_SOURCE_HEALTH_ALIASES = {
    "football_data_co_uk": "football_data",
    "dongqiudi_schedule": "dongqiudi",
    "odds_api": "the_odds_api",
}


def normalize_source_health(raw_root: dict[str, Any]) -> DashboardSourceHealth:
    health = raw_root.get("source_health")
    if not isinstance(health, dict) or not health:
        decision = raw_root.get("decision_audit")
        if isinstance(decision, dict):
            audit = decision.get("source_audit")
            if isinstance(audit, dict):
                health = audit
    if not isinstance(health, dict):
        return {}
    out: DashboardSourceHealth = {}
    for key, value in health.items():
        if not isinstance(value, dict):
            continue
        canonical = _SOURCE_HEALTH_ALIASES.get(key, key)
        entry: SourceHealthEntry = {
            "status": _as_str_or_none(value.get("status")),
            "error": _as_str_or_none(value.get("error")),
            "checked_at_utc": _as_str_or_none(value.get("checked_at_utc")),
        }
        # Preserve any other vendor-specific fields the dashboard might surface
        for k, v in value.items():
            if k not in entry:
                entry[k] = v  # type: ignore[literal-required]
        out[canonical] = entry
    return out


# ─── Top-level entry point ──────────────────────────────────────────────────


def normalize_dashboard_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *snapshot* with frontend-facing fields normalized.

    Unknown keys are preserved untouched so legacy callers stay compatible.
    """
    if not isinstance(snapshot, dict):
        raise TypeError("snapshot must be a dict")
    out = dict(snapshot)
    out["auto_learning_state"] = normalize_auto_learning_state(snapshot.get("auto_learning_state"))
    out["latest_validation"] = normalize_latest_validation(snapshot.get("latest_validation"))
    out["buckets"] = normalize_calibration_buckets(snapshot.get("buckets"))
    out["learning_events"] = normalize_learning_events(snapshot.get("learning_events"))
    out["backtest_curve"] = normalize_backtest_curve(snapshot.get("backtest_curve"))
    out["source_health"] = normalize_source_health(snapshot)
    return out

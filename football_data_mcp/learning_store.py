from __future__ import annotations

import json
import hashlib
import math
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


DEFAULT_LEARNING_DB = "/tmp/football_data_mcp_learning.sqlite3"
MAX_LEARNING_SAMPLE_MINUTES_TO_KICKOFF = 10
DEFAULT_BALANCED_STRATEGY = {
    "min_live_sample_count": 20,
    "prior_strength": 20.0,
    "min_calibrated_probability": 0.58,
    "min_decimal_odds": 1.65,
    "max_decimal_odds": 2.05,
    "min_value_edge": 0.02,
}


def learning_db_path() -> str:
    return os.getenv("FOOTBALL_DATA_LEARNING_DB", DEFAULT_LEARNING_DB)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or learning_db_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendation_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_key TEXT,
            run_id TEXT NOT NULL,
            tool TEXT NOT NULL,
            mode TEXT NOT NULL,
            target_market TEXT NOT NULL,
            match_id TEXT,
            match_num_str TEXT,
            league TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            kickoff_utc TEXT,
            kickoff_utc_plus_8 TEXT,
            market TEXT NOT NULL,
            selection TEXT NOT NULL,
            selection_key TEXT,
            line REAL,
            decimal_odds REAL,
            model_probability REAL,
            calibrated_probability REAL,
            market_probability REAL,
            edge REAL,
            expected_multiplier REAL,
            recommendation TEXT,
            stake_level TEXT,
            risk_flags_json TEXT NOT NULL,
            caution_flags_json TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            settlement_status TEXT NOT NULL DEFAULT 'open',
            home_score INTEGER,
            away_score INTEGER,
            hit INTEGER,
            payout_multiplier REAL,
            profit_units REAL,
            settled_at_utc TEXT,
            created_at_utc TEXT NOT NULL
        )
        """
    )
    _ensure_column(conn, "recommendation_records", "record_key", "TEXT")
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_recommendation_records_match
        ON recommendation_records(home_team, away_team, kickoff_utc_plus_8, settlement_status)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_recommendation_records_match_id
        ON recommendation_records(match_id, settlement_status)
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_recommendation_records_record_key
        ON recommendation_records(record_key)
        """
    )
    _backfill_record_keys(conn)
    conn.execute(
        """
        UPDATE recommendation_records
        SET settlement_status = 'tracked_only'
        WHERE market = 'parlay' AND settlement_status = 'open'
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_recommendation_records_run
        ON recommendation_records(run_id, tool, market)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS calibration_buckets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market TEXT NOT NULL,
            league_bucket TEXT NOT NULL,
            line_bucket TEXT NOT NULL,
            odds_bucket TEXT NOT NULL,
            probability_bucket TEXT NOT NULL,
            sample_count INTEGER NOT NULL,
            hit_count INTEGER NOT NULL,
            hit_rate REAL,
            avg_model_probability REAL,
            avg_edge REAL,
            roi REAL,
            updated_at_utc TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            UNIQUE(market, league_bucket, line_bucket, odds_bucket, probability_bucket)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS strategy_state (
            key TEXT PRIMARY KEY,
            market TEXT NOT NULL,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            active INTEGER NOT NULL,
            sample_count INTEGER NOT NULL,
            hit_rate REAL,
            roi REAL,
            avg_model_probability REAL,
            min_live_sample_count INTEGER NOT NULL,
            prior_strength REAL NOT NULL,
            min_calibrated_probability REAL NOT NULL,
            min_decimal_odds REAL NOT NULL,
            max_decimal_odds REAL NOT NULL,
            min_value_edge REAL NOT NULL,
            updated_at_utc TEXT NOT NULL,
            raw_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS shadow_prediction_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shadow_key TEXT,
            run_id TEXT NOT NULL,
            tool TEXT NOT NULL,
            mode TEXT NOT NULL,
            target_market TEXT NOT NULL,
            decision TEXT NOT NULL,
            rejection_reason TEXT,
            match_id TEXT,
            match_num_str TEXT,
            league TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            kickoff_utc TEXT,
            kickoff_utc_plus_8 TEXT,
            market TEXT,
            selection TEXT,
            selection_key TEXT,
            line REAL,
            decimal_odds REAL,
            model_probability REAL,
            calibrated_probability REAL,
            market_probability REAL,
            edge REAL,
            expected_multiplier REAL,
            recommendation TEXT,
            stake_level TEXT,
            quality_json TEXT NOT NULL,
            thresholds_json TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            settlement_status TEXT NOT NULL DEFAULT 'open',
            home_score INTEGER,
            away_score INTEGER,
            hit INTEGER,
            payout_multiplier REAL,
            profit_units REAL,
            settled_at_utc TEXT,
            created_at_utc TEXT NOT NULL
        )
        """
    )
    _ensure_column(conn, "shadow_prediction_records", "shadow_key", "TEXT")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_shadow_prediction_records_key
        ON shadow_prediction_records(shadow_key)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_shadow_prediction_records_match
        ON shadow_prediction_records(match_id, settlement_status)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_shadow_prediction_records_run
        ON shadow_prediction_records(run_id, decision, market)
        """
    )
    conn.commit()


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_type: str) -> None:
    if column_name not in _table_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def _backfill_record_keys(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT * FROM recommendation_records
        WHERE record_key IS NULL OR record_key = ''
        ORDER BY id ASC
        """
    ).fetchall()
    for row in rows:
        record = dict(row)
        key = recommendation_record_key(record)
        existing = conn.execute(
            "SELECT id FROM recommendation_records WHERE record_key = ? LIMIT 1",
            (key,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE recommendation_records
                SET record_key = ?, settlement_status = 'duplicate_ignored'
                WHERE id = ?
                """,
                (f"{key}:duplicate:{record['id']}", record["id"]),
            )
        else:
            conn.execute(
                "UPDATE recommendation_records SET record_key = ? WHERE id = ?",
                (key, record["id"]),
            )


def make_run_id(prefix: str = "cycle") -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def round_metric(value: float | None, ndigits: int = 6) -> float | None:
    return round(value, ndigits) if value is not None else None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def _normalize_text(value: str) -> str:
    value = (value or "").lower()
    value = re.sub(r"\b(fc|cf|afc|sc|u23|u21)\b", " ", value)
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _team_matches(left: str, right: str) -> bool:
    left_norm = _normalize_text(left)
    right_norm = _normalize_text(right)
    if not left_norm or not right_norm:
        return False
    return left_norm == right_norm or left_norm in right_norm or right_norm in left_norm


def _key_part(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return _normalize_text(str(value))


def _key_line(value: Any) -> str:
    parsed = parse_float(value)
    return "line:none" if parsed is None else f"line:{parsed:+.3f}"


def recommendation_record_key(item: dict[str, Any]) -> str:
    match = item.get("match") or {}
    best = item.get("best_candidate") or item
    advice = item.get("final_execution_advice") or item.get("final_decision") or {}
    match_id = str(match.get("match_id") or item.get("match_id") or "").strip()
    kickoff = str(match.get("kickoff_utc_plus_8") or item.get("kickoff_utc_plus_8") or match.get("kickoff_utc") or item.get("kickoff_utc") or "")
    league = str(match.get("league") or item.get("league") or "")
    home_team = str(match.get("home_team") or item.get("home_team") or "")
    away_team = str(match.get("away_team") or item.get("away_team") or "")
    market = str(best.get("market") or advice.get("market") or item.get("market") or "")
    selection_key = str(best.get("selection_key") or item.get("selection_key") or "")
    selection = str(best.get("selection") or advice.get("selection") or item.get("selection") or "")
    line = best.get("line") if best.get("line") is not None else item.get("line")
    match_identity = match_id or "|".join(_key_part(part) for part in (league, home_team, away_team, kickoff))
    selection_identity = selection if market == "parlay" else (selection_key or selection)
    parts = [
        "recommendation:v1",
        _key_part(item.get("tool") or ""),
        _key_part(item.get("target_market") or market),
        _key_part(match_identity),
        _key_part(market),
        _key_part(selection_identity),
        _key_line(line),
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"rec:{digest}"


def _record_tuple(item: dict[str, Any]) -> tuple[Any, ...]:
    match = item.get("match") or {}
    best = item.get("best_candidate") or item
    confidence = item.get("selection_confidence") or {}
    advice = item.get("final_execution_advice") or item.get("final_decision") or {}
    raw = item.get("raw") if "raw" in item else item
    created_at = str(item.get("created_at_utc") or now_utc_iso())
    market = str(best.get("market") or advice.get("market") or item.get("market") or "")
    settlement_status = str(item.get("settlement_status") or ("tracked_only" if market == "parlay" else "open"))
    return (
        str(item.get("record_key") or recommendation_record_key(item)),
        str(item.get("run_id") or ""),
        str(item.get("tool") or ""),
        str(item.get("mode") or ""),
        str(item.get("target_market") or best.get("market") or ""),
        str(match.get("match_id") or item.get("match_id") or ""),
        str(match.get("match_num_str") or item.get("match_num_str") or ""),
        str(match.get("league") or item.get("league") or ""),
        str(match.get("home_team") or item.get("home_team") or ""),
        str(match.get("away_team") or item.get("away_team") or ""),
        str(match.get("kickoff_utc") or item.get("kickoff_utc") or ""),
        str(match.get("kickoff_utc_plus_8") or item.get("kickoff_utc_plus_8") or ""),
        market,
        str(best.get("selection") or advice.get("selection") or item.get("selection") or ""),
        str(best.get("selection_key") or item.get("selection_key") or ""),
        parse_float(best.get("line") if best.get("line") is not None else item.get("line")),
        parse_float(best.get("decimal_odds") if best.get("decimal_odds") is not None else item.get("decimal_odds")),
        parse_float(best.get("model_probability") if best.get("model_probability") is not None else item.get("model_probability")),
        parse_float(
            best.get("calibrated_probability")
            if best.get("calibrated_probability") is not None
            else confidence.get("calibrated_probability")
        ),
        parse_float(best.get("market_probability") if best.get("market_probability") is not None else item.get("market_probability")),
        parse_float(best.get("edge") if best.get("edge") is not None else item.get("edge")),
        parse_float(best.get("expected_multiplier") if best.get("expected_multiplier") is not None else item.get("expected_multiplier")),
        str(best.get("recommendation") or advice.get("raw_mcp_recommendation") or item.get("recommendation") or ""),
        str(best.get("stake_level") or advice.get("stake_level") or item.get("stake_level") or ""),
        _json(item.get("risk_flags") or (item.get("risk_overlay") or {}).get("risk_flags") or []),
        _json(item.get("caution_flags") or []),
        _json(raw),
        settlement_status,
        created_at,
    )


def save_recommendation_records(records: list[dict[str, Any]], *, db_path: str | None = None) -> int:
    if not records:
        return 0
    with _connect(db_path) as conn:
        ensure_schema(conn)
        before = conn.total_changes
        conn.executemany(
            """
            INSERT INTO recommendation_records (
                record_key, run_id, tool, mode, target_market, match_id, match_num_str, league,
                home_team, away_team, kickoff_utc, kickoff_utc_plus_8, market, selection,
                selection_key, line, decimal_odds, model_probability, calibrated_probability,
                market_probability, edge, expected_multiplier, recommendation, stake_level,
                risk_flags_json, caution_flags_json, raw_json, settlement_status, created_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(record_key) DO UPDATE SET
                run_id = excluded.run_id,
                tool = excluded.tool,
                mode = excluded.mode,
                target_market = excluded.target_market,
                match_id = excluded.match_id,
                match_num_str = excluded.match_num_str,
                league = excluded.league,
                home_team = excluded.home_team,
                away_team = excluded.away_team,
                kickoff_utc = excluded.kickoff_utc,
                kickoff_utc_plus_8 = excluded.kickoff_utc_plus_8,
                market = excluded.market,
                selection = excluded.selection,
                selection_key = excluded.selection_key,
                line = excluded.line,
                decimal_odds = excluded.decimal_odds,
                model_probability = excluded.model_probability,
                calibrated_probability = excluded.calibrated_probability,
                market_probability = excluded.market_probability,
                edge = excluded.edge,
                expected_multiplier = excluded.expected_multiplier,
                recommendation = excluded.recommendation,
                stake_level = excluded.stake_level,
                risk_flags_json = excluded.risk_flags_json,
                caution_flags_json = excluded.caution_flags_json,
                raw_json = excluded.raw_json,
                settlement_status = excluded.settlement_status,
                created_at_utc = excluded.created_at_utc
            WHERE recommendation_records.settlement_status = 'open'
              AND excluded.settlement_status = 'open'
            """,
            [_record_tuple(record) for record in records],
        )
        inserted_count = conn.total_changes - before
        conn.commit()
    return inserted_count


def update_open_recommendation_record(record_id: int | str, item: dict[str, Any], *, db_path: str | None = None) -> int:
    """Replace one still-open recommendation row with a freshly reanalyzed prediction."""
    values = _record_tuple(item)
    with _connect(db_path) as conn:
        ensure_schema(conn)
        before = conn.total_changes
        conn.execute(
            """
            UPDATE recommendation_records
            SET
                record_key = ?,
                run_id = ?,
                tool = ?,
                mode = ?,
                target_market = ?,
                match_id = ?,
                match_num_str = ?,
                league = ?,
                home_team = ?,
                away_team = ?,
                kickoff_utc = ?,
                kickoff_utc_plus_8 = ?,
                market = ?,
                selection = ?,
                selection_key = ?,
                line = ?,
                decimal_odds = ?,
                model_probability = ?,
                calibrated_probability = ?,
                market_probability = ?,
                edge = ?,
                expected_multiplier = ?,
                recommendation = ?,
                stake_level = ?,
                risk_flags_json = ?,
                caution_flags_json = ?,
                raw_json = ?,
                settlement_status = ?,
                created_at_utc = ?
            WHERE id = ?
              AND settlement_status = 'open'
            """,
            (*values, str(record_id)),
        )
        updated_count = conn.total_changes - before
        conn.commit()
    return updated_count


def _decode_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    for key in ("risk_flags_json", "caution_flags_json", "raw_json"):
        decoded_key = key.replace("_json", "")
        try:
            fallback = "{}" if key == "raw_json" else "[]"
            item[decoded_key] = json.loads(item.get(key) or fallback)
        except json.JSONDecodeError:
            item[decoded_key] = [] if key != "raw_json" else {}
    return item


def list_recommendation_records(
    *,
    db_path: str | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    with _connect(db_path) as conn:
        ensure_schema(conn)
        if status:
            rows = conn.execute(
                """
                SELECT * FROM recommendation_records
                WHERE settlement_status = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (status, int(limit or 200)),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM recommendation_records
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit or 200),),
            ).fetchall()
    return [_decode_row(row) for row in rows]


def get_recommendation_record(record_id: int | str, *, db_path: str | None = None) -> dict[str, Any] | None:
    with _connect(db_path) as conn:
        ensure_schema(conn)
        row = conn.execute(
            """
            SELECT * FROM recommendation_records
            WHERE id = ?
            LIMIT 1
            """,
            (str(record_id),),
        ).fetchone()
    return _decode_row(row) if row else None


def _split_line_payout(margin_after_line: float, decimal_odds: float) -> float:
    if margin_after_line > 1e-9:
        return decimal_odds
    if margin_after_line < -1e-9:
        return 0.0
    return 1.0


def _split_quarter_line(line: float) -> list[float]:
    doubled = line * 2
    if abs(doubled - round(doubled)) < 1e-9:
        return [line]
    lower = math.floor(line * 2) / 2
    upper = math.ceil(line * 2) / 2
    return [lower, upper]


def _asian_payout_multiplier(*, selected_margin: float, line: float, decimal_odds: float) -> float:
    payouts = [_split_line_payout(selected_margin + split_line, decimal_odds) for split_line in _split_quarter_line(line)]
    return round_metric(sum(payouts) / len(payouts), 6) or 0.0


def _three_way_payout(selection_key: str, home_score: int, away_score: int, decimal_odds: float) -> float:
    if home_score > away_score:
        actual = "home"
    elif home_score < away_score:
        actual = "away"
    else:
        actual = "draw"
    return decimal_odds if selection_key == actual else 0.0


def _hhad_payout(selection_key: str, line: float, home_score: int, away_score: int, decimal_odds: float) -> float:
    adjusted = home_score + line - away_score
    if adjusted > 1e-9:
        actual = "home"
    elif adjusted < -1e-9:
        actual = "away"
    else:
        actual = "draw"
    return decimal_odds if selection_key == actual else 0.0


def settle_record(record: dict[str, Any], *, home_score: int, away_score: int) -> dict[str, Any]:
    decimal_odds = parse_float(record.get("decimal_odds")) or 0.0
    line = parse_float(record.get("line"))
    market = str(record.get("market") or "")
    selection_key = str(record.get("selection_key") or "")
    payout = 0.0
    if decimal_odds <= 1:
        payout = 0.0
    elif market == "1x2":
        payout = _three_way_payout(selection_key, home_score, away_score, decimal_odds)
    elif market == "jingcai_hhad" and line is not None:
        payout = _hhad_payout(selection_key, line, home_score, away_score, decimal_odds)
    elif market == "asian_handicap" and line is not None:
        if selection_key == "home_cover":
            margin = home_score - away_score
        else:
            margin = away_score - home_score
        payout = _asian_payout_multiplier(selected_margin=margin, line=line, decimal_odds=decimal_odds)
    else:
        return {
            "settlement_status": "unsupported_market",
            "home_score": home_score,
            "away_score": away_score,
            "hit": None,
            "payout_multiplier": None,
            "profit_units": None,
        }
    profit = round_metric(payout - 1.0, 6)
    return {
        "settlement_status": "settled",
        "home_score": home_score,
        "away_score": away_score,
        "hit": 1 if payout > 1 else 0,
        "payout_multiplier": round_metric(payout, 6),
        "profit_units": profit,
    }


def _has_score(result: dict[str, Any]) -> bool:
    return result.get("home_score") is not None and result.get("away_score") is not None


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _kickoff_close_enough(record: dict[str, Any], result: dict[str, Any]) -> bool:
    record_time = _parse_iso_datetime(record.get("kickoff_utc_plus_8") or record.get("kickoff_utc"))
    result_time = _parse_iso_datetime(result.get("kickoff_utc_plus_8") or result.get("kickoff_utc"))
    if not record_time or not result_time:
        return True
    if record_time.date() == result_time.date():
        return True
    return abs(record_time - result_time) <= timedelta(hours=18)


def _learning_minutes_to_kickoff(item: dict[str, Any], *, default_as_of: Any = None) -> float | None:
    match = item.get("match") if isinstance(item.get("match"), dict) else {}
    time_window = match.get("time_window") if isinstance(match.get("time_window"), dict) else {}
    if not time_window and isinstance(item.get("time_window"), dict):
        time_window = item.get("time_window") or {}
    as_of = _parse_iso_datetime(time_window.get("as_of") or item.get("created_at_utc") or default_as_of)
    kickoff = _parse_iso_datetime(
        time_window.get("kickoff")
        or match.get("kickoff_utc_plus_8")
        or match.get("kickoff_utc")
        or item.get("kickoff_utc_plus_8")
        or item.get("kickoff_utc")
    )
    if not as_of or not kickoff:
        return None
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)
    return (kickoff.astimezone(timezone.utc) - as_of.astimezone(timezone.utc)).total_seconds() / 60


def _is_near_kickoff_learning_sample(item: dict[str, Any], *, default_as_of: Any = None) -> bool:
    minutes = _learning_minutes_to_kickoff(item, default_as_of=default_as_of)
    if minutes is None:
        return True
    return 0 <= minutes <= MAX_LEARNING_SAMPLE_MINUTES_TO_KICKOFF


def _find_matching_result(record: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any] | None:
    record_match_id = str(record.get("match_id") or "").strip()
    if record_match_id:
        for result in results:
            if str(result.get("match_id") or "").strip() == record_match_id and _has_score(result):
                return result

    for result in results:
        if not _has_score(result):
            continue
        result_match_id = str(result.get("match_id") or "").strip()
        if record_match_id and result_match_id and result_match_id != record_match_id:
            continue
        if result.get("home_team") and result.get("away_team"):
            if not _team_matches(str(record.get("home_team") or ""), str(result.get("home_team") or "")):
                continue
            if not _team_matches(str(record.get("away_team") or ""), str(result.get("away_team") or "")):
                continue
            if not _kickoff_close_enough(record, result):
                continue
        elif result.get("match_id") and str(result.get("match_id")) != str(record.get("match_id") or ""):
            continue
        else:
            continue
        return result
    return None


def settle_recommendations(results: list[dict[str, Any]], *, db_path: str | None = None) -> dict[str, Any]:
    settled_count = 0
    skipped_count = 0
    unsupported_count = 0
    settled_rows: list[dict[str, Any]] = []
    with _connect(db_path) as conn:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT * FROM recommendation_records
            WHERE settlement_status = 'open'
            ORDER BY id ASC
            """
        ).fetchall()
        for row in rows:
            record = dict(row)
            result = _find_matching_result(record, results)
            if not result:
                skipped_count += 1
                continue
            settlement = settle_record(
                record,
                home_score=int(result["home_score"]),
                away_score=int(result["away_score"]),
            )
            if settlement["settlement_status"] == "unsupported_market":
                unsupported_count += 1
            else:
                settled_count += 1
            conn.execute(
                """
                UPDATE recommendation_records
                SET settlement_status = ?, home_score = ?, away_score = ?, hit = ?,
                    payout_multiplier = ?, profit_units = ?, settled_at_utc = ?
                WHERE id = ?
                """,
                (
                    settlement["settlement_status"],
                    settlement["home_score"],
                    settlement["away_score"],
                    settlement["hit"],
                    settlement["payout_multiplier"],
                    settlement["profit_units"],
                    now_utc_iso(),
                    record["id"],
                ),
            )
            settled_rows.append({**record, **settlement})
        conn.commit()
    return {
        "status": "ok",
        "settled_count": settled_count,
        "skipped_count": skipped_count,
        "unsupported_count": unsupported_count,
        "settled_records": settled_rows,
    }


def shadow_prediction_record_key(item: dict[str, Any]) -> str:
    match = item.get("match") or {}
    best = item.get("best_candidate") or item
    run_id = str(item.get("run_id") or "")
    match_id = str(match.get("match_id") or item.get("match_id") or "").strip()
    kickoff = str(match.get("kickoff_utc_plus_8") or item.get("kickoff_utc_plus_8") or match.get("kickoff_utc") or item.get("kickoff_utc") or "")
    league = str(match.get("league") or item.get("league") or "")
    home_team = str(match.get("home_team") or item.get("home_team") or "")
    away_team = str(match.get("away_team") or item.get("away_team") or "")
    market = str(best.get("market") or item.get("market") or "")
    selection_key = str(best.get("selection_key") or item.get("selection_key") or "")
    selection = str(best.get("selection") or item.get("selection") or "")
    line = best.get("line") if best.get("line") is not None else item.get("line")
    decimal_odds = best.get("decimal_odds") if best.get("decimal_odds") is not None else item.get("decimal_odds")
    probability = (
        best.get("calibrated_probability")
        if best.get("calibrated_probability") is not None
        else best.get("model_probability") if best.get("model_probability") is not None else item.get("model_probability")
    )
    match_identity = match_id or "|".join(_key_part(part) for part in (league, home_team, away_team, kickoff))
    parts = [
        "shadow:v1",
        _key_part(run_id),
        _key_part(item.get("tool") or ""),
        _key_part(item.get("mode") or ""),
        _key_part(item.get("target_market") or ""),
        _key_part(item.get("decision") or ""),
        _key_part(match_identity),
        _key_part(market),
        _key_part(selection_key or selection),
        _key_line(line),
        _key_part(decimal_odds),
        _key_part(probability),
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"shadow:{digest}"


def _shadow_settlement_status(item: dict[str, Any], best: dict[str, Any]) -> str:
    explicit = str(item.get("settlement_status") or "").strip()
    if explicit:
        return explicit
    market = str(best.get("market") or item.get("market") or "")
    selection_key = str(best.get("selection_key") or item.get("selection_key") or "")
    decimal_odds = parse_float(best.get("decimal_odds") if best.get("decimal_odds") is not None else item.get("decimal_odds"))
    if market and selection_key and decimal_odds is not None:
        return "open"
    return "tracked_only"


def _shadow_record_tuple(item: dict[str, Any]) -> tuple[Any, ...]:
    match = item.get("match") or {}
    best = item.get("best_candidate") or item
    confidence = item.get("selection_confidence") or {}
    created_at = str(item.get("created_at_utc") or now_utc_iso())
    raw = item.get("raw") if "raw" in item else item
    return (
        str(item.get("shadow_key") or shadow_prediction_record_key(item)),
        str(item.get("run_id") or ""),
        str(item.get("tool") or ""),
        str(item.get("mode") or ""),
        str(item.get("target_market") or best.get("market") or ""),
        str(item.get("decision") or "observed"),
        str(item.get("rejection_reason") or ""),
        str(match.get("match_id") or item.get("match_id") or ""),
        str(match.get("match_num_str") or item.get("match_num_str") or ""),
        str(match.get("league") or item.get("league") or ""),
        str(match.get("home_team") or item.get("home_team") or ""),
        str(match.get("away_team") or item.get("away_team") or ""),
        str(match.get("kickoff_utc") or item.get("kickoff_utc") or ""),
        str(match.get("kickoff_utc_plus_8") or item.get("kickoff_utc_plus_8") or ""),
        str(best.get("market") or item.get("market") or ""),
        str(best.get("selection") or item.get("selection") or ""),
        str(best.get("selection_key") or item.get("selection_key") or ""),
        parse_float(best.get("line") if best.get("line") is not None else item.get("line")),
        parse_float(best.get("decimal_odds") if best.get("decimal_odds") is not None else item.get("decimal_odds")),
        parse_float(best.get("model_probability") if best.get("model_probability") is not None else item.get("model_probability")),
        parse_float(
            best.get("calibrated_probability")
            if best.get("calibrated_probability") is not None
            else confidence.get("calibrated_probability")
            if confidence.get("calibrated_probability") is not None
            else item.get("calibrated_probability")
        ),
        parse_float(best.get("market_probability") if best.get("market_probability") is not None else item.get("market_probability")),
        parse_float(best.get("edge") if best.get("edge") is not None else item.get("edge")),
        parse_float(best.get("expected_multiplier") if best.get("expected_multiplier") is not None else item.get("expected_multiplier")),
        str(best.get("recommendation") or item.get("recommendation") or ""),
        str(best.get("stake_level") or item.get("stake_level") or ""),
        _json(item.get("quality") or {}),
        _json(item.get("thresholds") or {}),
        _json(raw),
        _shadow_settlement_status(item, best),
        created_at,
    )


def save_shadow_prediction_records(records: list[dict[str, Any]], *, db_path: str | None = None) -> int:
    if not records:
        return 0
    with _connect(db_path) as conn:
        ensure_schema(conn)
        before = conn.total_changes
        conn.executemany(
            """
            INSERT OR IGNORE INTO shadow_prediction_records (
                shadow_key, run_id, tool, mode, target_market, decision, rejection_reason,
                match_id, match_num_str, league, home_team, away_team, kickoff_utc,
                kickoff_utc_plus_8, market, selection, selection_key, line, decimal_odds,
                model_probability, calibrated_probability, market_probability, edge,
                expected_multiplier, recommendation, stake_level, quality_json,
                thresholds_json, raw_json, settlement_status, created_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [_shadow_record_tuple(record) for record in records],
        )
        inserted_count = conn.total_changes - before
        conn.commit()
    return inserted_count


def _decode_shadow_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    for key in ("quality_json", "thresholds_json", "raw_json"):
        decoded_key = key.replace("_json", "")
        try:
            item[decoded_key] = json.loads(item.get(key) or "{}")
        except json.JSONDecodeError:
            item[decoded_key] = {}
    return item


def list_shadow_prediction_records(
    *,
    db_path: str | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    with _connect(db_path) as conn:
        ensure_schema(conn)
        if status:
            rows = conn.execute(
                """
                SELECT * FROM shadow_prediction_records
                WHERE settlement_status = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (status, int(limit or 200)),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM shadow_prediction_records
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit or 200),),
            ).fetchall()
    return [_decode_shadow_row(row) for row in rows]


def update_open_match_states(states: list[dict[str, Any]], *, db_path: str | None = None) -> dict[str, Any]:
    usable_states = {
        str(state.get("match_id") or "").strip(): state
        for state in states
        if isinstance(state, dict) and str(state.get("match_id") or "").strip()
    }
    if not usable_states:
        return {
            "status": "ok",
            "updated_count": 0,
            "recommendation_count": 0,
            "shadow_prediction_count": 0,
        }

    placeholders = ",".join("?" for _ in usable_states)
    recommendation_count = 0
    shadow_prediction_count = 0
    with _connect(db_path) as conn:
        ensure_schema(conn)
        for table, counter_name in (
            ("recommendation_records", "recommendation_count"),
            ("shadow_prediction_records", "shadow_prediction_count"),
        ):
            rows = conn.execute(
                f"""
                SELECT id, match_id, raw_json
                FROM {table}
                WHERE settlement_status = 'open'
                  AND match_id IN ({placeholders})
                """,
                tuple(usable_states.keys()),
            ).fetchall()
            for row in rows:
                match_id = str(row["match_id"] or "").strip()
                state = usable_states.get(match_id)
                if not state:
                    continue
                try:
                    raw = json.loads(row["raw_json"] or "{}")
                except json.JSONDecodeError:
                    raw = {}
                if not isinstance(raw, dict):
                    raw = {}
                raw["match_state"] = state
                conn.execute(
                    f"UPDATE {table} SET raw_json = ? WHERE id = ?",
                    (_json(raw), row["id"]),
                )
                if counter_name == "recommendation_count":
                    recommendation_count += 1
                else:
                    shadow_prediction_count += 1
        conn.commit()

    return {
        "status": "ok",
        "updated_count": recommendation_count + shadow_prediction_count,
        "recommendation_count": recommendation_count,
        "shadow_prediction_count": shadow_prediction_count,
    }


def settle_shadow_predictions(results: list[dict[str, Any]], *, db_path: str | None = None) -> dict[str, Any]:
    settled_count = 0
    skipped_count = 0
    unsupported_count = 0
    settled_rows: list[dict[str, Any]] = []
    with _connect(db_path) as conn:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT * FROM shadow_prediction_records
            WHERE settlement_status = 'open'
            ORDER BY id ASC
            """
        ).fetchall()
        for row in rows:
            record = dict(row)
            result = _find_matching_result(record, results)
            if not result:
                skipped_count += 1
                continue
            settlement = settle_record(
                record,
                home_score=int(result["home_score"]),
                away_score=int(result["away_score"]),
            )
            if settlement["settlement_status"] == "unsupported_market":
                unsupported_count += 1
            else:
                settled_count += 1
            conn.execute(
                """
                UPDATE shadow_prediction_records
                SET settlement_status = ?, home_score = ?, away_score = ?, hit = ?,
                    payout_multiplier = ?, profit_units = ?, settled_at_utc = ?
                WHERE id = ?
                """,
                (
                    settlement["settlement_status"],
                    settlement["home_score"],
                    settlement["away_score"],
                    settlement["hit"],
                    settlement["payout_multiplier"],
                    settlement["profit_units"],
                    now_utc_iso(),
                    record["id"],
                ),
            )
            settled_rows.append({**record, **settlement})
        conn.commit()
    return {
        "status": "ok",
        "settled_count": settled_count,
        "skipped_count": skipped_count,
        "unsupported_count": unsupported_count,
        "settled_records": settled_rows,
    }


def _shadow_metric_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    total_count = len(records)
    settled = [record for record in records if record.get("settlement_status") == "settled"]
    profits = [parse_float(record.get("profit_units")) for record in settled]
    profits = [profit for profit in profits if profit is not None]
    hit_count = sum(int(record.get("hit") or 0) for record in settled)
    return {
        "total_count": total_count,
        "open_count": sum(1 for record in records if record.get("settlement_status") == "open"),
        "settled_count": len(settled),
        "hit_count": hit_count,
        "hit_rate": round_metric(hit_count / len(settled)) if settled else None,
        "roi": round_metric(_average(profits), 4),
        "avg_edge": round_metric(_average([edge for edge in (parse_float(record.get("edge")) for record in records) if edge is not None]), 4),
    }


def _group_shadow_metrics(records: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        group_key = str(record.get(key) or "unknown")
        grouped.setdefault(group_key, []).append(record)
    return {group_key: _shadow_metric_summary(group_records) for group_key, group_records in sorted(grouped.items())}


def shadow_prediction_metrics(*, db_path: str | None = None, limit: int = 5000) -> dict[str, Any]:
    with _connect(db_path) as conn:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT * FROM shadow_prediction_records
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit or 5000),),
        ).fetchall()
    records = [_decode_shadow_row(row) for row in rows]
    record_counts: dict[str, int] = {}
    for record in records:
        status = str(record.get("settlement_status") or "unknown")
        record_counts[status] = record_counts.get(status, 0) + 1
    rejected_records = [record for record in records if record.get("rejection_reason")]
    return {
        "status": "ok",
        "db_path": db_path or learning_db_path(),
        "total_count": len(records),
        "record_counts": record_counts,
        "overall": _shadow_metric_summary(records),
        "by_decision": _group_shadow_metrics(records, "decision"),
        "by_market": _group_shadow_metrics(records, "market"),
        "by_rejection_reason": _group_shadow_metrics(rejected_records, "rejection_reason"),
    }


def _bucket(value: float | None, *, size: float, prefix: str) -> str:
    if value is None:
        return f"{prefix}:unknown"
    start = math.floor(value / size) * size
    end = start + size
    return f"{prefix}:{start:.2f}-{end:.2f}"


def _line_bucket(market: str, line: float | None) -> str:
    if line is None or market == "1x2":
        return "line:none"
    return f"line:{line:+g}"


def _calibration_key(record: dict[str, Any]) -> tuple[str, str, str, str, str]:
    probability = parse_float(record.get("calibrated_probability")) or parse_float(record.get("model_probability"))
    return (
        str(record.get("market") or "unknown"),
        str(record.get("league") or "ALL"),
        _line_bucket(str(record.get("market") or ""), parse_float(record.get("line"))),
        _bucket(parse_float(record.get("decimal_odds")), size=0.2, prefix="odds"),
        _bucket(probability, size=0.05, prefix="prob"),
    )


def _append_key(keys: list[tuple[str, str, str, str, str]], key: tuple[str, str, str, str, str]) -> None:
    if key not in keys:
        keys.append(key)


def _calibration_keys(record: dict[str, Any]) -> list[tuple[str, str, str, str, str]]:
    market, league_bucket, line_bucket, odds_bucket, probability_bucket = _calibration_key(record)
    keys: list[tuple[str, str, str, str, str]] = []
    _append_key(keys, (market, league_bucket, line_bucket, odds_bucket, probability_bucket))
    _append_key(keys, (market, "ALL", line_bucket, odds_bucket, probability_bucket))
    _append_key(keys, (market, "ALL", line_bucket, "odds:ALL", probability_bucket))
    _append_key(keys, (market, "ALL", "line:ALL", "odds:ALL", probability_bucket))
    _append_key(keys, (market, "ALL", "line:ALL", "odds:ALL", "prob:ALL"))
    return keys


def recompute_calibration(*, db_path: str | None = None) -> dict[str, Any]:
    with _connect(db_path) as conn:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT * FROM recommendation_records
            WHERE settlement_status = 'settled'
            """
        ).fetchall()
        grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}
        for row in rows:
            record = dict(row)
            for key in _calibration_keys(record):
                grouped.setdefault(key, []).append(record)
        conn.execute("DELETE FROM calibration_buckets")
        buckets = []
        updated_at = now_utc_iso()
        for key, records in sorted(grouped.items()):
            market, league_bucket, line_bucket, odds_bucket, probability_bucket = key
            sample_count = len(records)
            hit_count = sum(int(record.get("hit") or 0) for record in records)
            hit_rate = hit_count / sample_count if sample_count else None
            probabilities = [
                parse_float(record.get("calibrated_probability")) or parse_float(record.get("model_probability"))
                for record in records
            ]
            edges = [parse_float(record.get("edge")) for record in records]
            profits = [parse_float(record.get("profit_units")) for record in records]
            avg_model_probability = _average([item for item in probabilities if item is not None])
            avg_edge = _average([item for item in edges if item is not None])
            roi = _average([item for item in profits if item is not None])
            raw = {
                "record_ids": [record.get("id") for record in records],
                "sample_count": sample_count,
                "hit_count": hit_count,
                "bucket_scope": _bucket_scope(league_bucket, line_bucket, odds_bucket, probability_bucket),
            }
            bucket = {
                "market": market,
                "league_bucket": league_bucket,
                "line_bucket": line_bucket,
                "odds_bucket": odds_bucket,
                "probability_bucket": probability_bucket,
                "sample_count": sample_count,
                "hit_count": hit_count,
                "hit_rate": round_metric(hit_rate),
                "avg_model_probability": round_metric(avg_model_probability),
                "avg_edge": round_metric(avg_edge, 4),
                "roi": round_metric(roi, 4),
                "updated_at_utc": updated_at,
                "raw": raw,
            }
            buckets.append(bucket)
            conn.execute(
                """
                INSERT INTO calibration_buckets (
                    market, league_bucket, line_bucket, odds_bucket, probability_bucket,
                    sample_count, hit_count, hit_rate, avg_model_probability, avg_edge,
                    roi, updated_at_utc, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    market,
                    league_bucket,
                    line_bucket,
                    odds_bucket,
                    probability_bucket,
                    sample_count,
                    hit_count,
                    bucket["hit_rate"],
                    bucket["avg_model_probability"],
                    bucket["avg_edge"],
                    bucket["roi"],
                    updated_at,
                    _json(raw),
                ),
            )
        conn.commit()
    return {
        "status": "ok",
        "db_path": db_path or learning_db_path(),
        "settled_count": len(rows),
        "calibration_bucket_count": len(buckets),
        "buckets": buckets,
    }


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _bucket_scope(league_bucket: str, line_bucket: str, odds_bucket: str, probability_bucket: str) -> str:
    if league_bucket != "ALL" and line_bucket != "line:ALL" and odds_bucket != "odds:ALL" and probability_bucket != "prob:ALL":
        return "exact"
    if league_bucket == "ALL" and line_bucket != "line:ALL" and odds_bucket != "odds:ALL" and probability_bucket != "prob:ALL":
        return "market_line_odds_probability"
    if line_bucket != "line:ALL" and probability_bucket != "prob:ALL":
        return "market_line_probability"
    if probability_bucket != "prob:ALL":
        return "market_probability"
    return "market_global"


def calibration_status(*, db_path: str | None = None, limit: int = 50) -> dict[str, Any]:
    with _connect(db_path) as conn:
        ensure_schema(conn)
        counts = conn.execute(
            """
            SELECT settlement_status, COUNT(*) AS count
            FROM recommendation_records
            GROUP BY settlement_status
            """
        ).fetchall()
        buckets = conn.execute(
            """
            SELECT * FROM calibration_buckets
            ORDER BY sample_count DESC, roi DESC
            LIMIT ?
            """,
            (int(limit or 50),),
        ).fetchall()
        bucket_total = conn.execute("SELECT COUNT(*) AS count FROM calibration_buckets").fetchone()["count"]
        strategy_rows = conn.execute(
            """
            SELECT * FROM strategy_state
            ORDER BY updated_at_utc DESC
            """
        ).fetchall()
    return {
        "status": "ok",
        "db_path": db_path or learning_db_path(),
        "record_counts": {row["settlement_status"]: row["count"] for row in counts},
        "bucket_count": bucket_total,
        "buckets": [
            {
                **{key: value for key, value in dict(row).items() if key != "raw_json"},
                "raw": json.loads(row["raw_json"] or "{}"),
            }
            for row in buckets
        ],
        "strategy_states": [_decode_strategy_state_row(row) for row in strategy_rows],
    }


def _strategy_key(market: str, mode: str) -> str:
    return f"{str(market or '').strip().lower()}:{str(mode or '').strip().lower()}"


def _default_strategy_state(*, market: str = "asian_handicap", mode: str = "balanced") -> dict[str, Any]:
    defaults = dict(DEFAULT_BALANCED_STRATEGY)
    return {
        "key": _strategy_key(market, mode),
        "market": market,
        "mode": mode,
        "status": "collecting_samples",
        "active": False,
        "sample_count": 0,
        "hit_rate": None,
        "roi": None,
        "avg_model_probability": None,
        **defaults,
        "updated_at_utc": None,
        "raw": {
            "rule": "Strategy state starts in collection mode until enough settled paper recommendations exist.",
            "base_thresholds": defaults,
        },
    }


def _decode_strategy_state_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    try:
        raw = json.loads(item.get("raw_json") or "{}")
    except json.JSONDecodeError:
        raw = {}
    return {
        "key": item.get("key"),
        "market": item.get("market"),
        "mode": item.get("mode"),
        "status": item.get("status"),
        "active": bool(item.get("active")),
        "sample_count": int(item.get("sample_count") or 0),
        "hit_rate": item.get("hit_rate"),
        "roi": item.get("roi"),
        "avg_model_probability": item.get("avg_model_probability"),
        "min_live_sample_count": int(item.get("min_live_sample_count") or DEFAULT_BALANCED_STRATEGY["min_live_sample_count"]),
        "prior_strength": item.get("prior_strength"),
        "min_calibrated_probability": item.get("min_calibrated_probability"),
        "min_decimal_odds": item.get("min_decimal_odds"),
        "max_decimal_odds": item.get("max_decimal_odds"),
        "min_value_edge": item.get("min_value_edge"),
        "updated_at_utc": item.get("updated_at_utc"),
        "raw": raw,
    }


def get_strategy_state(
    *,
    db_path: str | None = None,
    market: str = "asian_handicap",
    mode: str = "balanced",
) -> dict[str, Any]:
    with _connect(db_path) as conn:
        ensure_schema(conn)
        row = conn.execute(
            """
            SELECT * FROM strategy_state
            WHERE key = ?
            LIMIT 1
            """,
            (_strategy_key(market, mode),),
        ).fetchone()
    if row:
        return _decode_strategy_state_row(row)
    return _default_strategy_state(market=market, mode=mode)


def _strategy_global_bucket(conn: sqlite3.Connection, market: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM calibration_buckets
        WHERE market = ?
          AND league_bucket = 'ALL'
          AND line_bucket = 'line:ALL'
          AND odds_bucket = 'odds:ALL'
          AND probability_bucket = 'prob:ALL'
        LIMIT 1
        """,
        (market,),
    ).fetchone()
    if not row:
        return None
    item = dict(row)
    try:
        item["raw"] = json.loads(item.get("raw_json") or "{}")
    except json.JSONDecodeError:
        item["raw"] = {}
    return item


def _derive_strategy_state(
    bucket: dict[str, Any] | None,
    *,
    market: str,
    mode: str,
) -> dict[str, Any]:
    defaults = dict(DEFAULT_BALANCED_STRATEGY)
    sample_count = int((bucket or {}).get("sample_count") or 0)
    hit_rate = parse_float((bucket or {}).get("hit_rate"))
    roi = parse_float((bucket or {}).get("roi"))
    avg_model_probability = parse_float((bucket or {}).get("avg_model_probability"))
    active = sample_count >= defaults["min_live_sample_count"]
    status = "live_calibration_active" if active else "collecting_samples"
    min_probability = defaults["min_calibrated_probability"]
    min_value_edge = defaults["min_value_edge"]
    min_decimal_odds = defaults["min_decimal_odds"]
    max_decimal_odds = defaults["max_decimal_odds"]
    probability_gap = (
        hit_rate - avg_model_probability
        if hit_rate is not None and avg_model_probability is not None
        else None
    )

    if active:
        if roi is not None and roi < -0.10:
            min_probability += 0.04
            min_value_edge += 0.02
            min_decimal_odds += 0.05
        elif roi is not None and roi < 0:
            min_probability += 0.02
            min_value_edge += 0.01

        if probability_gap is not None and probability_gap < -0.08:
            min_probability += 0.04
        elif probability_gap is not None and probability_gap < -0.03:
            min_probability += 0.02

        if hit_rate is not None and hit_rate >= 0.62 and (roi is None or roi <= 0):
            min_decimal_odds += 0.05

        if roi is not None and roi > 0.06 and (probability_gap is None or probability_gap >= -0.02):
            min_probability -= 0.01
            min_value_edge -= 0.005

    prior_strength = 40.0 if sample_count < 30 else 30.0 if sample_count < 60 else 20.0
    if not active:
        prior_strength = defaults["prior_strength"]

    return {
        "key": _strategy_key(market, mode),
        "market": market,
        "mode": mode,
        "status": status,
        "active": active,
        "sample_count": sample_count,
        "hit_rate": round_metric(hit_rate),
        "roi": round_metric(roi, 4),
        "avg_model_probability": round_metric(avg_model_probability),
        "min_live_sample_count": defaults["min_live_sample_count"],
        "prior_strength": round_metric(prior_strength, 2),
        "min_calibrated_probability": round_metric(_clamp(min_probability, 0.55, 0.72)),
        "min_decimal_odds": round_metric(_clamp(min_decimal_odds, 1.4, 2.2), 4),
        "max_decimal_odds": round_metric(_clamp(max_decimal_odds, 1.6, 2.8), 4),
        "min_value_edge": round_metric(_clamp(min_value_edge, 0.0, 0.08)),
        "updated_at_utc": now_utc_iso(),
        "raw": {
            "source_bucket": bucket,
            "probability_gap": round_metric(probability_gap),
            "base_thresholds": defaults,
            "rule": (
                "Closed-loop policy promotes settled paper outcomes into machine-readable thresholds. "
                "Negative ROI or overconfident buckets tighten balanced Asian-handicap requirements; "
                "positive ROI can relax them slightly after enough settled samples."
            ),
        },
    }


def update_strategy_state(
    *,
    db_path: str | None = None,
    market: str = "asian_handicap",
    mode: str = "balanced",
) -> dict[str, Any]:
    market = str(market or "asian_handicap").strip().lower()
    mode = str(mode or "balanced").strip().lower()
    with _connect(db_path) as conn:
        ensure_schema(conn)
        bucket = _strategy_global_bucket(conn, market)
        state = _derive_strategy_state(bucket, market=market, mode=mode)
        conn.execute(
            """
            INSERT INTO strategy_state (
                key, market, mode, status, active, sample_count, hit_rate, roi,
                avg_model_probability, min_live_sample_count, prior_strength,
                min_calibrated_probability, min_decimal_odds, max_decimal_odds,
                min_value_edge, updated_at_utc, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                market = excluded.market,
                mode = excluded.mode,
                status = excluded.status,
                active = excluded.active,
                sample_count = excluded.sample_count,
                hit_rate = excluded.hit_rate,
                roi = excluded.roi,
                avg_model_probability = excluded.avg_model_probability,
                min_live_sample_count = excluded.min_live_sample_count,
                prior_strength = excluded.prior_strength,
                min_calibrated_probability = excluded.min_calibrated_probability,
                min_decimal_odds = excluded.min_decimal_odds,
                max_decimal_odds = excluded.max_decimal_odds,
                min_value_edge = excluded.min_value_edge,
                updated_at_utc = excluded.updated_at_utc,
                raw_json = excluded.raw_json
            """,
            (
                state["key"],
                state["market"],
                state["mode"],
                state["status"],
                1 if state["active"] else 0,
                state["sample_count"],
                state["hit_rate"],
                state["roi"],
                state["avg_model_probability"],
                state["min_live_sample_count"],
                state["prior_strength"],
                state["min_calibrated_probability"],
                state["min_decimal_odds"],
                state["max_decimal_odds"],
                state["min_value_edge"],
                state["updated_at_utc"],
                _json(state["raw"]),
            ),
        )
        conn.commit()
    return state


def build_record_from_pick(
    pick: dict[str, Any],
    *,
    run_id: str,
    tool: str,
    mode: str,
    target_market: str,
) -> dict[str, Any]:
    return {
        **pick,
        "run_id": run_id,
        "tool": tool,
        "mode": mode,
        "target_market": target_market,
        "raw": pick,
    }


def build_records_from_shortlist(result: dict[str, Any], *, run_id: str | None = None) -> list[dict[str, Any]]:
    resolved_run_id = run_id or make_run_id("shortlist")
    generated_at = result.get("generated_at_utc")
    return [
        build_record_from_pick(
            pick,
            run_id=resolved_run_id,
            tool=str(result.get("tool") or "shortlist_value_matches"),
            mode=str(result.get("mode") or ""),
            target_market=str(result.get("target_market") or ""),
        )
        for pick in result.get("picks") or []
        if _is_near_kickoff_learning_sample(pick, default_as_of=generated_at)
    ]


def build_learning_observation_records_from_shortlist(
    result: dict[str, Any],
    *,
    run_id: str | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    resolved_run_id = run_id or make_run_id("shortlist-observation")
    target_market = str(result.get("target_market") or "")
    generated_at = result.get("generated_at_utc")
    records = []
    for item in result.get("rejected") or []:
        if not _is_near_kickoff_learning_sample(item, default_as_of=generated_at):
            continue
        best = item.get("best_candidate") or {}
        market = str(best.get("market") or "")
        if target_market and target_market != "any" and market != target_market:
            continue
        if not (item.get("match") and best.get("selection") and best.get("selection_key")):
            continue
        if parse_float(best.get("decimal_odds")) is None:
            continue
        if parse_float(best.get("model_probability")) is None and parse_float(best.get("calibrated_probability")) is None:
            continue
        records.append(
            {
                "match": item.get("match") or {},
                "best_candidate": best,
                "run_id": resolved_run_id,
                "tool": str(result.get("tool") or "shortlist_value_matches"),
                "mode": f"{str(result.get('mode') or '')}_observation".strip("_"),
                "target_market": target_market,
                "caution_flags": item.get("caution_flags") or [],
                "raw": {"kind": "learning_observation", **item},
            }
        )
        if len(records) >= max(0, int(limit or 0)):
            break
    return records


def build_shadow_prediction_records_from_shortlist(
    result: dict[str, Any],
    *,
    run_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    resolved_run_id = run_id or make_run_id("shadow")
    bounded_limit = max(0, int(limit or 0))
    thresholds = result.get("balanced_thresholds") or {}
    generated_at = result.get("generated_at_utc")
    records: list[dict[str, Any]] = []
    source_items = [
        ("accepted", "", item)
        for item in result.get("picks") or []
        if _is_near_kickoff_learning_sample(item, default_as_of=generated_at)
    ] + [
        ("rejected", str(item.get("reason") or ""), item)
        for item in result.get("rejected") or []
        if _is_near_kickoff_learning_sample(item, default_as_of=generated_at)
    ]
    for decision, rejection_reason, item in source_items:
        best = item.get("best_candidate") or {}
        match = item.get("match") or {}
        records.append(
            {
                "match": match,
                "best_candidate": best,
                "run_id": resolved_run_id,
                "tool": str(result.get("tool") or "shortlist_value_matches"),
                "mode": str(result.get("mode") or ""),
                "target_market": str(result.get("target_market") or ""),
                "decision": decision,
                "rejection_reason": rejection_reason,
                "quality": item.get("quality") or {},
                "thresholds": thresholds,
                "selection_confidence": item.get("selection_confidence") or {},
                "settlement_status": _shadow_settlement_status({"best_candidate": best}, best),
                "raw": {
                    "kind": "shadow_prediction",
                    "decision": decision,
                    "rejection_reason": rejection_reason,
                    "source_tool": str(result.get("tool") or "shortlist_value_matches"),
                    **item,
                },
            }
        )
        if len(records) >= bounded_limit:
            break
    return records


def build_records_from_parlay(result: dict[str, Any], *, run_id: str | None = None) -> list[dict[str, Any]]:
    resolved_run_id = run_id or make_run_id("parlay")
    records = []
    for ticket in result.get("recommended_tickets") or []:
        records.append(
            {
                "run_id": resolved_run_id,
                "tool": str(result.get("tool") or "recommend_jingcai_parlay"),
                "mode": str(result.get("parlay_mode") or ""),
                "target_market": "parlay",
                "settlement_status": "tracked_only",
                "league": "",
                "home_team": "PARLAY",
                "away_team": str(ticket.get("parlay_type") or ""),
                "market": "parlay",
                "selection": " + ".join(str((leg or {}).get("selection") or "") for leg in ticket.get("legs") or []),
                "selection_key": "parlay",
                "decimal_odds": ticket.get("combined_decimal_odds"),
                "model_probability": ticket.get("estimated_hit_probability"),
                "edge": ticket.get("edge_proxy"),
                "expected_multiplier": ticket.get("expected_multiplier"),
                "recommendation": ticket.get("recommendation"),
                "stake_level": ticket.get("stake_level"),
                "risk_flags": ticket.get("risk_flags") or [],
                "caution_flags": ticket.get("caution_flags") or [],
                "raw": ticket,
            }
        )
    return records

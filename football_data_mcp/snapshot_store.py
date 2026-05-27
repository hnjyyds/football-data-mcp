from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from hashlib import sha256
from statistics import median
from typing import Any


DEFAULT_SNAPSHOT_DB = "/tmp/football_data_mcp_snapshots.sqlite3"


@dataclass(frozen=True)
class MarketSnapshot:
    provider: str
    source_key: str
    event_id: str
    league: str
    home_team: str
    away_team: str
    kickoff_utc: str
    bookmaker: str
    market_type: str
    selection: str
    decimal_odds: float
    line: float | None
    source_time_utc: str
    fetched_at_utc: str
    raw: dict[str, Any]


def snapshot_db_path() -> str:
    return os.getenv("FOOTBALL_DATA_SNAPSHOT_DB", DEFAULT_SNAPSHOT_DB)


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or snapshot_db_path()
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
        CREATE TABLE IF NOT EXISTS market_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_key TEXT,
            provider TEXT NOT NULL,
            source_key TEXT NOT NULL,
            event_id TEXT NOT NULL,
            league TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            kickoff_utc TEXT NOT NULL,
            bookmaker TEXT NOT NULL,
            market_type TEXT NOT NULL,
            selection TEXT NOT NULL,
            decimal_odds REAL NOT NULL,
            line REAL,
            source_time_utc TEXT NOT NULL,
            fetched_at_utc TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
        )
        """
    )
    _ensure_column(conn, "market_snapshots", "snapshot_key", "TEXT")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_market_snapshots_snapshot_key
        ON market_snapshots(snapshot_key)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_market_snapshots_match
        ON market_snapshots(home_team, away_team, kickoff_utc, market_type)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_market_snapshots_fetch
        ON market_snapshots(provider, fetched_at_utc)
        """
    )
    conn.commit()


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_type: str) -> None:
    if column_name not in _table_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def market_snapshot_key(snapshot: MarketSnapshot) -> str:
    identity = {
        "provider": snapshot.provider,
        "source_key": snapshot.source_key,
        "event_id": snapshot.event_id,
        "bookmaker": snapshot.bookmaker,
        "market_type": snapshot.market_type,
        "selection": snapshot.selection,
        "line": snapshot.line,
        "decimal_odds": snapshot.decimal_odds,
        "source_time_utc": snapshot.source_time_utc,
    }
    encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def save_market_snapshots(snapshots: list[MarketSnapshot], *, db_path: str | None = None) -> int:
    if not snapshots:
        return 0
    with _connect(db_path) as conn:
        ensure_schema(conn)
        before = conn.total_changes
        conn.executemany(
            """
            INSERT OR IGNORE INTO market_snapshots (
                snapshot_key, provider, source_key, event_id, league, home_team, away_team, kickoff_utc,
                bookmaker, market_type, selection, decimal_odds, line, source_time_utc,
                fetched_at_utc, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    market_snapshot_key(item),
                    item.provider,
                    item.source_key,
                    item.event_id,
                    item.league,
                    item.home_team,
                    item.away_team,
                    item.kickoff_utc,
                    item.bookmaker,
                    item.market_type,
                    item.selection,
                    item.decimal_odds,
                    item.line,
                    item.source_time_utc,
                    item.fetched_at_utc,
                    json.dumps(item.raw, ensure_ascii=False, sort_keys=True),
                )
                for item in snapshots
            ],
        )
        conn.commit()
        return conn.total_changes - before


_TEXT_VARIANTS = str.maketrans(
    {
        "裡": "里",
        "裏": "里",
        "臺": "台",
        "台": "台",
    }
)


def _normalize_team(value: str) -> str:
    value = (value or "").translate(_TEXT_VARIANTS)
    value = (value or "").lower()
    value = re.sub(r"\b(fc|cf|afc|sc|u23|u21)\b", " ", value)
    value = re.sub(r"_+", " ", value)
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def _team_matches(needle: str, candidate: str) -> bool:
    needle_norm = _normalize_team(needle)
    candidate_norm = _normalize_team(candidate)
    if not needle_norm or not candidate_norm:
        return False
    return needle_norm == candidate_norm or needle_norm in candidate_norm or candidate_norm in needle_norm


def _name_similarity(left: str, right: str) -> float:
    left_norm = _normalize_team(left)
    right_norm = _normalize_team(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm or left_norm in right_norm or right_norm in left_norm:
        return 1.0
    sequence_score = SequenceMatcher(None, left_norm, right_norm).ratio()
    left_chars = {char for char in left_norm if not char.isspace()}
    right_chars = {char for char in right_norm if not char.isspace()}
    overlap_score = len(left_chars & right_chars) / max(1, min(len(left_chars), len(right_chars)))
    return max(sequence_score, overlap_score)


def _snapshot_candidate_score(home_team: str, away_team: str, league: str, item: dict[str, Any]) -> float:
    home_score = _name_similarity(home_team, str(item.get("home_team") or ""))
    away_score = _name_similarity(away_team, str(item.get("away_team") or ""))
    league_score = _name_similarity(league, str(item.get("league") or "")) if league else 0.0
    if home_score >= 1.0 and away_score >= 1.0:
        return 1.0
    if not league or league_score < 0.6:
        return 0.0
    if home_score >= 1.0 and away_score >= 0.45:
        return 0.86 + min(away_score, 0.99) * 0.05 + min(league_score, 0.99) * 0.04
    if away_score >= 1.0 and home_score >= 0.45:
        return 0.86 + min(home_score, 0.99) * 0.05 + min(league_score, 0.99) * 0.04
    if home_score >= 0.65 and away_score >= 0.65:
        return 0.72 + min(home_score + away_score + league_score, 2.97) * 0.05
    return 0.0


def market_snapshot_match_key(home_team: str, away_team: str) -> str:
    return f"{_normalize_team(home_team)}|{_normalize_team(away_team)}"


def market_snapshot_coverage_by_match(*, db_path: str | None = None) -> dict[str, dict[str, Any]]:
    with _connect(db_path) as conn:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT
                home_team,
                away_team,
                COUNT(*) AS snapshot_count,
                COUNT(DISTINCT bookmaker) AS bookmaker_count,
                COUNT(DISTINCT market_type) AS market_type_count,
                MAX(fetched_at_utc) AS latest_fetched_at_utc
            FROM market_snapshots
            GROUP BY home_team, away_team
            """
        ).fetchall()
    coverage: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = dict(row)
        key = market_snapshot_match_key(str(item.get("home_team") or ""), str(item.get("away_team") or ""))
        if key == "|":
            continue
        existing = coverage.get(key)
        if existing:
            existing["snapshot_count"] = int(existing.get("snapshot_count") or 0) + int(item.get("snapshot_count") or 0)
            existing["bookmaker_count"] = max(
                int(existing.get("bookmaker_count") or 0),
                int(item.get("bookmaker_count") or 0),
            )
            existing["market_type_count"] = max(
                int(existing.get("market_type_count") or 0),
                int(item.get("market_type_count") or 0),
            )
            existing["latest_fetched_at_utc"] = max(
                str(existing.get("latest_fetched_at_utc") or ""),
                str(item.get("latest_fetched_at_utc") or ""),
            )
            if existing.get("provider") != item.get("provider") or existing.get("event_id") != item.get("event_id"):
                existing["provider"] = existing.get("provider") or item.get("provider")
                existing["source_key"] = existing.get("source_key") or item.get("source_key")
                existing["event_id"] = existing.get("event_id") or item.get("event_id")
            continue
        coverage[key] = {
            "snapshot_count": int(item.get("snapshot_count") or 0),
            "bookmaker_count": int(item.get("bookmaker_count") or 0),
            "market_type_count": int(item.get("market_type_count") or 0),
            "latest_fetched_at_utc": item.get("latest_fetched_at_utc"),
            "provider": item.get("provider"),
            "source_key": item.get("source_key"),
            "event_id": item.get("event_id"),
            "league": item.get("league"),
            "home_team": item.get("home_team"),
            "away_team": item.get("away_team"),
        }
    return coverage


def market_snapshot_coverage_for_records(
    records: list[dict[str, Any]],
    *,
    db_path: str | None = None,
) -> dict[str, dict[str, Any]]:
    if not records:
        return {}
    with _connect(db_path) as conn:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT
                provider,
                source_key,
                event_id,
                league,
                home_team,
                away_team,
                COUNT(*) AS snapshot_count,
                COUNT(DISTINCT bookmaker) AS bookmaker_count,
                COUNT(DISTINCT market_type) AS market_type_count,
                MAX(fetched_at_utc) AS latest_fetched_at_utc
            FROM market_snapshots
            GROUP BY provider, source_key, event_id, league, home_team, away_team
            """
        ).fetchall()

    event_coverages = [dict(row) for row in rows]
    coverage: dict[str, dict[str, Any]] = {}
    exact_by_key: dict[str, dict[str, Any]] = {}
    for item in event_coverages:
        key = market_snapshot_match_key(str(item.get("home_team") or ""), str(item.get("away_team") or ""))
        if key == "|":
            continue
        existing = exact_by_key.get(key)
        if existing:
            existing["snapshot_count"] = int(existing.get("snapshot_count") or 0) + int(item.get("snapshot_count") or 0)
            existing["bookmaker_count"] = max(
                int(existing.get("bookmaker_count") or 0),
                int(item.get("bookmaker_count") or 0),
            )
            existing["market_type_count"] = max(
                int(existing.get("market_type_count") or 0),
                int(item.get("market_type_count") or 0),
            )
            existing["latest_fetched_at_utc"] = max(
                str(existing.get("latest_fetched_at_utc") or ""),
                str(item.get("latest_fetched_at_utc") or ""),
            )
        else:
            exact_by_key[key] = {
                "snapshot_count": int(item.get("snapshot_count") or 0),
                "bookmaker_count": int(item.get("bookmaker_count") or 0),
                "market_type_count": int(item.get("market_type_count") or 0),
                "latest_fetched_at_utc": item.get("latest_fetched_at_utc"),
                "provider": item.get("provider"),
                "source_key": item.get("source_key"),
                "event_id": item.get("event_id"),
                "league": item.get("league"),
                "home_team": item.get("home_team"),
                "away_team": item.get("away_team"),
            }

    for record in records:
        record_key = market_snapshot_match_key(
            str(record.get("home_team") or ""),
            str(record.get("away_team") or ""),
        )
        if record_key == "|" or record_key in coverage:
            continue
        exact = exact_by_key.get(record_key)
        if exact:
            coverage[record_key] = exact
            continue
        best_score = 0.0
        best_item: dict[str, Any] | None = None
        for item in event_coverages:
            score = _snapshot_candidate_score(
                str(record.get("home_team") or ""),
                str(record.get("away_team") or ""),
                str(record.get("league") or ""),
                item,
            )
            if score > best_score:
                best_score = score
                best_item = item
        if best_item and best_score >= 0.72:
            coverage[record_key] = {
                "snapshot_count": int(best_item.get("snapshot_count") or 0),
                "bookmaker_count": int(best_item.get("bookmaker_count") or 0),
                "market_type_count": int(best_item.get("market_type_count") or 0),
                "latest_fetched_at_utc": best_item.get("latest_fetched_at_utc"),
                "provider": best_item.get("provider"),
                "source_key": best_item.get("source_key"),
                "event_id": best_item.get("event_id"),
                "league": best_item.get("league"),
                "home_team": best_item.get("home_team"),
                "away_team": best_item.get("away_team"),
            }
    return coverage


def _snapshot_row_dict(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["raw"] = json.loads(item.pop("raw_json") or "{}")
    return item


def find_market_snapshots(
    home_team: str,
    away_team: str,
    *,
    league: str | None = None,
    db_path: str | None = None,
    limit: int = 500,
    allow_fuzzy: bool = True,
) -> list[dict[str, Any]]:
    with _connect(db_path) as conn:
        ensure_schema(conn)
        exact_rows = conn.execute(
            """
            SELECT * FROM market_snapshots
            WHERE home_team = ? AND away_team = ?
            ORDER BY fetched_at_utc DESC, id DESC
            LIMIT ?
            """,
            (str(home_team or ""), str(away_team or ""), limit),
        ).fetchall()
        if exact_rows:
            return [_snapshot_row_dict(row) for row in exact_rows]
        if not allow_fuzzy:
            return []
        rows = conn.execute(
            """
            SELECT * FROM market_snapshots
            ORDER BY fetched_at_utc DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    matches = []
    fuzzy_matches: list[tuple[float, tuple[str, str, str, str, str, str], dict[str, Any]]] = []
    for row in rows:
        item = _snapshot_row_dict(row)
        if _team_matches(home_team, item["home_team"]) and _team_matches(away_team, item["away_team"]):
            matches.append(item)
            continue
        score = _snapshot_candidate_score(home_team, away_team, league or "", item)
        if score:
            fuzzy_matches.append(
                (
                    score,
                    (
                        str(item.get("provider") or ""),
                        str(item.get("source_key") or ""),
                        str(item.get("event_id") or ""),
                        str(item.get("league") or ""),
                        str(item.get("home_team") or ""),
                        str(item.get("away_team") or ""),
                    ),
                    item,
                )
            )
    if matches:
        return matches
    if fuzzy_matches:
        best_score, best_key, _ = max(fuzzy_matches, key=lambda candidate: candidate[0])
        if best_score >= 0.72:
            return [item for score, key, item in fuzzy_matches if key == best_key and score >= best_score - 0.001]
    return matches


def market_snapshot_coverage_for_match(
    home_team: str,
    away_team: str,
    *,
    league: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    rows = find_market_snapshots(home_team, away_team, league=league, db_path=db_path, limit=20000)
    if not rows:
        return {}
    return {
        "snapshot_count": len(rows),
        "bookmaker_count": len({str(row.get("bookmaker") or "") for row in rows if row.get("bookmaker")}),
        "market_type_count": len({str(row.get("market_type") or "") for row in rows if row.get("market_type")}),
        "latest_fetched_at_utc": max((str(row.get("fetched_at_utc") or "") for row in rows), default=""),
    }


def build_market_consensus(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in rows:
        grouped.setdefault(row["market_type"], {}).setdefault(row["selection"], []).append(row)

    consensus: dict[str, Any] = {}
    for market_type, selections in grouped.items():
        consensus[market_type] = {}
        for selection, selection_rows in selections.items():
            prices = [float(row["decimal_odds"]) for row in selection_rows if row.get("decimal_odds")]
            bookmakers = sorted({row["bookmaker"] for row in selection_rows if row.get("bookmaker")})
            latest_source_time = max((row["source_time_utc"] for row in selection_rows if row.get("source_time_utc")), default=None)
            latest_fetch_time = max((row["fetched_at_utc"] for row in selection_rows if row.get("fetched_at_utc")), default=None)
            lines = sorted({row["line"] for row in selection_rows if row.get("line") is not None})
            consensus[market_type][selection] = {
                "bookmaker_count": len(bookmakers),
                "bookmakers": bookmakers,
                "snapshot_count": len(selection_rows),
                "median_decimal_odds": round(float(median(prices)), 6) if prices else None,
                "min_decimal_odds": min(prices) if prices else None,
                "max_decimal_odds": max(prices) if prices else None,
                "line": lines[0] if len(lines) == 1 else None,
                "lines": lines,
                "latest_source_time_utc": latest_source_time,
                "latest_fetched_at_utc": latest_fetch_time,
            }
    return consensus


def _parse_snapshot_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _snapshot_row_time(row: dict[str, Any]) -> datetime | None:
    return _parse_snapshot_time(row.get("source_time_utc")) or _parse_snapshot_time(row.get("fetched_at_utc"))


def _resolve_market_selection(selection: str, home_team: str, away_team: str) -> str:
    value = str(selection or "").strip()
    lowered = value.lower()
    if lowered in {"home", "h", "主", "主队"}:
        return home_team
    if lowered in {"away", "a", "客", "客队"}:
        return away_team
    if lowered in {"draw", "d", "平", "平局"}:
        return "Draw"
    return value


def _selection_matches(selection: str, candidate: str) -> bool:
    selection_norm = _normalize_team(selection)
    candidate_norm = _normalize_team(candidate)
    if not selection_norm or not candidate_norm:
        return str(selection or "").strip().lower() == str(candidate or "").strip().lower()
    return selection_norm == candidate_norm or selection_norm in candidate_norm or candidate_norm in selection_norm


def _line_matches(expected: float | None, candidate: Any, *, tolerance: float = 1e-6) -> bool:
    if expected is None:
        return True
    try:
        expected_value = float(expected)
    except (TypeError, ValueError):
        return True
    try:
        candidate_value = float(candidate)
    except (TypeError, ValueError):
        return False
    return abs(expected_value - candidate_value) <= tolerance


def _market_type_aliases(market_type: str) -> set[str]:
    normalized = str(market_type or "").strip().lower()
    if normalized in {"1x2", "h2h", "moneyline"}:
        return {"1x2", "h2h", "moneyline"}
    if normalized in {"asian_handicap", "spreads", "spread"}:
        return {"asian_handicap", "spreads", "spread"}
    if normalized in {"over_under", "totals", "total"}:
        return {"over_under", "totals", "total"}
    return {normalized} if normalized else set()


def _market_type_matches(expected: str, candidate: Any) -> bool:
    expected_aliases = _market_type_aliases(expected)
    candidate_aliases = _market_type_aliases(str(candidate or ""))
    return bool(expected_aliases and candidate_aliases and expected_aliases.intersection(candidate_aliases))


def _canonical_market_type(value: Any) -> str:
    aliases = _market_type_aliases(str(value or ""))
    if aliases.intersection({"1x2", "h2h", "moneyline"}):
        return "h2h"
    if aliases.intersection({"asian_handicap", "spreads", "spread"}):
        return "asian_handicap"
    if aliases.intersection({"over_under", "totals", "total"}):
        return "over_under"
    return str(value or "").strip().lower()


def _snapshot_selection_key(row: dict[str, Any], home_team: str, away_team: str) -> str:
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    raw_side = str((raw or {}).get("side") or "").strip().lower()
    if raw_side in {"home", "draw", "away", "home_cover", "away_cover", "over", "under"}:
        return raw_side

    market_type = _canonical_market_type(row.get("market_type"))
    selection = _resolve_market_selection(str(row.get("selection") or ""), home_team, away_team)
    selection_norm = selection.strip().lower()
    if market_type == "h2h":
        if selection_norm in {"draw", "d", "x", "平", "平局"}:
            return "draw"
        if _selection_matches(selection, home_team):
            return "home"
        if _selection_matches(selection, away_team):
            return "away"
    if market_type == "asian_handicap":
        if _selection_matches(selection, home_team):
            return "home_cover"
        if _selection_matches(selection, away_team):
            return "away_cover"
    if market_type == "over_under":
        if selection_norm in {"over", "o", "大", "大球"}:
            return "over"
        if selection_norm in {"under", "u", "小", "小球"}:
            return "under"
    return selection_norm


def _market_movement_round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _market_movement_median(values: list[float]) -> float | None:
    return float(median(values)) if values else None


def _market_movement_direction(
    implied_probability_delta: float | None,
    odds_delta: float | None,
) -> tuple[str, str]:
    probability_delta = float(implied_probability_delta or 0.0)
    price_delta = float(odds_delta or 0.0)
    if abs(probability_delta) < 0.005 and abs(price_delta) < 0.02:
        return "stable", "平稳"
    if probability_delta > 0:
        return "shortening", "升温"
    return "drifting", "降温"


def _market_movement_selection_summary(
    rows: list[dict[str, Any]],
    *,
    market_type: str,
    selection_key: str,
) -> dict[str, Any]:
    timed_rows = [(row, row_time) for row in rows if (row_time := _snapshot_row_time(row)) is not None]
    latest_selection = str((rows[0] if rows else {}).get("selection") or selection_key)
    base = {
        "market_type": market_type,
        "selection_key": selection_key,
        "selection": latest_selection,
        "snapshot_count": len(rows),
        "bookmaker_count": len({str(row.get("bookmaker") or "") for row in rows if row.get("bookmaker")}),
    }
    if len(timed_rows) < 2:
        return {
            **base,
            "status": "insufficient_history",
            "reason": "need_at_least_two_time_ordered_snapshots",
        }

    first_by_bookmaker: dict[str, tuple[dict[str, Any], datetime]] = {}
    latest_by_bookmaker: dict[str, tuple[dict[str, Any], datetime]] = {}
    for row, row_time in sorted(timed_rows, key=lambda item: item[1]):
        bookmaker = str(row.get("bookmaker") or "unknown")
        if bookmaker not in first_by_bookmaker:
            first_by_bookmaker[bookmaker] = (row, row_time)
        latest_by_bookmaker[bookmaker] = (row, row_time)

    first_rows = [row for row, _row_time in first_by_bookmaker.values()]
    latest_rows = [row for row, _row_time in latest_by_bookmaker.values()]
    first_prices = [float(row["decimal_odds"]) for row in first_rows if float(row.get("decimal_odds") or 0.0) > 1.0]
    latest_prices = [float(row["decimal_odds"]) for row in latest_rows if float(row.get("decimal_odds") or 0.0) > 1.0]
    opening_price = _market_movement_median(first_prices)
    latest_price = _market_movement_median(latest_prices)
    if opening_price is None or latest_price is None:
        return {
            **base,
            "status": "insufficient_history",
            "reason": "valid_decimal_odds_missing",
        }

    first_lines = [
        float(row["line"])
        for row in first_rows
        if row.get("line") is not None
    ]
    latest_lines = [
        float(row["line"])
        for row in latest_rows
        if row.get("line") is not None
    ]
    opening_line = _market_movement_median(first_lines)
    latest_line = _market_movement_median(latest_lines)
    odds_delta = latest_price - opening_price
    implied_opening = 1.0 / opening_price
    implied_latest = 1.0 / latest_price
    implied_probability_delta = implied_latest - implied_opening
    direction, direction_label = _market_movement_direction(implied_probability_delta, odds_delta)
    first_time = min(row_time for _row, row_time in timed_rows)
    latest_time = max(row_time for _row, row_time in timed_rows)
    if first_time == latest_time:
        status = "insufficient_history"
        reason = "snapshots_share_same_observed_time"
    else:
        status = "available"
        reason = ""

    return {
        **base,
        "status": status,
        "reason": reason,
        "direction": direction,
        "direction_label": direction_label,
        "opening_decimal_odds": _market_movement_round(opening_price, 4),
        "latest_decimal_odds": _market_movement_round(latest_price, 4),
        "odds_delta": _market_movement_round(odds_delta, 4),
        "opening_implied_probability": _market_movement_round(implied_opening),
        "latest_implied_probability": _market_movement_round(implied_latest),
        "implied_probability_delta": _market_movement_round(implied_probability_delta),
        "opening_line": _market_movement_round(opening_line, 4),
        "latest_line": _market_movement_round(latest_line, 4),
        "line_delta": _market_movement_round(
            latest_line - opening_line if latest_line is not None and opening_line is not None else None,
            4,
        ),
        "latest_price_spread": _market_movement_round(max(latest_prices) - min(latest_prices), 4) if latest_prices else None,
        "first_observed_at_utc": first_time.isoformat(),
        "latest_observed_at_utc": latest_time.isoformat(),
    }


def build_market_movement_summary(
    rows: list[dict[str, Any]],
    *,
    home_team: str = "",
    away_team: str = "",
) -> dict[str, Any]:
    """Summarize opening-to-latest movement from persisted multi-bookmaker snapshots."""
    if not rows:
        return {
            "status": "unavailable",
            "method": "market_snapshot_movement_v1",
            "reason": "matching_market_snapshots_missing",
            "snapshot_count": 0,
            "bookmaker_count": 0,
            "market_type_count": 0,
            "markets": {},
            "key_movements": [],
        }

    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in rows:
        market_type = _canonical_market_type(row.get("market_type"))
        if not market_type:
            continue
        selection_key = _snapshot_selection_key(row, home_team, away_team)
        if not selection_key:
            continue
        grouped.setdefault(market_type, {}).setdefault(selection_key, []).append(row)

    markets: dict[str, Any] = {}
    key_movements: list[dict[str, Any]] = []
    for market_type, selections in grouped.items():
        selection_summaries = {
            selection_key: _market_movement_selection_summary(
                selection_rows,
                market_type=market_type,
                selection_key=selection_key,
            )
            for selection_key, selection_rows in selections.items()
        }
        available = [
            item
            for item in selection_summaries.values()
            if item.get("status") == "available" and item.get("implied_probability_delta") is not None
        ]
        primary = max(
            available or list(selection_summaries.values()),
            key=lambda item: abs(float(item.get("implied_probability_delta") or 0.0)),
            default={},
        )
        markets[market_type] = {
            "available": bool(available),
            "selection_count": len(selection_summaries),
            "snapshot_count": sum(int(item.get("snapshot_count") or 0) for item in selection_summaries.values()),
            "bookmaker_count": len(
                {
                    str(row.get("bookmaker") or "")
                    for selection_rows in selections.values()
                    for row in selection_rows
                    if row.get("bookmaker")
                }
            ),
            "primary_movement": primary,
            "selections": selection_summaries,
        }
        for item in available:
            key_movements.append(
                {
                    "market_type": item.get("market_type"),
                    "selection_key": item.get("selection_key"),
                    "selection": item.get("selection"),
                    "direction": item.get("direction"),
                    "direction_label": item.get("direction_label"),
                    "opening_decimal_odds": item.get("opening_decimal_odds"),
                    "latest_decimal_odds": item.get("latest_decimal_odds"),
                    "odds_delta": item.get("odds_delta"),
                    "opening_line": item.get("opening_line"),
                    "latest_line": item.get("latest_line"),
                    "line_delta": item.get("line_delta"),
                    "implied_probability_delta": item.get("implied_probability_delta"),
                    "bookmaker_count": item.get("bookmaker_count"),
                    "snapshot_count": item.get("snapshot_count"),
                    "latest_observed_at_utc": item.get("latest_observed_at_utc"),
                }
            )

    key_movements.sort(key=lambda item: abs(float(item.get("implied_probability_delta") or 0.0)), reverse=True)
    primary_movement = key_movements[0] if key_movements else {}
    return {
        "status": "available" if key_movements else "insufficient_history",
        "method": "market_snapshot_movement_v1",
        "reason": "" if key_movements else "need_multiple_time_ordered_snapshots_per_selection",
        "snapshot_count": len(rows),
        "bookmaker_count": len({str(row.get("bookmaker") or "") for row in rows if row.get("bookmaker")}),
        "market_type_count": len({str(row.get("market_type") or "") for row in rows if row.get("market_type")}),
        "first_fetched_at_utc": min((str(row.get("fetched_at_utc") or "") for row in rows), default=""),
        "latest_fetched_at_utc": max((str(row.get("fetched_at_utc") or "") for row in rows), default=""),
        "primary_movement": primary_movement,
        "markets": markets,
        "key_movements": key_movements[:8],
        "usage_policy": (
            "Use movement as professional market evidence. It can support or warn against a pick, "
            "but it does not replace model probability, settlement, or recommendation gates."
        ),
    }


def market_movement_for_match(
    home_team: str,
    away_team: str,
    *,
    league: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    rows = find_market_snapshots(home_team, away_team, league=league, db_path=db_path, limit=20000)
    return build_market_movement_summary(rows, home_team=home_team, away_team=away_team)


def closing_line_value_for_pick(
    *,
    home_team: str,
    away_team: str,
    selection: str,
    prediction_decimal_odds: float,
    market_type: str = "h2h",
    line: float | None = None,
    league: str | None = None,
    kickoff_utc: str | None = None,
    prediction_time_utc: str | None = None,
    closing_window_minutes: int = 30,
    db_path: str | None = None,
    allow_fuzzy_match: bool = True,
) -> dict[str, Any]:
    prediction_price = float(prediction_decimal_odds or 0.0)
    if prediction_price <= 1.0:
        return {
            "status": "unavailable",
            "method": "closing_line_value_from_market_snapshots_v1",
            "reason": "prediction_decimal_odds_required",
        }

    resolved_selection = _resolve_market_selection(selection, home_team, away_team)
    rows = find_market_snapshots(
        home_team,
        away_team,
        league=league,
        db_path=db_path,
        limit=20000,
        allow_fuzzy=allow_fuzzy_match,
    )
    market_rows = [
        row
        for row in rows
        if _market_type_matches(str(market_type or ""), row.get("market_type"))
        and _selection_matches(resolved_selection, str(row.get("selection") or ""))
        and _line_matches(line, row.get("line"))
        and float(row.get("decimal_odds") or 0.0) > 1.0
    ]
    if not market_rows:
        return {
            "status": "unavailable",
            "method": "closing_line_value_from_market_snapshots_v1",
            "reason": "matching_market_snapshots_missing",
            "home_team": home_team,
            "away_team": away_team,
            "selection": resolved_selection,
            "market_type": market_type,
            "line": line,
        }

    kickoff_time = _parse_snapshot_time(kickoff_utc) or _parse_snapshot_time(market_rows[0].get("kickoff_utc"))
    prediction_time = _parse_snapshot_time(prediction_time_utc)
    timed_rows = [(row, row_time) for row in market_rows if (row_time := _snapshot_row_time(row)) is not None]
    if not timed_rows:
        return {
            "status": "unavailable",
            "method": "closing_line_value_from_market_snapshots_v1",
            "reason": "snapshot_times_missing",
            "home_team": home_team,
            "away_team": away_team,
            "selection": resolved_selection,
            "market_type": market_type,
            "line": line,
        }

    closing_candidates = timed_rows
    if kickoff_time is not None:
        before_kickoff = [(row, row_time) for row, row_time in timed_rows if row_time <= kickoff_time]
        if not before_kickoff:
            return {
                "status": "unavailable",
                "method": "closing_line_value_from_market_snapshots_v1",
                "reason": "pre_kickoff_closing_snapshots_missing",
                "home_team": home_team,
                "away_team": away_team,
                "selection": resolved_selection,
                "market_type": market_type,
                "line": line,
            }
        window_start = kickoff_time - timedelta(minutes=max(1, int(closing_window_minutes or 30)))
        window_rows = [(row, row_time) for row, row_time in before_kickoff if row_time >= window_start]
        closing_candidates = window_rows or before_kickoff

    latest_by_bookmaker: dict[str, tuple[dict[str, Any], datetime]] = {}
    for row, row_time in closing_candidates:
        bookmaker = str(row.get("bookmaker") or "")
        existing = latest_by_bookmaker.get(bookmaker)
        if existing is None or row_time > existing[1]:
            latest_by_bookmaker[bookmaker] = (row, row_time)
    closing_rows = [row for row, _row_time in latest_by_bookmaker.values()]
    closing_prices = [float(row["decimal_odds"]) for row in closing_rows]
    closing_price = float(median(closing_prices))

    prediction_snapshot_rows = []
    if prediction_time is not None:
        prediction_snapshot_rows = [
            row
            for row, row_time in timed_rows
            if row_time <= prediction_time
        ]

    clv_decimal_delta = prediction_price - closing_price
    clv_return = prediction_price / closing_price - 1.0
    return {
        "status": "available",
        "method": "closing_line_value_from_market_snapshots_v1",
        "home_team": home_team,
        "away_team": away_team,
        "selection": resolved_selection,
        "market_type": market_type,
        "line": line,
        "prediction_decimal_odds": round(float(prediction_price), 6),
        "closing_decimal_odds": round(float(closing_price), 6),
        "clv_decimal_delta": round(float(clv_decimal_delta), 6),
        "clv_return": round(float(clv_return), 6),
        "clv_implied_probability_delta": round((1.0 / closing_price) - (1.0 / prediction_price), 6),
        "closing_bookmaker_count": len(closing_rows),
        "closing_snapshot_count": len(closing_rows),
        "closing_window_minutes": max(1, int(closing_window_minutes or 30)),
        "latest_closing_snapshot_utc": max(
            (str(row.get("source_time_utc") or row.get("fetched_at_utc") or "") for row in closing_rows),
            default="",
        ),
        "prediction_snapshot_count": len(prediction_snapshot_rows),
        "rule": "CLV 为正表示记录推荐价优于同一盘口方向的收盘共识价。",
    }


def _record_market_type(market: str) -> str:
    normalized = str(market or "").strip().lower()
    if normalized in {"1x2", "h2h", "moneyline"}:
        return "h2h"
    if normalized in {"asian_handicap", "spreads", "spread"}:
        return "spreads"
    if normalized in {"over_under", "totals", "total"}:
        return "totals"
    return normalized


def _record_selection(record: dict[str, Any]) -> str:
    selection_key = str(record.get("selection_key") or "").strip().lower()
    market_type = _record_market_type(str(record.get("market") or ""))
    if market_type == "h2h":
        if selection_key in {"home", "h"}:
            return "home"
        if selection_key in {"away", "a"}:
            return "away"
        if selection_key in {"draw", "d"}:
            return "draw"
    if market_type == "spreads":
        if selection_key in {"home", "home_cover", "h"}:
            return "home"
        if selection_key in {"away", "away_cover", "a"}:
            return "away"
    if market_type == "totals":
        if selection_key in {"over", "o"}:
            return "Over"
        if selection_key in {"under", "u"}:
            return "Under"
    return str(record.get("selection") or selection_key or "")


def closing_line_value_for_records(
    records: list[dict[str, Any]],
    *,
    db_path: str | None = None,
    closing_window_minutes: int = 30,
    limit: int = 100,
    allow_fuzzy_match: bool = True,
) -> dict[str, Any]:
    bounded_records = records[: max(1, min(int(limit or 100), 1000))]
    tracked = []
    skipped_count = 0
    for record in bounded_records:
        home_team = str(record.get("home_team") or "")
        away_team = str(record.get("away_team") or "")
        prediction_decimal_odds = record.get("decimal_odds")
        if not home_team or not away_team or prediction_decimal_odds is None:
            skipped_count += 1
            continue
        clv = closing_line_value_for_pick(
            home_team=home_team,
            away_team=away_team,
            selection=_record_selection(record),
            prediction_decimal_odds=float(prediction_decimal_odds),
            market_type=_record_market_type(str(record.get("market") or "")),
            line=record.get("line"),
            league=str(record.get("league") or "") or None,
            kickoff_utc=str(record.get("kickoff_utc") or record.get("kickoff_utc_plus_8") or "") or None,
            prediction_time_utc=str(record.get("created_at_utc") or "") or None,
            closing_window_minutes=closing_window_minutes,
            db_path=db_path,
            allow_fuzzy_match=allow_fuzzy_match,
        )
        tracked.append(
            {
                "record_id": record.get("id"),
                "record_key": record.get("record_key"),
                "home_team": home_team,
                "away_team": away_team,
                "market": record.get("market"),
                "selection": record.get("selection"),
                "selection_key": record.get("selection_key"),
                "status": clv.get("status"),
                "clv": clv,
            }
        )

    available = [item["clv"] for item in tracked if (item.get("clv") or {}).get("status") == "available"]
    returns = [float(item["clv_return"]) for item in available if item.get("clv_return") is not None]
    positive_count = sum(1 for value in returns if value > 0)
    return {
        "status": "ok" if tracked else "empty",
        "method": "closing_line_value_batch_tracking_v1",
        "record_count": len(bounded_records),
        "tracked_count": len(tracked),
        "skipped_count": skipped_count,
        "available_count": len(available),
        "positive_clv_count": positive_count,
        "positive_clv_rate": round(positive_count / len(returns), 6) if returns else None,
        "avg_clv_return": round(sum(returns) / len(returns), 6) if returns else None,
        "records": tracked,
        "rule": "CLV 只读取已持久化的赔率快照；缺少匹配盘口或只有开赛后价格时保持不可用。",
    }


def provider_snapshot_counts(*, db_path: str | None = None) -> dict[str, Any]:
    with _connect(db_path) as conn:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT provider, COUNT(*) AS snapshot_count, MAX(fetched_at_utc) AS latest_fetched_at_utc
            FROM market_snapshots
            GROUP BY provider
            """
        ).fetchall()
    return {row["provider"]: dict(row) for row in rows}


def market_snapshot_summary(*, db_path: str | None = None, latest_event_limit: int = 8) -> dict[str, Any]:
    with _connect(db_path) as conn:
        ensure_schema(conn)
        total = conn.execute(
            """
            SELECT
                COUNT(*) AS total_snapshot_count,
                COUNT(DISTINCT provider || ':' || source_key || ':' || event_id) AS event_count,
                COUNT(DISTINCT bookmaker) AS bookmaker_count,
                MAX(fetched_at_utc) AS latest_fetched_at_utc
            FROM market_snapshots
            """
        ).fetchone()
        provider_rows = conn.execute(
            """
            SELECT
                provider,
                COUNT(*) AS snapshot_count,
                COUNT(DISTINCT source_key || ':' || event_id) AS event_count,
                COUNT(DISTINCT bookmaker) AS bookmaker_count,
                COUNT(DISTINCT market_type) AS market_type_count,
                MIN(fetched_at_utc) AS first_fetched_at_utc,
                MAX(fetched_at_utc) AS latest_fetched_at_utc
            FROM market_snapshots
            GROUP BY provider
            ORDER BY snapshot_count DESC, provider ASC
            """
        ).fetchall()
        market_rows = conn.execute(
            """
            SELECT provider, market_type, COUNT(*) AS snapshot_count
            FROM market_snapshots
            GROUP BY provider, market_type
            ORDER BY provider ASC, snapshot_count DESC, market_type ASC
            """
        ).fetchall()
        latest_rows = conn.execute(
            """
            SELECT
                provider,
                source_key,
                event_id,
                league,
                home_team,
                away_team,
                kickoff_utc,
                COUNT(*) AS snapshot_count,
                COUNT(DISTINCT bookmaker) AS bookmaker_count,
                COUNT(DISTINCT market_type) AS market_type_count,
                MAX(fetched_at_utc) AS latest_fetched_at_utc
            FROM market_snapshots
            GROUP BY provider, source_key, event_id, league, home_team, away_team, kickoff_utc
            ORDER BY latest_fetched_at_utc DESC, snapshot_count DESC
            LIMIT ?
            """,
            (max(1, min(int(latest_event_limit or 8), 50)),),
        ).fetchall()

    market_types_by_provider: dict[str, list[str]] = {}
    market_type_counts = []
    for row in market_rows:
        item = dict(row)
        provider = str(item.get("provider") or "")
        market_types_by_provider.setdefault(provider, []).append(str(item.get("market_type") or ""))
        market_type_counts.append(item)

    providers = []
    for row in provider_rows:
        item = dict(row)
        item["market_types"] = market_types_by_provider.get(str(item.get("provider") or ""), [])
        providers.append(item)

    total_item = dict(total) if total else {}
    return {
        "db_path": db_path or snapshot_db_path(),
        "total_snapshot_count": int(total_item.get("total_snapshot_count") or 0),
        "event_count": int(total_item.get("event_count") or 0),
        "bookmaker_count": int(total_item.get("bookmaker_count") or 0),
        "latest_fetched_at_utc": total_item.get("latest_fetched_at_utc"),
        "provider_count": len(providers),
        "providers": providers,
        "market_type_counts": market_type_counts,
        "latest_events": [dict(row) for row in latest_rows],
    }


def snapshot_to_dict(snapshot: MarketSnapshot) -> dict[str, Any]:
    return asdict(snapshot)

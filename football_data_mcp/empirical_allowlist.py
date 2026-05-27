"""
Empirical league allowlist: derive coverage from past settled records.

Replaces the hand-curated SETTLEMENT_COVERED_LEAGUES_DEFAULT (which under-counted
many leagues that dongqiudi actually does cover, e.g., 澳足总, 中乙, 阿后备, 挪甲,
解放者杯, 西女超, 美乙2 — all 6+ settled samples in production).

Rules:
- Any league with >=3 settled records in the past 60 days is "covered"
- Always include the curated default set as a baseline (hand-picked top leagues
  that we want to recommend in even before evidence accumulates)
- Cached 30 minutes; refreshed by daemon every cycle

Falls back gracefully:
- Empty DB → curated default only
- Cache miss → recompute on demand
"""
from __future__ import annotations

import logging
import os
import sqlite3
import time
from typing import Any

from football_data_mcp import learning_store

logger = logging.getLogger(__name__)

EMPIRICAL_MIN_SETTLED = int(os.getenv("FOOTBALL_DATA_EMPIRICAL_MIN_SETTLED", "3"))
EMPIRICAL_LOOKBACK_DAYS = int(os.getenv("FOOTBALL_DATA_EMPIRICAL_LOOKBACK_DAYS", "60"))
ALLOWLIST_CACHE_TTL = float(os.getenv("FOOTBALL_DATA_EMPIRICAL_CACHE_TTL_SECONDS", "1800"))  # 30 min

_CACHED_ALLOWLIST: frozenset[str] | None = None
_CACHED_AT: float = 0.0
_LAST_BREAKDOWN: dict[str, int] = {}


def get_empirical_settleable_leagues(
    *,
    db_path: str | None = None,
    min_settled: int | None = None,
    lookback_days: int | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """
    Return leagues empirically proven to be settleable (>=N settled records).

    Returns:
        {
          "leagues": frozenset[str],
          "league_counts": {league: settled_count},
          "min_settled": int,
          "lookback_days": int,
          "from_cache": bool,
        }
    """
    global _CACHED_ALLOWLIST, _CACHED_AT, _LAST_BREAKDOWN
    min_n = min_settled if min_settled is not None else EMPIRICAL_MIN_SETTLED
    lookback = lookback_days if lookback_days is not None else EMPIRICAL_LOOKBACK_DAYS

    if use_cache and _CACHED_ALLOWLIST is not None and (time.time() - _CACHED_AT) < ALLOWLIST_CACHE_TTL:
        return {
            "leagues": _CACHED_ALLOWLIST,
            "league_counts": dict(_LAST_BREAKDOWN),
            "min_settled": min_n,
            "lookback_days": lookback,
            "from_cache": True,
        }

    counts: dict[str, int] = {}
    try:
        with sqlite3.connect(db_path or learning_store.learning_db_path()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT league, COUNT(*) AS cnt
                FROM recommendation_records
                WHERE settlement_status = 'settled'
                  AND settled_at_utc >= datetime('now', '-{int(lookback)} days')
                  AND league IS NOT NULL
                  AND league != ''
                GROUP BY league
                """
            ).fetchall()
            for row in rows:
                counts[str(row["league"])] = int(row["cnt"])
    except Exception as exc:
        logger.warning("empirical allowlist: DB read failed: %s", exc)

    qualified = frozenset(
        league for league, count in counts.items() if count >= min_n
    )

    _CACHED_ALLOWLIST = qualified
    _CACHED_AT = time.time()
    _LAST_BREAKDOWN = counts

    return {
        "leagues": qualified,
        "league_counts": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "min_settled": min_n,
        "lookback_days": lookback,
        "from_cache": False,
    }


def merged_allowlist(
    curated_default: frozenset[str] | set[str],
    *,
    db_path: str | None = None,
) -> frozenset[str]:
    """
    Combine the curated default allowlist with empirically-proven leagues.

    A league is allowed if EITHER:
    - It's in the curated default (top mainstream leagues we want anyway), OR
    - It has >=3 settled records in past 60 days (empirical proof of coverage)

    This is the actual production allowlist used by the daemon.
    """
    empirical = get_empirical_settleable_leagues(db_path=db_path)
    return frozenset(curated_default) | empirical["leagues"]


def invalidate_cache() -> None:
    """Force recompute on next call (after a fresh batch of settlements)."""
    global _CACHED_ALLOWLIST, _CACHED_AT
    _CACHED_ALLOWLIST = None
    _CACHED_AT = 0.0

"""
Database janitor: periodic cleanup of bad / unsettleable / orphaned data.

Bad data taxonomy (worst → least severe):
0. HARD_EXCLUDED_COMPETITION: product-level banned categories such as
   reserve/youth/women/friendlies/lower-tier regional cups. Hard-delete from
   model inputs because they are intentionally out of scope.
1. ORPHANED: records with no match_id AND no kickoff_utc — cannot ever be
   matched to anything. Safe to hard-delete.
2. UNSETTLEABLE_STALE: kickoff >48h ago, still 'open', from leagues that
   no public source covers. Mark as unsettleable, then archive after grace.
3. DUPLICATE_IGNORED: records that lost the dedup race. Hard-delete after
   grace period (default 7 days) once we're confident they're truly dead.
4. STALE_CALIBRATION_BUCKETS: buckets with 0 samples that survived a recompute
   (happens when records get marked unsettleable and bucket recompute skipped).
5. EXPIRED_SHADOW: shadow predictions older than retention window.

The janitor:
- Always supports dry_run mode (preview without changes)
- Logs everything for audit
- Reports per-category counts
- Won't touch normal 'settled' records (those are the gold)
- Will delete settled records only when the competition itself is hard-excluded
- Won't touch the 'strategy_state' table

Periodic run from auto_learning daemon (every 6h by default).
"""
from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from football_data_mcp import competition_policy, learning_store, snapshot_store

logger = logging.getLogger(__name__)

# Retention / grace periods (env-overridable)
ORPHAN_GRACE_HOURS = int(os.getenv("FOOTBALL_DATA_JANITOR_ORPHAN_GRACE_HOURS", "1"))
UNSETTLEABLE_THRESHOLD_HOURS = int(os.getenv("FOOTBALL_DATA_JANITOR_UNSETTLEABLE_HOURS", "48"))
# Default 0 → delete unsettleable records immediately when detected.
# They contribute no analytical value (no scores will ever arrive) and only
# pollute the prediction ledger / KPIs / UI. Set to >0 days for archival.
UNSETTLEABLE_ARCHIVE_DAYS = int(os.getenv("FOOTBALL_DATA_JANITOR_UNSETTLEABLE_ARCHIVE_DAYS", "0"))
DUPLICATE_GRACE_DAYS = int(os.getenv("FOOTBALL_DATA_JANITOR_DUPLICATE_GRACE_DAYS", "7"))
SHADOW_RETENTION_DAYS = int(os.getenv("FOOTBALL_DATA_JANITOR_SHADOW_RETENTION_DAYS", "90"))
SQLITE_DELETE_BATCH_SIZE = 500


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or learning_store.learning_db_path()
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ─── Category 1: orphaned records (no match_id + no kickoff) ──────────────────

def _find_orphaned(conn: sqlite3.Connection, *, table: str) -> list[dict[str, Any]]:
    cutoff = (_now_utc() - timedelta(hours=ORPHAN_GRACE_HOURS)).isoformat()
    rows = conn.execute(
        f"""
        SELECT id, league, home_team, away_team, match_id, kickoff_utc, created_at_utc
        FROM {table}
        WHERE (match_id IS NULL OR match_id = '')
          AND (kickoff_utc IS NULL OR kickoff_utc = '')
          AND created_at_utc < ?
        """,
        (cutoff,),
    ).fetchall()
    return [dict(r) for r in rows]


# ─── Category 2: stale opens (kickoff >48h ago, still 'open') ────────────────

def _find_stale_opens(conn: sqlite3.Connection, *, table: str) -> list[dict[str, Any]]:
    cutoff = (_now_utc() - timedelta(hours=UNSETTLEABLE_THRESHOLD_HOURS)).isoformat()
    rows = conn.execute(
        f"""
        SELECT id, league, home_team, away_team, match_id, kickoff_utc
        FROM {table}
        WHERE settlement_status = 'open'
          AND kickoff_utc IS NOT NULL
          AND kickoff_utc != ''
          AND kickoff_utc < ?
        """,
        (cutoff,),
    ).fetchall()
    return [dict(r) for r in rows]


# ─── Category 3: long-archived unsettleable (>30 days) ───────────────────────

def _find_archived_unsettleable(conn: sqlite3.Connection, *, table: str) -> list[dict[str, Any]]:
    cutoff = (_now_utc() - timedelta(days=UNSETTLEABLE_ARCHIVE_DAYS)).isoformat()
    rows = conn.execute(
        f"""
        SELECT id, league, home_team, away_team, kickoff_utc, settled_at_utc
        FROM {table}
        WHERE settlement_status = 'unsettleable'
          AND COALESCE(settled_at_utc, '') < ?
        """,
        (cutoff,),
    ).fetchall()
    return [dict(r) for r in rows]


# ─── Category 4: duplicate_ignored older than grace period ───────────────────

def _find_archived_duplicates(conn: sqlite3.Connection, *, table: str) -> list[dict[str, Any]]:
    cutoff = (_now_utc() - timedelta(days=DUPLICATE_GRACE_DAYS)).isoformat()
    rows = conn.execute(
        f"""
        SELECT id, league, home_team, away_team, kickoff_utc, created_at_utc
        FROM {table}
        WHERE settlement_status = 'duplicate_ignored'
          AND created_at_utc < ?
        """,
        (cutoff,),
    ).fetchall()
    return [dict(r) for r in rows]


# ─── Category 5: stale shadow predictions ────────────────────────────────────

def _find_stale_shadow(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    cutoff = (_now_utc() - timedelta(days=SHADOW_RETENTION_DAYS)).isoformat()
    rows = conn.execute(
        """
        SELECT id, league, home_team, away_team, kickoff_utc, created_at_utc, settlement_status
        FROM shadow_prediction_records
        WHERE created_at_utc < ?
        """,
        (cutoff,),
    ).fetchall()
    return [dict(r) for r in rows]


# ─── Category 6: empty calibration buckets ───────────────────────────────────

def _find_empty_calibration_buckets(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, market, league_bucket, line_bucket, odds_bucket, probability_bucket, sample_count
        FROM calibration_buckets
        WHERE sample_count <= 0
        """
    ).fetchall()
    return [dict(r) for r in rows]


def _find_hard_excluded_learning_rows(conn: sqlite3.Connection, *, table: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
        SELECT id, league, home_team, away_team, match_id, kickoff_utc,
               kickoff_utc_plus_8, settlement_status, created_at_utc
        FROM {table}
        """
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        reason = competition_policy.match_hard_exclusion_reason(item)
        if reason:
            item["hard_exclusion_reason"] = reason
            out.append(item)
    return out


def _find_hard_excluded_snapshot_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, provider, event_id, league, home_team, away_team,
               kickoff_utc, bookmaker, market_type, fetched_at_utc
        FROM market_snapshots
        """
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        reason = competition_policy.match_hard_exclusion_reason(item)
        if reason:
            item["hard_exclusion_reason"] = reason
            out.append(item)
    return out


def _batched(items: list[Any], batch_size: int = SQLITE_DELETE_BATCH_SIZE) -> list[list[Any]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def _delete_ids(conn: sqlite3.Connection, *, table: str, ids: list[int]) -> int:
    if not ids:
        return 0
    deleted = 0
    for batch in _batched(ids):
        placeholders = ",".join("?" for _ in batch)
        cursor = conn.execute(f"DELETE FROM {table} WHERE id IN ({placeholders})", batch)
        deleted += max(0, int(cursor.rowcount or 0))
    return deleted


def _delete_notification_deliveries_for_learning_rows(
    conn: sqlite3.Connection,
    *,
    table: str,
    ids: list[int],
) -> int:
    if not ids:
        return 0
    source = "recommendation" if table == "recommendation_records" else "shadow_prediction"
    ledger_ids = [f"{source}:{row_id}" for row_id in ids]
    deleted = 0
    for batch in _batched(ledger_ids):
        placeholders = ",".join("?" for _ in batch)
        cursor = conn.execute(
            f"DELETE FROM notification_deliveries WHERE ledger_id IN ({placeholders})",
            batch,
        )
        deleted += max(0, int(cursor.rowcount or 0))
    return deleted


def _purge_hard_excluded_learning_rows(
    conn: sqlite3.Connection,
    report: dict[str, Any],
    *,
    dry_run: bool,
) -> dict[str, int]:
    deleted_records = 0
    deleted_deliveries = 0
    for table in ("recommendation_records", "shadow_prediction_records"):
        rows = _find_hard_excluded_learning_rows(conn, table=table)
        report["categories"][f"{table}.hard_excluded_competitions"] = {
            "action": "hard_delete",
            "count": len(rows),
            "by_reason": _group_count(rows, "hard_exclusion_reason"),
            "leagues": _group_count(rows, "league"),
            "sample": rows[:3],
        }
        report["totals"]["inspected"] += len(rows)
        if not dry_run and rows:
            ids = [int(row["id"]) for row in rows]
            delivery_count = _delete_notification_deliveries_for_learning_rows(
                conn,
                table=table,
                ids=ids,
            )
            row_count = _delete_ids(conn, table=table, ids=ids)
            deleted_records += row_count
            deleted_deliveries += delivery_count
            report["totals"]["deleted"] += row_count + delivery_count
    if deleted_deliveries:
        report["categories"]["notification_deliveries.hard_excluded_competitions"] = {
            "action": "hard_delete",
            "count": deleted_deliveries,
        }
    return {
        "records_deleted": deleted_records,
        "notification_deliveries_deleted": deleted_deliveries,
    }


def run_janitor(
    *,
    db_path: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Inspect the DB for bad data, optionally clean it up.

    Returns a structured report of what was found / removed.
    Categories operated on:
    - hard_excluded_competitions: HARD DELETE, including settled contaminated rows
    - orphaned (no match_id + no kickoff): HARD DELETE
    - stale_opens (kickoff>48h ago, still open): MARK unsettleable
    - archived_unsettleable (>30d old): HARD DELETE
    - archived_duplicates (>7d old): HARD DELETE
    - stale_shadow (>90d old): HARD DELETE
    - empty_calibration_buckets: HARD DELETE
    """
    report: dict[str, Any] = {
        "dry_run": dry_run,
        "executed_at_utc": _now_utc().isoformat(),
        "categories": {},
        "totals": {"inspected": 0, "marked": 0, "deleted": 0},
        "config": {
            "orphan_grace_hours": ORPHAN_GRACE_HOURS,
            "unsettleable_threshold_hours": UNSETTLEABLE_THRESHOLD_HOURS,
            "unsettleable_archive_days": UNSETTLEABLE_ARCHIVE_DAYS,
            "duplicate_grace_days": DUPLICATE_GRACE_DAYS,
            "shadow_retention_days": SHADOW_RETENTION_DAYS,
        },
    }

    with _connect(db_path) as conn:
        learning_store.ensure_schema(conn)

        _purge_hard_excluded_learning_rows(conn, report, dry_run=dry_run)

        # 1. Orphans - hard delete
        for table in ("recommendation_records", "shadow_prediction_records"):
            orphans = _find_orphaned(conn, table=table)
            report["categories"][f"{table}.orphaned"] = {
                "action": "hard_delete",
                "count": len(orphans),
                "sample": orphans[:3],
            }
            report["totals"]["inspected"] += len(orphans)
            if not dry_run and orphans:
                ids = [r["id"] for r in orphans]
                placeholders = ",".join("?" for _ in ids)
                conn.execute(f"DELETE FROM {table} WHERE id IN ({placeholders})", ids)
                report["totals"]["deleted"] += len(orphans)

        # 2. Stale opens → hard delete (unsettleable rows have no analytical value)
        for table in ("recommendation_records", "shadow_prediction_records"):
            stale = _find_stale_opens(conn, table=table)
            report["categories"][f"{table}.stale_opens"] = {
                "action": "hard_delete",
                "count": len(stale),
                "leagues": _group_count(stale, "league"),
                "sample": stale[:3],
            }
            report["totals"]["inspected"] += len(stale)
            if not dry_run and stale:
                ids = [r["id"] for r in stale]
                placeholders = ",".join("?" for _ in ids)
                conn.execute(
                    f"DELETE FROM {table} WHERE id IN ({placeholders})",
                    ids,
                )
                report["totals"]["deleted"] += len(stale)

        # 3. Archived unsettleable - hard delete (long-tail)
        for table in ("recommendation_records", "shadow_prediction_records"):
            archived = _find_archived_unsettleable(conn, table=table)
            report["categories"][f"{table}.archived_unsettleable"] = {
                "action": "hard_delete",
                "count": len(archived),
                "leagues": _group_count(archived, "league"),
                "sample": archived[:3],
            }
            report["totals"]["inspected"] += len(archived)
            if not dry_run and archived:
                ids = [r["id"] for r in archived]
                placeholders = ",".join("?" for _ in ids)
                conn.execute(f"DELETE FROM {table} WHERE id IN ({placeholders})", ids)
                report["totals"]["deleted"] += len(archived)

        # 4. Archived duplicates
        for table in ("recommendation_records",):  # shadow doesn't use duplicate_ignored
            dups = _find_archived_duplicates(conn, table=table)
            report["categories"][f"{table}.archived_duplicates"] = {
                "action": "hard_delete",
                "count": len(dups),
                "sample": dups[:3],
            }
            report["totals"]["inspected"] += len(dups)
            if not dry_run and dups:
                ids = [r["id"] for r in dups]
                placeholders = ",".join("?" for _ in ids)
                conn.execute(f"DELETE FROM {table} WHERE id IN ({placeholders})", ids)
                report["totals"]["deleted"] += len(dups)

        # 5. Stale shadow predictions
        shadow_stale = _find_stale_shadow(conn)
        report["categories"]["shadow_prediction_records.aged_out"] = {
            "action": "hard_delete",
            "count": len(shadow_stale),
            "by_status": _group_count(shadow_stale, "settlement_status"),
            "sample": shadow_stale[:3],
        }
        report["totals"]["inspected"] += len(shadow_stale)
        if not dry_run and shadow_stale:
            ids = [r["id"] for r in shadow_stale]
            placeholders = ",".join("?" for _ in ids)
            conn.execute(f"DELETE FROM shadow_prediction_records WHERE id IN ({placeholders})", ids)
            report["totals"]["deleted"] += len(shadow_stale)

        # 6. Empty calibration buckets
        empties = _find_empty_calibration_buckets(conn)
        report["categories"]["calibration_buckets.empty"] = {
            "action": "hard_delete",
            "count": len(empties),
            "sample": empties[:3],
        }
        report["totals"]["inspected"] += len(empties)
        if not dry_run and empties:
            ids = [r["id"] for r in empties]
            placeholders = ",".join("?" for _ in ids)
            conn.execute(f"DELETE FROM calibration_buckets WHERE id IN ({placeholders})", ids)
            report["totals"]["deleted"] += len(empties)

        if not dry_run:
            conn.commit()
            # Run VACUUM only when something was deleted, and only periodically
            # (VACUUM rewrites the entire DB file, expensive on large DBs)
            if report["totals"]["deleted"] >= 50:
                try:
                    conn.execute("VACUUM")
                    report["vacuum_performed"] = True
                except Exception as exc:
                    report["vacuum_performed"] = False
                    report["vacuum_error"] = str(exc)

    logger.info(
        "db_janitor: dry_run=%s inspected=%d marked=%d deleted=%d",
        dry_run,
        report["totals"]["inspected"],
        report["totals"]["marked"],
        report["totals"]["deleted"],
    )
    return report


def _connect_snapshot(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or snapshot_store.snapshot_db_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def purge_hard_excluded_competition_records(
    *,
    learning_db_path: str | None = None,
    snapshot_db_path: str | None = None,
    dry_run: bool = True,
    recompute_after: bool = True,
) -> dict[str, Any]:
    """Purge product-level banned competitions from historical model data.

    This is intentionally stronger than the normal janitor: hard-excluded
    competitions are out of modeling scope, so even settled rows are removed and
    calibration/strategy aggregates are rebuilt afterward.
    """
    report: dict[str, Any] = {
        "dry_run": dry_run,
        "executed_at_utc": _now_utc().isoformat(),
        "categories": {},
        "totals": {"inspected": 0, "marked": 0, "deleted": 0},
        "db_paths": {
            "learning": learning_db_path or learning_store.learning_db_path(),
            "snapshots": snapshot_db_path or snapshot_store.snapshot_db_path(),
        },
    }
    learning_result = {"records_deleted": 0, "notification_deliveries_deleted": 0}
    with _connect(learning_db_path) as conn:
        learning_store.ensure_schema(conn)
        learning_result = _purge_hard_excluded_learning_rows(conn, report, dry_run=dry_run)
        if not dry_run:
            conn.commit()

    if not dry_run and recompute_after and learning_result["records_deleted"] > 0:
        report["learning_recompute"] = {
            "calibration": learning_store.recompute_calibration(db_path=learning_db_path),
            "strategy_states": learning_store.update_all_market_strategy_states(db_path=learning_db_path),
        }

    with _connect_snapshot(snapshot_db_path) as conn:
        snapshot_store.ensure_schema(conn)
        rows = _find_hard_excluded_snapshot_rows(conn)
        report["categories"]["market_snapshots.hard_excluded_competitions"] = {
            "action": "hard_delete",
            "count": len(rows),
            "by_reason": _group_count(rows, "hard_exclusion_reason"),
            "leagues": _group_count(rows, "league"),
            "sample": rows[:3],
        }
        report["totals"]["inspected"] += len(rows)
        if not dry_run and rows:
            deleted = _delete_ids(conn, table="market_snapshots", ids=[int(row["id"]) for row in rows])
            report["totals"]["deleted"] += deleted
            conn.commit()

    return report


def _group_count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        k = str(r.get(key) or "(empty)")
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))

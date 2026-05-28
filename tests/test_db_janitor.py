"""Unit tests for db_janitor: bad data detection + cleanup."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from football_data_mcp import db_janitor, learning_store


def _seed_db(db_path: str) -> None:
    """Create schema + insert a controlled mix of records."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    learning_store.ensure_schema(conn)
    conn.commit()
    now = datetime.now(timezone.utc)

    def iso(dt: datetime) -> str:
        return dt.isoformat()

    # 1. Orphaned record (no match_id, no kickoff, old enough to be past grace)
    conn.execute(
        """
        INSERT INTO recommendation_records (
            record_key, run_id, tool, mode, target_market, league,
            home_team, away_team, market, selection, risk_flags_json,
            caution_flags_json, raw_json, settlement_status, created_at_utc
        ) VALUES ('rec:orphan1', 'r', 't', 'm', 'asian_handicap', 'L1',
                  'A', 'B', 'asian_handicap', 'A -0.5', '[]', '[]', '{}',
                  'open', ?)
        """,
        (iso(now - timedelta(hours=24)),),
    )
    # 2. Stale open (kickoff 50h ago, still open)
    conn.execute(
        """
        INSERT INTO recommendation_records (
            record_key, run_id, tool, mode, target_market, match_id, league,
            home_team, away_team, kickoff_utc, market, selection,
            risk_flags_json, caution_flags_json, raw_json, settlement_status, created_at_utc
        ) VALUES ('rec:stale1', 'r', 't', 'm', 'asian_handicap', 'MID-1',
                  'L2', 'C', 'D', ?, 'asian_handicap', 'C -0.5', '[]', '[]',
                  '{}', 'open', ?)
        """,
        (iso(now - timedelta(hours=50)), iso(now - timedelta(hours=52))),
    )
    # 3. Old archived unsettleable (45 days old)
    conn.execute(
        """
        INSERT INTO recommendation_records (
            record_key, run_id, tool, mode, target_market, match_id, league,
            home_team, away_team, kickoff_utc, market, selection,
            risk_flags_json, caution_flags_json, raw_json,
            settlement_status, settled_at_utc, created_at_utc
        ) VALUES ('rec:archived1', 'r', 't', 'm', 'asian_handicap', 'MID-2',
                  'L3', 'E', 'F', ?, 'asian_handicap', 'E +0.5', '[]', '[]',
                  '{}', 'unsettleable', ?, ?)
        """,
        (
            iso(now - timedelta(days=46)),
            iso(now - timedelta(days=45)),
            iso(now - timedelta(days=46)),
        ),
    )
    # 4. Settled record — should NEVER be touched
    conn.execute(
        """
        INSERT INTO recommendation_records (
            record_key, run_id, tool, mode, target_market, match_id, league,
            home_team, away_team, kickoff_utc, market, selection, decimal_odds,
            risk_flags_json, caution_flags_json, raw_json,
            settlement_status, home_score, away_score, hit, settled_at_utc, created_at_utc
        ) VALUES ('rec:settled1', 'r', 't', 'm', 'asian_handicap', 'MID-3',
                  'L4', 'G', 'H', ?, 'asian_handicap', 'G -0.5', 1.85,
                  '[]', '[]', '{}', 'settled', 2, 1, 1, ?, ?)
        """,
        (
            iso(now - timedelta(days=60)),
            iso(now - timedelta(days=59)),
            iso(now - timedelta(days=60)),
        ),
    )
    # 5. Recent open (NOT stale) — should NEVER be touched
    conn.execute(
        """
        INSERT INTO recommendation_records (
            record_key, run_id, tool, mode, target_market, match_id, league,
            home_team, away_team, kickoff_utc, market, selection,
            risk_flags_json, caution_flags_json, raw_json,
            settlement_status, created_at_utc
        ) VALUES ('rec:recent1', 'r', 't', 'm', 'asian_handicap', 'MID-4',
                  'L5', 'I', 'J', ?, 'asian_handicap', 'I +0.5', '[]', '[]',
                  '{}', 'open', ?)
        """,
        (iso(now + timedelta(hours=12)), iso(now - timedelta(hours=1))),
    )
    # 6. Empty calibration bucket
    conn.execute(
        """
        INSERT INTO calibration_buckets (
            market, league_bucket, line_bucket, odds_bucket, probability_bucket,
            sample_count, hit_count, updated_at_utc, raw_json
        ) VALUES ('asian_handicap', 'ALL', 'line:none', 'odds:1.80-1.90',
                  'prob:0.60-0.65', 0, 0, ?, '{}')
        """,
        (iso(now - timedelta(days=1)),),
    )
    # 7. Old shadow prediction (95 days)
    conn.execute(
        """
        INSERT INTO shadow_prediction_records (
            shadow_key, run_id, tool, mode, target_market, decision, match_id,
            league, home_team, away_team, kickoff_utc, market, selection,
            quality_json, thresholds_json, raw_json,
            settlement_status, created_at_utc
        ) VALUES ('sh:old1', 'r', 't', 'm', 'asian_handicap', 'accepted', 'M-OLD',
                  'L6', 'K', 'L', ?, 'asian_handicap', 'K -0.5', '{}', '{}',
                  '{}', 'settled', ?)
        """,
        (
            iso(now - timedelta(days=95)),
            iso(now - timedelta(days=94)),
        ),
    )
    conn.commit()
    conn.close()


def test_dry_run_reports_findings_without_changes(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    _seed_db(db_path)
    report = db_janitor.run_janitor(db_path=db_path, dry_run=True)

    # Should report findings
    assert report["dry_run"] is True
    categories = report["categories"]
    assert categories["recommendation_records.orphaned"]["count"] == 1
    assert categories["recommendation_records.stale_opens"]["count"] == 1
    assert categories["recommendation_records.archived_unsettleable"]["count"] == 1
    assert categories["calibration_buckets.empty"]["count"] == 1
    assert categories["shadow_prediction_records.aged_out"]["count"] == 1

    # Nothing should be deleted/marked
    assert report["totals"]["deleted"] == 0
    assert report["totals"]["marked"] == 0

    # Confirm DB unchanged
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM recommendation_records").fetchone()[0] == 5
    conn.close()


def test_executes_cleanup_with_correct_actions(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    _seed_db(db_path)
    report = db_janitor.run_janitor(db_path=db_path, dry_run=False)

    assert report["dry_run"] is False
    # All categories are now hard-delete (unsettleable rows have no value):
    # 1 orphan + 1 stale_open + 1 archived_unsettleable + 1 empty bucket + 1 old shadow
    assert report["totals"]["deleted"] == 5
    assert report["totals"]["marked"] == 0  # nothing is just "marked" anymore

    conn = sqlite3.connect(db_path)
    # Total should be 5 - 3 deletions in recommendation_records = 2
    assert conn.execute("SELECT COUNT(*) FROM recommendation_records").fetchone()[0] == 2

    # Settled record must still exist
    row = conn.execute("SELECT settlement_status FROM recommendation_records WHERE record_key = 'rec:settled1'").fetchone()
    assert row is not None and row[0] == "settled"

    # Recent open must still exist
    row = conn.execute("SELECT settlement_status FROM recommendation_records WHERE record_key = 'rec:recent1'").fetchone()
    assert row is not None and row[0] == "open"

    # Stale open is now deleted (not marked)
    row = conn.execute("SELECT settlement_status FROM recommendation_records WHERE record_key = 'rec:stale1'").fetchone()
    assert row is None

    # Orphan and archived_unsettleable gone
    assert conn.execute("SELECT COUNT(*) FROM recommendation_records WHERE record_key IN ('rec:orphan1', 'rec:archived1')").fetchone()[0] == 0

    # Empty bucket gone
    assert conn.execute("SELECT COUNT(*) FROM calibration_buckets").fetchone()[0] == 0

    # Old shadow gone
    assert conn.execute("SELECT COUNT(*) FROM shadow_prediction_records").fetchone()[0] == 0
    conn.close()


def test_janitor_never_touches_settled_records(tmp_path):
    """The single most important invariant."""
    db_path = str(tmp_path / "learning.sqlite3")
    _seed_db(db_path)

    # Run twice in a row — settled record should still be there
    db_janitor.run_janitor(db_path=db_path, dry_run=False)
    db_janitor.run_janitor(db_path=db_path, dry_run=False)

    conn = sqlite3.connect(db_path)
    settled_count = conn.execute(
        "SELECT COUNT(*) FROM recommendation_records WHERE settlement_status = 'settled'"
    ).fetchone()[0]
    assert settled_count == 1, "settled records must never be deleted"
    conn.close()


def test_janitor_idempotent(tmp_path):
    """Second consecutive run on cleaned DB should be a no-op."""
    db_path = str(tmp_path / "learning.sqlite3")
    _seed_db(db_path)
    first = db_janitor.run_janitor(db_path=db_path, dry_run=False)
    second = db_janitor.run_janitor(db_path=db_path, dry_run=False)

    assert first["totals"]["deleted"] > 0
    assert second["totals"]["deleted"] == 0
    assert second["totals"]["marked"] == 0


def test_report_groups_leagues_for_visibility(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    _seed_db(db_path)
    report = db_janitor.run_janitor(db_path=db_path, dry_run=True)
    stale_info = report["categories"]["recommendation_records.stale_opens"]
    # Should include league of the stale open
    assert "L2" in stale_info["leagues"]
    assert stale_info["leagues"]["L2"] == 1

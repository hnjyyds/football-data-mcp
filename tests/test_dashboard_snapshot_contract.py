"""End-to-end test: dashboard_snapshot output passes the contract normalizer."""
from __future__ import annotations

from football_data_mcp import sources
from football_data_mcp.dashboard_contract import normalize_dashboard_snapshot


def test_dashboard_snapshot_returns_normalized_contract(monkeypatch, tmp_path):
    """The live snapshot output should already be in normalized shape."""
    # Stub heavy collaborators so the test stays fast.
    monkeypatch.setattr(sources, "_ensure_fdo_index_warm", lambda: None)
    monkeypatch.setattr(sources, "_ensure_dongqiudi_logo_cache_warm", lambda: None)

    # Use an empty DB so no real state is required.
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")

    snap = sources.dashboard_snapshot(db_path=db_path, market_db_path=market_db_path)

    # Idempotent: feeding the snapshot through the normalizer again yields the
    # same shape (proves the wiring already applied it).
    renormalized = normalize_dashboard_snapshot(snap)
    for key in (
        "auto_learning_state",
        "latest_validation",
        "buckets",
        "learning_events",
        "backtest_curve",
        "source_health",
    ):
        assert key in snap
        assert snap[key] == renormalized[key], f"{key} not pre-normalized in dashboard_snapshot"

    # Specific invariants the frontend depends on
    als = snap["auto_learning_state"]
    assert isinstance(als, dict)
    assert isinstance(als["enabled"], bool)
    assert isinstance(als["run_count"], int)
    # last_error must be str | None, never empty string
    assert als["last_error"] is None or isinstance(als["last_error"], str)
    if isinstance(als["last_error"], str):
        assert als["last_error"] != ""

    # buckets is always a list (never None)
    assert isinstance(snap["buckets"], list)
    # backtest_curve.points always exists as a list
    assert "points" in snap["backtest_curve"]
    assert isinstance(snap["backtest_curve"]["points"], list)
    # source_health is always a dict, even if empty
    assert isinstance(snap["source_health"], dict)

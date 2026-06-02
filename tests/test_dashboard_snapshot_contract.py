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
    assert snap["model_failure_diagnostics"]["status"] == "insufficient_sample"
    assert isinstance(snap["model_failure_diagnostics"]["drivers"], list)


def test_dashboard_snapshot_does_not_trigger_external_enrichment_warmers_by_default(monkeypatch, tmp_path):
    """Dashboard rendering must stay read-only; external refresh belongs to daemon/jobs."""
    monkeypatch.delenv("FOOTBALL_DATA_DASHBOARD_BACKGROUND_ENRICHMENT", raising=False)

    def unexpected_warm() -> None:
        raise AssertionError("dashboard_snapshot must not start external enrichment warmers by default")

    monkeypatch.setattr(sources, "_ensure_fdo_index_warm", unexpected_warm)
    monkeypatch.setattr(sources, "_ensure_dongqiudi_logo_cache_warm", unexpected_warm)

    snap = sources.dashboard_snapshot(
        db_path=str(tmp_path / "learning.sqlite3"),
        market_db_path=str(tmp_path / "snapshots.sqlite3"),
    )

    assert snap["policy"]["read_only"] is True


def test_dashboard_snapshot_can_explicitly_warm_enrichment_indexes(monkeypatch, tmp_path):
    """Explicit refresh flows may opt in to background enrichment warmers."""
    calls: list[str] = []
    monkeypatch.setattr(sources, "_ensure_fdo_index_warm", lambda: calls.append("fdo"))
    monkeypatch.setattr(sources, "_ensure_dongqiudi_logo_cache_warm", lambda: calls.append("dongqiudi"))

    sources.dashboard_snapshot(
        db_path=str(tmp_path / "learning.sqlite3"),
        market_db_path=str(tmp_path / "snapshots.sqlite3"),
        allow_background_enrichment_refresh=True,
    )

    assert calls == ["fdo", "dongqiudi"]

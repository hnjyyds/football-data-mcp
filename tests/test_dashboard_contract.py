"""Contract tests for the /api/dashboard snapshot.

These tests pin down the JSON shape the dashboard frontend depends on.
Adding/removing a field here should be a deliberate, reviewable change
because the frontend's runtime schema validator and TypeScript types
mirror this contract.
"""
from __future__ import annotations

from typing import Any

import pytest

from football_data_mcp.dashboard_contract import (
    normalize_dashboard_snapshot,
    AutoLearningState,
    LatestValidation,
    CalibrationBucketRow,
    LearningEvent,
    LineupSide,
    OddsTrendPoint,
    BacktestCurvePoint,
    DashboardSourceHealth,
)


def _minimal_snapshot() -> dict[str, Any]:
    return {
        "status": "ok",
        "tool": "dashboard_snapshot",
        "generated_at_utc": "2026-05-28T07:00:00+00:00",
        "db_path": "/data/learning.sqlite3",
        "kpis": {
            "open_records": 0,
            "settled_records": 0,
            "tracked_only_records": 0,
            "duplicate_ignored_records": 0,
            "asian_pick_count": 0,
            "observation_count": 0,
            "calibration_bucket_count": 0,
            "strategy_sample_count": 0,
            "live_calibration_active": False,
        },
        "prediction_kpis": {
            "total_count": 0,
            "recommended_count": 0,
            "observation_count": 0,
            "open_count": 0,
            "settled_count": 0,
            "hit_count": 0,
            "miss_count": 0,
            "hit_rate": None,
            "roi": None,
        },
    }


class TestAutoLearningState:
    def test_present_fields_pass_through(self):
        raw = {
            "auto_learning_state": {
                "enabled": True,
                "run_count": 42,
                "last_error": "boom",
                "last_finished_at_utc": "2026-05-28T06:59:00+00:00",
                "current_step": "asian_shortlist",
                "consecutive_empty_cycles": 3,
                "interval_seconds": 120,
                "cycle_timeout_seconds": 300,
                "analysis_timeout_seconds": 45,
                "last_result_summary": {
                    "asian_total_candidates": 6,
                    "asian_record_count": 0,
                    "asian_shadow_prediction_record_count": 5,
                },
            },
        }
        snap = {**_minimal_snapshot(), **raw}
        out = normalize_dashboard_snapshot(snap)
        assert out["auto_learning_state"] is not None
        als: AutoLearningState = out["auto_learning_state"]
        assert als["enabled"] is True
        assert als["run_count"] == 42
        assert als["last_error"] == "boom"
        assert als["consecutive_empty_cycles"] == 3
        assert als["interval_seconds"] == 120
        assert als["cycle_timeout_seconds"] == 300
        assert als["analysis_timeout_seconds"] == 45
        assert als["last_result_summary"]["asian_total_candidates"] == 6

    def test_missing_state_defaults_to_disabled(self):
        out = normalize_dashboard_snapshot(_minimal_snapshot())
        als = out["auto_learning_state"]
        assert als is not None
        assert als["enabled"] is False
        assert als["run_count"] == 0
        assert als["last_error"] is None
        assert als["consecutive_empty_cycles"] == 0

    def test_last_error_coerced_to_string_or_none(self):
        snap = _minimal_snapshot()
        snap["auto_learning_state"] = {"last_error": ""}
        out = normalize_dashboard_snapshot(snap)
        # Empty string should become None — the frontend uses truthiness to decide
        assert out["auto_learning_state"]["last_error"] is None


class TestLatestValidation:
    def test_normalizes_fields(self):
        snap = {
            **_minimal_snapshot(),
            "latest_validation": {
                "method": "holdout_v2",
                "automation_readiness": "not_ready",
                "beats_market": False,
                "log_loss_model": 0.61,
                "log_loss_market": 0.59,
                "log_loss_diff": 0.02,
                "brier_model": 0.24,
                "brier_market": 0.23,
                "roi": -0.05,
                "bet_count": 0,
                "evaluated_count": 84,
                "created_at_utc": "2026-05-28T04:18:00+00:00",
            },
        }
        out = normalize_dashboard_snapshot(snap)
        lv: LatestValidation = out["latest_validation"]
        assert lv is not None
        assert lv["method"] == "holdout_v2"
        assert lv["automation_readiness"] == "not_ready"
        assert lv["beats_market"] is False
        assert lv["bet_count"] == 0
        assert lv["evaluated_count"] == 84

    def test_missing_validation_is_null(self):
        out = normalize_dashboard_snapshot(_minimal_snapshot())
        assert out["latest_validation"] is None


class TestCalibrationBuckets:
    def test_normalizes_buckets_with_band_or_probability_bucket(self):
        snap = {
            **_minimal_snapshot(),
            "buckets": [
                {
                    "calibration_band": "0.40-0.45",
                    "sample_count": 206,
                    "hit_count": 98,
                    "hit_rate": 0.475728,
                    "roi": -0.0286,
                },
                {
                    "probability_bucket": "prob:0.35-0.40",
                    "sample_count": 64,
                    "hit_count": 27,
                    "hit_rate": 0.421875,
                    "roi": -0.1084,
                },
            ],
        }
        out = normalize_dashboard_snapshot(snap)
        buckets: list[CalibrationBucketRow] = out["buckets"]
        assert len(buckets) == 2
        # Both representations should normalize to a `band` field
        assert buckets[0]["band"] == "0.40-0.45"
        assert buckets[1]["band"] == "prob:0.35-0.40"
        assert buckets[0]["sample_count"] == 206
        assert buckets[0]["roi"] == pytest.approx(-0.0286)

    def test_buckets_default_empty_list(self):
        out = normalize_dashboard_snapshot(_minimal_snapshot())
        assert out["buckets"] == []


class TestLearningEvents:
    def test_event_canonicalizes_to_title_detail_at(self):
        snap = {
            **_minimal_snapshot(),
            "learning_events": [
                {
                    "title": "策略状态刷新",
                    "detail": "live_calibration_active",
                    "at_utc": "2026-05-28T07:00:54+00:00",
                },
                # Older schema used `label` + `description` + `timestamp` — normalize them
                {
                    "label": "自动结算",
                    "description": "明星FC vs AMSG",
                    "timestamp": "2026-05-28T04:37:31+00:00",
                },
                # An event missing all keys should be dropped
                {"unrelated": 1},
            ],
        }
        out = normalize_dashboard_snapshot(snap)
        events: list[LearningEvent] = out["learning_events"]
        assert len(events) == 2
        assert events[0]["title"] == "策略状态刷新"
        assert events[0]["at_utc"] == "2026-05-28T07:00:54+00:00"
        assert events[1]["title"] == "自动结算"
        assert events[1]["detail"] == "明星FC vs AMSG"
        assert events[1]["at_utc"] == "2026-05-28T04:37:31+00:00"


class TestSourceHealth:
    def test_normalizes_provider_aliases(self):
        snap = {
            **_minimal_snapshot(),
            "source_health": {
                "football_data": {"status": "ok", "checked_at_utc": "2026-05-28T07:00:00+00:00"},
                "leisu": {"status": "blocked", "error": "leisu_access_forbidden"},
                "dongqiudi_schedule": {"status": "ok"},
                "odds_api": {"status": "rate_limited"},
            },
        }
        out = normalize_dashboard_snapshot(snap)
        sh: DashboardSourceHealth = out["source_health"]
        assert sh["football_data"]["status"] == "ok"
        assert sh["leisu"]["status"] == "blocked"
        assert sh["leisu"]["error"] == "leisu_access_forbidden"
        # Alias resolved
        assert sh["dongqiudi"]["status"] == "ok"
        assert sh["the_odds_api"]["status"] == "rate_limited"

    def test_falls_back_to_decision_audit_source_audit(self):
        snap = {
            **_minimal_snapshot(),
            "decision_audit": {
                "source_audit": {
                    "football_data": {"status": "ok"},
                },
            },
        }
        out = normalize_dashboard_snapshot(snap)
        assert out["source_health"]["football_data"]["status"] == "ok"


class TestOddsTrend:
    def test_each_point_carries_label(self):
        # The detail snapshot is normalized separately, but here we test the
        # helper used by both: every point ends with a non-empty string label.
        from football_data_mcp.dashboard_contract import normalize_odds_trend_points
        raw = [
            {"x": "2026-05-28T05:00", "home": 1.95, "draw": 3.4, "away": 4.1},
            {"label": "08:30Z", "home": 1.92},
            {},  # invalid, should be dropped
        ]
        points: list[OddsTrendPoint] = normalize_odds_trend_points(raw)
        assert len(points) == 2
        assert points[0]["label"] == "2026-05-28T05:00"
        assert points[1]["label"] == "08:30Z"


class TestBacktestCurve:
    def test_points_normalize_label_and_roi(self):
        snap = {
            **_minimal_snapshot(),
            "backtest_curve": {
                "points": [
                    {"x": 0, "y": 0.0, "extra": "kept"},
                    {"index": 5, "y": -0.03},
                    {"label": "2026-05-28", "y": 0.04},
                ],
            },
        }
        out = normalize_dashboard_snapshot(snap)
        pts: list[BacktestCurvePoint] = out["backtest_curve"]["points"]
        # All points preserved; canonical label and roi populated on every entry.
        assert [p["label"] for p in pts] == ["0", "5", "2026-05-28"]
        assert pts[0]["roi"] == 0.0
        assert pts[1]["roi"] == pytest.approx(-0.03)
        assert pts[2]["roi"] == pytest.approx(0.04)
        # Original fields (e.g. `extra`) are preserved alongside the canonical ones
        assert pts[0]["extra"] == "kept"

    def test_preserves_top_level_summary_fields(self):
        snap = {
            **_minimal_snapshot(),
            "backtest_curve": {
                "status": "ok",
                "severity": "info",
                "title": "ROI curve",
                "detail": "live",
                "summary": {"max_drawdown": -0.12},
                "points": [{"index": 1, "y": 0.0}],
            },
        }
        out = normalize_dashboard_snapshot(snap)
        bc = out["backtest_curve"]
        # Non-point summary fields must survive normalization
        assert bc["status"] == "ok"
        assert bc["severity"] == "info"
        assert bc["title"] == "ROI curve"
        assert bc["summary"]["max_drawdown"] == pytest.approx(-0.12)

    def test_missing_summary_is_filled_with_safe_defaults(self):
        # 历史/旧版本可能只返回 points 而没有 summary，
        # 此时前端会因为读 summary.profit_units 直接白屏。
        # 规范化层必须补一个完整 summary，让前端契约稳定。
        snap = {
            **_minimal_snapshot(),
            "backtest_curve": {
                "points": [{"label": "1", "roi": 0.01}],
            },
        }
        out = normalize_dashboard_snapshot(snap)
        bc = out["backtest_curve"]
        assert "summary" in bc, "summary must be present even if upstream omitted it"
        summary = bc["summary"]
        assert summary["profit_units"] is None
        assert summary["settled_count"] == 0
        assert summary["rolling_window"] == 10

    def test_invalid_backtest_curve_returns_empty_summary_and_points(self):
        snap = {**_minimal_snapshot(), "backtest_curve": "not-a-dict"}
        out = normalize_dashboard_snapshot(snap)
        bc = out["backtest_curve"]
        assert bc["points"] == []
        assert bc["summary"]["profit_units"] is None

    def test_partial_summary_merges_with_defaults(self):
        # 上游可能返回部分字段（如只填了 profit_units），其它键也应被默认值兜底。
        snap = {
            **_minimal_snapshot(),
            "backtest_curve": {
                "summary": {"profit_units": 1.5, "settled_count": 3},
                "points": [],
            },
        }
        out = normalize_dashboard_snapshot(snap)
        summary = out["backtest_curve"]["summary"]
        assert summary["profit_units"] == pytest.approx(1.5)
        assert summary["settled_count"] == 3
        # Defaulted keys remain present
        assert summary["rolling_window"] == 10
        assert summary["roi"] is None


class TestLineupNormalization:
    def test_record_lineup_provides_named_sides(self):
        from football_data_mcp.dashboard_contract import normalize_lineup
        raw = {
            "available": True,
            "basis": "starter",
            "status_text": "已确认",
            "home": {"formation": "4-3-3", "players": [{"number": 1, "name": "A"}]},
            "away": {"formation": "4-2-3-1", "players": [{"name": "B"}]},
            "warnings": ["缺少替补"],
        }
        lineup = normalize_lineup(raw)
        assert lineup is not None
        assert lineup["available"] is True
        side_home: LineupSide = lineup["home"]
        assert side_home["formation"] == "4-3-3"
        assert side_home["players"][0]["number"] == 1
        # Away missing number is allowed
        assert lineup["away"]["players"][0]["name"] == "B"
        assert lineup["warnings"] == ["缺少替补"]

    def test_unavailable_lineup_returns_none(self):
        from football_data_mcp.dashboard_contract import normalize_lineup
        assert normalize_lineup(None) is None
        assert normalize_lineup({"available": False})["available"] is False


class TestPassthroughInvariants:
    def test_status_and_top_level_required_fields_preserved(self):
        snap = _minimal_snapshot()
        out = normalize_dashboard_snapshot(snap)
        # Top-level invariants the frontend dashboardClient already validates
        assert out["status"] == "ok"
        assert out["tool"] == "dashboard_snapshot"
        assert out["generated_at_utc"] == "2026-05-28T07:00:00+00:00"
        assert out["kpis"] == snap["kpis"]
        assert out["prediction_kpis"] == snap["prediction_kpis"]

    def test_does_not_lose_unrecognised_top_level_keys(self):
        snap = {**_minimal_snapshot(), "custom_extension": {"v": 1}}
        out = normalize_dashboard_snapshot(snap)
        assert out["custom_extension"] == {"v": 1}

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from football_data_mcp import learning_store, snapshot_store, sources as sources_module


def test_run_auto_learning_cycle_records_shortlist_and_parlay(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")

    async def fake_shortlist_value_matches(**kwargs):
        assert kwargs["db_path"] == db_path
        return {
            "status": "ok",
            "tool": "shortlist_value_matches",
            "mode": kwargs["mode"],
            "target_market": kwargs["target_market"],
            "picks": [
                {
                    "match": {
                        "league": "测试联赛",
                        "home_team": "主队A",
                        "away_team": "客队A",
                        "kickoff_utc_plus_8": "2026-05-24T20:00:00+08:00",
                    },
                    "best_candidate": {
                        "market": "asian_handicap",
                        "selection": "主队A -0.5",
                        "selection_key": "home_cover",
                        "line": -0.5,
                        "decimal_odds": 1.9,
                        "model_probability": 0.62,
                        "edge": 0.05,
                        "recommendation": "immediate_bet",
                        "stake_level": "small",
                    },
                    "final_execution_advice": {"action": "bet_now"},
                    "selection_confidence": {"calibrated_probability": 0.62},
                    "caution_flags": [],
                }
            ],
        }

    async def fake_recommend_jingcai_parlay(**kwargs):
        return {
            "status": "ok",
            "tool": "recommend_jingcai_parlay",
            "parlay_mode": kwargs["parlay_mode"],
            "recommended_tickets": [
                {
                    "parlay_type": "2串1",
                    "recommendation": "parlay_recommended",
                    "stake_level": "tiny",
                    "combined_decimal_odds": 1.7,
                    "estimated_hit_probability": 0.42,
                    "edge_proxy": -0.2,
                    "expected_multiplier": 0.8,
                    "risk_flags": ["confidence_mode_negative_ev_allowed"],
                    "caution_flags": [],
                    "legs": [{"selection": "主队B 主胜"}, {"selection": "主队C 主胜"}],
                }
            ],
        }

    monkeypatch.setattr(sources_module, "shortlist_value_matches", fake_shortlist_value_matches)
    monkeypatch.setattr(sources_module, "recommend_jingcai_parlay", fake_recommend_jingcai_parlay)

    result = asyncio.run(
        sources_module.run_auto_learning_cycle(
            timezone_name="Asia/Shanghai",
            top_n=2,
            limit=5,
            db_path=db_path,
            auto_settle=False,
        )
    )

    assert result["status"] == "ok"
    assert result["saved_record_count"] == 2
    assert result["asian_shortlist"]["record_count"] == 1
    assert result["jingcai_parlay"]["record_count"] == 1
    records = learning_store.list_recommendation_records(db_path=db_path)
    assert {record["market"] for record in records} == {"asian_handicap", "parlay"}


def test_settle_learning_recommendations_recomputes_calibration(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-1",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "league": "测试联赛",
                "home_team": "主队A",
                "away_team": "客队A",
                "market": "asian_handicap",
                "selection": "主队A -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.9,
                "model_probability": 0.62,
                "recommendation": "immediate_bet",
            }
        ],
        db_path=db_path,
    )

    result = asyncio.run(
        sources_module.settle_learning_recommendations(
            results=[{"home_team": "主队A", "away_team": "客队A", "home_score": 2, "away_score": 0}],
            auto_fetch=False,
            db_path=db_path,
        )
    )

    assert result["settlement"]["settled_count"] == 1
    assert result["calibration"]["settled_count"] == 1
    assert result["calibration"]["buckets"][0]["hit_rate"] == 1.0
    assert result["strategy_state"]["market"] == "asian_handicap"
    assert result["strategy_state"]["mode"] == "balanced"


def test_dashboard_snapshot_exposes_prediction_accountability_when_formal_recommendations_are_empty(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "accountability-open",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "accountability-open",
                "league": "测试联赛",
                "home_team": "纸面主队",
                "away_team": "纸面客队",
                "kickoff_utc_plus_8": "2026-05-26T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "纸面主队 +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.86,
                "model_probability": 0.53,
                "calibrated_probability": 0.51,
                "market_probability": 0.50,
                "edge": 0.01,
                "recommendation": "no_value",
                "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
            },
            {
                "run_id": "accountability-settled",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "accountability-settled",
                "league": "测试联赛",
                "home_team": "回测主队",
                "away_team": "回测客队",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "回测主队 -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.90,
                "model_probability": 0.55,
                "calibrated_probability": 0.52,
                "market_probability": 0.50,
                "edge": 0.02,
                "recommendation": "no_value",
                "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
            },
        ],
        db_path=db_path,
    )
    learning_store.settle_recommendations(
        [
            {
                "match_id": "accountability-settled",
                "home_team": "回测主队",
                "away_team": "回测客队",
                "home_score": 1,
                "away_score": 0,
            }
        ],
        db_path=db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=20)
    accountability = snapshot["prediction_accountability"]

    assert accountability["policy"]["prediction_policy"] == "always_predict_and_backtest"
    assert accountability["status"] == "active_paper_validation"
    assert accountability["headline"] == "不推荐不等于不预测"
    assert accountability["summary"]["total_predictions"] == 2
    assert accountability["summary"]["formal_recommendations"] == 0
    assert accountability["summary"]["paper_predictions"] == 2
    assert accountability["summary"]["settled_predictions"] == 1
    assert accountability["summary"]["open_predictions"] == 1
    assert accountability["checks"][0]["key"] == "prediction_loop"
    assert accountability["checks"][0]["status"] == "ok"
    assert any(check["key"] == "formal_gate" and check["status"] in {"warning", "blocked"} for check in accountability["checks"])


def test_live_calibration_falls_back_to_broad_bucket_with_shrinkage(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    records = []
    results = []
    for index in range(20):
        records.append(
            {
                "run_id": f"cycle-{index}",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "match_id": f"learned-match-{index}",
                "league": "训练联赛A" if index < 10 else "训练联赛B",
                "home_team": f"训练主队{index}",
                "away_team": f"训练客队{index}",
                "market": "asian_handicap",
                "selection": f"训练主队{index} -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.9,
                "model_probability": 0.62,
            }
        )
        if index < 10:
            home_score, away_score = 2, 0
        else:
            home_score, away_score = 0, 1
        results.append(
            {
                "match_id": f"learned-match-{index}",
                "home_team": f"训练主队{index}",
                "away_team": f"训练客队{index}",
                "home_score": home_score,
                "away_score": away_score,
            }
        )
    learning_store.save_recommendation_records(records, db_path=db_path)
    learning_store.settle_recommendations(results, db_path=db_path)
    learning_store.recompute_calibration(db_path=db_path)

    [pick] = sources_module._apply_live_calibration_to_picks(
        [
            {
                "match": {"league": "未见过的新联赛", "home_team": "主队", "away_team": "客队"},
                "best_candidate": {
                    "market": "asian_handicap",
                    "selection": "主队 -0.5",
                    "selection_key": "home_cover",
                    "line": -0.5,
                    "decimal_odds": 1.9,
                    "model_probability": 0.62,
                },
                "selection_confidence": {"calibrated_probability": 0.62},
            }
        ],
        db_path=db_path,
    )

    calibration = pick["live_calibration"]
    assert calibration["source"] == "live_calibration_bucket"
    assert calibration["bucket"]["league_bucket"] == "ALL"
    assert calibration["bucket"]["line_bucket"] == "line:-0.5"
    assert calibration["adjusted_probability"] == 0.56


def test_auto_learning_cycle_reports_refreshed_record_count_for_open_predictions(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")

    async def fake_shortlist_value_matches(**kwargs):
        return {
            "status": "ok",
            "tool": "shortlist_value_matches",
            "mode": kwargs["mode"],
            "target_market": kwargs["target_market"],
            "picks": [
                {
                    "match": {
                        "match_id": "stable-match",
                        "league": "测试联赛",
                        "home_team": "主队A",
                        "away_team": "客队A",
                        "kickoff_utc_plus_8": "2026-05-24T20:00:00+08:00",
                    },
                    "best_candidate": {
                        "market": "asian_handicap",
                        "selection": "主队A -0.5",
                        "selection_key": "home_cover",
                        "line": -0.5,
                        "decimal_odds": 1.9,
                        "model_probability": 0.62,
                        "edge": 0.05,
                        "recommendation": "immediate_bet",
                        "stake_level": "small",
                    },
                    "final_execution_advice": {"action": "bet_now"},
                    "selection_confidence": {"calibrated_probability": 0.62},
                    "caution_flags": [],
                }
            ],
        }

    async def fake_recommend_jingcai_parlay(**kwargs):
        return {"status": "ok", "tool": "recommend_jingcai_parlay", "parlay_mode": kwargs["parlay_mode"], "recommended_tickets": []}

    monkeypatch.setattr(sources_module, "shortlist_value_matches", fake_shortlist_value_matches)
    monkeypatch.setattr(sources_module, "recommend_jingcai_parlay", fake_recommend_jingcai_parlay)

    first = asyncio.run(sources_module.run_auto_learning_cycle(db_path=db_path, auto_settle=False))
    second = asyncio.run(sources_module.run_auto_learning_cycle(db_path=db_path, auto_settle=False))

    assert first["saved_record_count"] == 1
    assert second["saved_record_count"] == 1
    assert len(learning_store.list_recommendation_records(db_path=db_path)) == 1


def test_auto_learning_cycle_records_rejected_as_learning_observations(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")

    async def fake_shortlist_value_matches(**kwargs):
        return {
            "status": "ok",
            "tool": "shortlist_value_matches",
            "mode": kwargs["mode"],
            "target_market": kwargs["target_market"],
            "picks": [],
            "rejected": [
                {
                    "reason": "no_positive_edge",
                    "match": {
                        "match_id": "observation-match",
                        "league": "学习联赛",
                        "home_team": "观察主队",
                        "away_team": "观察客队",
                        "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                    },
                    "best_candidate": {
                        "market": "asian_handicap",
                        "selection": "观察客队 +0.5",
                        "selection_key": "away_cover",
                        "line": 0.5,
                        "decimal_odds": 1.86,
                        "model_probability": 0.53,
                        "edge": -0.01,
                        "recommendation": "no_value",
                    },
                }
            ],
        }

    async def fake_recommend_jingcai_parlay(**kwargs):
        return {"status": "ok", "tool": "recommend_jingcai_parlay", "parlay_mode": kwargs["parlay_mode"], "recommended_tickets": []}

    monkeypatch.setattr(sources_module, "shortlist_value_matches", fake_shortlist_value_matches)
    monkeypatch.setattr(sources_module, "recommend_jingcai_parlay", fake_recommend_jingcai_parlay)

    result = asyncio.run(sources_module.run_auto_learning_cycle(db_path=db_path, auto_settle=False))

    assert result["saved_record_count"] == 1
    assert result["asian_shortlist"]["record_count"] == 0
    assert result["asian_shortlist"]["learning_observation_record_count"] == 1
    record = learning_store.list_recommendation_records(db_path=db_path)[0]
    assert record["mode"] == "balanced_observation"
    assert record["recommendation"] == "no_value"
    assert record["settlement_status"] == "open"


def test_learning_records_only_persist_near_kickoff_samples():
    near_match = {
        "match_id": "near-kickoff",
        "league": "临场联赛",
        "home_team": "临场主队",
        "away_team": "临场客队",
        "kickoff_utc_plus_8": "2026-05-25T20:09:00+08:00",
        "time_window": {
            "as_of": "2026-05-25T20:00:00+08:00",
            "kickoff": "2026-05-25T20:09:00+08:00",
        },
    }
    early_match = {
        "match_id": "too-early",
        "league": "远期联赛",
        "home_team": "远期主队",
        "away_team": "远期客队",
        "kickoff_utc_plus_8": "2026-05-25T23:00:00+08:00",
        "time_window": {
            "as_of": "2026-05-25T20:00:00+08:00",
            "kickoff": "2026-05-25T23:00:00+08:00",
        },
    }
    best_candidate = {
        "market": "asian_handicap",
        "selection": "客队 +0.5",
        "selection_key": "away_cover",
        "line": 0.5,
        "decimal_odds": 1.86,
        "model_probability": 0.53,
        "edge": -0.01,
        "recommendation": "no_value",
    }
    result = {
        "tool": "shortlist_value_matches",
        "mode": "balanced",
        "target_market": "asian_handicap",
        "picks": [
            {"match": early_match, "best_candidate": best_candidate, "selection_confidence": {"calibrated_probability": 0.53}},
            {"match": near_match, "best_candidate": best_candidate, "selection_confidence": {"calibrated_probability": 0.53}},
        ],
        "rejected": [
            {"reason": "no_positive_edge", "match": early_match, "best_candidate": best_candidate},
            {"reason": "no_positive_edge", "match": near_match, "best_candidate": best_candidate},
        ],
    }

    recommendation_records = learning_store.build_records_from_shortlist(result, run_id="near-window")
    observation_records = learning_store.build_learning_observation_records_from_shortlist(result, run_id="near-window")
    shadow_records = learning_store.build_shadow_prediction_records_from_shortlist(result, run_id="near-window")

    assert [record["match"]["match_id"] for record in recommendation_records] == ["near-kickoff"]
    assert [record["match"]["match_id"] for record in observation_records] == ["near-kickoff"]
    assert [record["match"]["match_id"] for record in shadow_records] == ["near-kickoff", "near-kickoff"]


def test_learning_records_use_shortlist_generated_time_when_time_window_missing():
    best_candidate = {
        "market": "asian_handicap",
        "selection": "客队 +0.5",
        "selection_key": "away_cover",
        "decimal_odds": 1.86,
        "model_probability": 0.53,
        "recommendation": "no_value",
    }
    result = {
        "tool": "shortlist_value_matches",
        "generated_at_utc": "2026-05-25T12:00:00+00:00",
        "mode": "balanced",
        "target_market": "asian_handicap",
        "picks": [
            {
                "match": {
                    "match_id": "too-early",
                    "kickoff_utc_plus_8": "2026-05-25T21:00:00+08:00",
                },
                "best_candidate": best_candidate,
            },
            {
                "match": {
                    "match_id": "near-kickoff",
                    "kickoff_utc_plus_8": "2026-05-25T20:09:00+08:00",
                },
                "best_candidate": best_candidate,
            },
        ],
        "rejected": [
            {
                "reason": "no_positive_edge",
                "match": {
                    "match_id": "too-early",
                    "kickoff_utc_plus_8": "2026-05-25T21:00:00+08:00",
                },
                "best_candidate": best_candidate,
            },
            {
                "reason": "no_positive_edge",
                "match": {
                    "match_id": "near-kickoff",
                    "kickoff_utc_plus_8": "2026-05-25T20:09:00+08:00",
                },
                "best_candidate": best_candidate,
            },
        ],
    }

    recommendation_records = learning_store.build_records_from_shortlist(result, run_id="generated-time")
    observation_records = learning_store.build_learning_observation_records_from_shortlist(result, run_id="generated-time")
    shadow_records = learning_store.build_shadow_prediction_records_from_shortlist(result, run_id="generated-time")

    assert [record["match"]["match_id"] for record in recommendation_records] == ["near-kickoff"]
    assert [record["match"]["match_id"] for record in observation_records] == ["near-kickoff"]
    assert [record["match"]["match_id"] for record in shadow_records] == ["near-kickoff", "near-kickoff"]


def test_auto_learning_cycle_records_shadow_predictions_from_all_analyzed_items(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    shortlist_kwargs = []

    async def fake_shortlist_value_matches(**kwargs):
        shortlist_kwargs.append(kwargs)
        return {
            "status": "ok",
            "tool": "shortlist_value_matches",
            "mode": kwargs["mode"],
            "target_market": kwargs["target_market"],
            "balanced_thresholds": {"min_calibrated_probability": 0.58},
            "picks": [
                {
                    "match": {
                        "match_id": "shadow-pick",
                        "league": "扩样联赛",
                        "home_team": "扩样主队",
                        "away_team": "扩样客队",
                        "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                    },
                    "best_candidate": {
                        "market": "asian_handicap",
                        "selection": "扩样主队 -0.5",
                        "selection_key": "home_cover",
                        "line": -0.5,
                        "decimal_odds": 1.9,
                        "model_probability": 0.62,
                        "calibrated_probability": 0.61,
                        "edge": 0.05,
                        "recommendation": "immediate_bet",
                    },
                }
            ],
            "rejected": [
                {
                    "reason": "no_positive_edge",
                    "match": {
                        "match_id": "shadow-reject",
                        "league": "扩样联赛",
                        "home_team": "观察主队",
                        "away_team": "观察客队",
                        "kickoff_utc_plus_8": "2026-05-25T21:00:00+08:00",
                    },
                    "best_candidate": {
                        "market": "asian_handicap",
                        "selection": "观察客队 +0.5",
                        "selection_key": "away_cover",
                        "line": 0.5,
                        "decimal_odds": 1.86,
                        "model_probability": 0.53,
                        "edge": -0.01,
                        "recommendation": "no_value",
                    },
                }
            ],
        }

    monkeypatch.setattr(sources_module, "shortlist_value_matches", fake_shortlist_value_matches)

    result = asyncio.run(
        sources_module.run_auto_learning_cycle(
            db_path=db_path,
            auto_settle=False,
            include_jingcai_parlay=False,
            include_learning_observations=False,
            analysis_candidate_limit=80,
            analysis_concurrency=10,
            shadow_prediction_limit=100,
        )
    )

    assert shortlist_kwargs[0]["analysis_candidate_limit"] == 80
    assert shortlist_kwargs[0]["analysis_concurrency"] == 10
    assert result["asian_shortlist"]["record_count"] == 1
    assert result["asian_shortlist"]["shadow_prediction_record_count"] == 2
    assert result["saved_shadow_prediction_count"] == 2
    shadows = learning_store.list_shadow_prediction_records(db_path=db_path)
    assert [shadow["decision"] for shadow in shadows] == ["rejected", "accepted"]
    assert result["shadow_prediction_metrics"]["record_counts"]["open"] == 2


def test_auto_learning_cycle_runs_shortlist_before_slow_leisu_snapshot_sync(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    calls = []

    async def fake_sync_leisu_odds_snapshots(**kwargs):
        calls.append(("snapshot_sync", kwargs))
        return {
            "status": "ok",
            "saved_snapshot_count": 9,
            "generated_snapshot_count": 9,
            "snapshot_store": {"db_path": "/tmp/snapshots.sqlite3"},
            "providers": {
                "leisu": {
                    "candidate_match_count": 3,
                    "probed_match_count": 2,
                    "accessible_match_count": 2,
                    "promotable_match_count": 2,
                    "require_quality_gate": True,
                }
            },
            "matches": [
                {
                    "hard_flags": [],
                    "soft_flags": [],
                }
            ],
        }

    async def fake_shortlist_value_matches(**kwargs):
        calls.append(("shortlist", kwargs))
        return {
            "status": "ok",
            "tool": "shortlist_value_matches",
            "mode": kwargs["mode"],
            "target_market": kwargs["target_market"],
            "picks": [],
            "rejected": [],
        }

    monkeypatch.setattr(sources_module, "sync_leisu_odds_snapshots", fake_sync_leisu_odds_snapshots)
    monkeypatch.setattr(sources_module, "shortlist_value_matches", fake_shortlist_value_matches)

    result = asyncio.run(
        sources_module.run_auto_learning_cycle(
            db_path=db_path,
            auto_settle=False,
            include_market_snapshot_sync=True,
            market_snapshot_window_minutes=180,
            market_snapshot_limit=2,
            market_snapshot_concurrency=1,
            include_jingcai_parlay=False,
        )
    )

    assert [item[0] for item in calls[:2]] == ["shortlist", "snapshot_sync"]
    assert calls[1][1]["window_minutes"] == 180
    assert calls[1][1]["limit"] == 2
    assert calls[1][1]["concurrency"] == 1
    assert result["market_snapshot_sync"]["status"] == "ok"
    assert result["market_snapshot_sync"]["saved_snapshot_count"] == 9
    assert result["market_snapshot_sync"]["probed_match_count"] == 2
    assert sources_module.AUTO_LEARNING_STATE["last_market_snapshot_sync"]["saved_snapshot_count"] == 9


def test_auto_learning_cycle_records_observation_when_candidate_is_not_publishable(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")

    async def fake_shortlist_value_matches(**kwargs):
        return {
            "status": "ok",
            "tool": "shortlist_value_matches",
            "mode": kwargs["mode"],
            "target_market": kwargs["target_market"],
            "total_candidates": 1,
            "analyzed_count": 1,
            "not_analyzed_count": 0,
            "eligible_count": 0,
            "returned_count": 0,
            "rejected_count": 1,
            "funnel_report": {"rejection_reasons": {"multi_bookmaker_snapshot_missing": 1}},
            "picks": [],
            "rejected": [
                {
                    "reason": "multi_bookmaker_snapshot_missing",
                    "match": {
                        "match_id": "observe-1",
                        "league": "观察联赛",
                        "home_team": "观察主队",
                        "away_team": "观察客队",
                        "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                    },
                    "best_candidate": {
                        "market": "asian_handicap",
                        "selection": "观察主队 +0.25",
                        "selection_key": "home_cover",
                        "line": 0.25,
                        "decimal_odds": 1.88,
                        "model_probability": 0.53,
                        "market_probability": 0.51,
                        "edge": 0.02,
                        "recommendation": "condition_observe",
                    },
                }
            ],
        }

    monkeypatch.setattr(sources_module, "shortlist_value_matches", fake_shortlist_value_matches)

    result = asyncio.run(
        sources_module.run_auto_learning_cycle(
            db_path=db_path,
            auto_settle=False,
            include_jingcai_parlay=False,
            include_market_snapshot_sync=False,
        )
    )

    assert result["asian_shortlist"]["record_count"] == 0
    assert result["asian_shortlist"]["learning_observation_record_count"] == 1
    assert result["asian_shortlist"]["shadow_prediction_record_count"] == 1
    assert result["asian_shortlist"]["analyzed_count"] == 1
    assert result["saved_record_count"] == 1
    records = learning_store.list_recommendation_records(db_path=db_path)
    assert len(records) == 1
    assert records[0]["mode"] == "balanced_observation"
    assert records[0]["recommendation"] == "condition_observe"


def test_shortlist_balanced_mode_uses_learned_strategy_thresholds(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": f"cycle-{index}",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "match_id": f"learned-threshold-{index}",
                "league": "策略联赛",
                "home_team": f"策略主队{index}",
                "away_team": f"策略客队{index}",
                "market": "asian_handicap",
                "selection": f"策略主队{index} -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.8,
                "model_probability": 0.62,
                "calibrated_probability": 0.62,
                "edge": 0.06,
            }
            for index in range(20)
        ],
        db_path=db_path,
    )
    learning_store.settle_recommendations(
        [
            {
                "match_id": f"learned-threshold-{index}",
                "home_team": f"策略主队{index}",
                "away_team": f"策略客队{index}",
                "home_score": 0,
                "away_score": 1,
            }
            for index in range(20)
        ],
        db_path=db_path,
    )
    learning_store.recompute_calibration(db_path=db_path)
    learning_store.update_strategy_state(db_path=db_path, market="asian_handicap", mode="balanced")

    async def fake_list_matches(**kwargs):
        return {
            "status": "ok",
            "time_window_policy": {},
            "source": {},
            "matches": [
                {
                    "match_id": "candidate-match",
                    "league": "策略联赛",
                    "home_team": "候选主队",
                    "away_team": "候选客队",
                    "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                }
            ],
        }

    async def fake_analyze_single_match(*args, **kwargs):
        return {
            "status": "ok",
            "agent_brief": {
                "match": {
                    "match_id": "candidate-match",
                    "league": "策略联赛",
                    "home_team": "候选主队",
                    "away_team": "候选客队",
                    "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                }
            },
            "quality": {"is_bettable_input": True},
            "analysis_pack": {
                "data_coverage": {
                    "blocks": {
                        "moneyline_1x2": True,
                        "asian_handicap": True,
                        "over_under": True,
                    }
                }
            },
            "odds": {},
            "best_candidate": {
                "market": "asian_handicap",
                "selection": "候选主队 -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.85,
                "model_probability": 0.60,
                "calibrated_probability": 0.60,
                "edge": 0.05,
                "recommendation": "immediate_bet",
                "stake_level": "small",
            },
            "market_candidates": [],
            "betting_decision_support": {
                "blocking_flags": [],
                "caution_flags": [],
                "confidence": 0.60,
            },
        }

    monkeypatch.setattr(sources_module, "list_matches", fake_list_matches)
    monkeypatch.setattr(sources_module, "analyze_single_match", fake_analyze_single_match)

    result = asyncio.run(
        sources_module.shortlist_value_matches(
            mode="balance",
            target_market="asian_handicap",
            db_path=db_path,
        )
    )

    assert result["learning_policy"]["active"] is True
    assert result["balanced_thresholds"]["min_calibrated_probability"] > 0.58
    assert result["eligible_count"] == 0
    assert result["rejected"][0]["reason"] == "calibrated_probability_below_threshold"


def test_dashboard_snapshot_separates_picks_observations_settlements_and_strategy(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-dashboard",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "match_id": "dashboard-pick",
                "league": "日职联",
                "home_team": "清水鼓动",
                "away_team": "大阪钢巴",
                "kickoff_utc_plus_8": "2026-05-25T19:00:00+08:00",
                "market": "asian_handicap",
                "selection": "大阪钢巴 +0.25",
                "selection_key": "away_cover",
                "line": 0.25,
                "decimal_odds": 1.82,
                "model_probability": 0.586,
                "calibrated_probability": 0.569,
                "edge": 0.02,
                "recommendation": "immediate_bet",
                "stake_level": "small",
                "risk_flags": ["lineup_unavailable"],
                "raw": {
                    "match_context": {
                        "fixture": {
                            "home_team_logo_url": "https://assets.example.com/shimizu.png",
                            "away_team_logo_url": "https://assets.example.com/gamba.png",
                        }
                    }
                },
            },
            {
                "run_id": "cycle-dashboard",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "dashboard-observation",
                "league": "韩K2",
                "home_team": "坡州开拓者",
                "away_team": "金浦",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "金浦 -0.5",
                "selection_key": "away_cover",
                "line": -0.5,
                "decimal_odds": 1.78,
                "model_probability": 0.52,
                "edge": -0.01,
                "recommendation": "no_value",
                "raw": {
                    "kind": "learning_observation",
                    "reason": "value_edge_below_threshold",
                },
            },
            {
                "run_id": "cycle-dashboard",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "match_id": "dashboard-settled",
                "league": "越南甲",
                "home_team": "北宁交通",
                "away_team": "胡志明市二队",
                "kickoff_utc_plus_8": "2026-05-24T09:00:00+08:00",
                "market": "asian_handicap",
                "selection": "胡志明市二队 +2.75",
                "selection_key": "away_cover",
                "line": 2.75,
                "decimal_odds": 1.9,
                "model_probability": 0.61,
                "recommendation": "immediate_bet",
            },
        ],
        db_path=db_path,
    )
    learning_store.settle_recommendations(
        [
            {
                "match_id": "dashboard-settled",
                "home_team": "北宁交通",
                "away_team": "胡志明市二队",
                "home_score": 8,
                "away_score": 0,
            }
        ],
        db_path=db_path,
    )
    learning_store.recompute_calibration(db_path=db_path)
    learning_store.update_strategy_state(db_path=db_path, market="asian_handicap", mode="balanced")

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=20)

    assert snapshot["status"] == "ok"
    assert snapshot["kpis"]["open_records"] == 2
    assert snapshot["kpis"]["settled_records"] == 1
    assert snapshot["kpis"]["asian_pick_count"] == 1
    assert snapshot["kpis"]["observation_count"] == 1
    assert snapshot["strategy_state"]["market"] == "asian_handicap"
    assert snapshot["asian_picks"][0]["matchup"] == "清水鼓动 vs 大阪钢巴"
    assert snapshot["asian_picks"][0]["home_team_logo_url"] == "https://assets.example.com/shimizu.png"
    assert snapshot["asian_picks"][0]["away_team_logo_url"] == "https://assets.example.com/gamba.png"
    assert snapshot["asian_picks"][0]["learned_probability"] == 0.569
    pick_ledger_row = next(row for row in snapshot["prediction_ledger"] if row["home_team"] == "清水鼓动")
    assert pick_ledger_row["home_team_logo_url"] == "https://assets.example.com/shimizu.png"
    assert pick_ledger_row["away_team_logo_url"] == "https://assets.example.com/gamba.png"
    assert snapshot["candidate_filters"][0]["reason"] == "value_edge_below_threshold"
    assert snapshot["recent_settlements"][0]["score"] == "8-0"
    assert snapshot["learning_events"][0]["kind"] in {"settlement", "strategy", "observation"}


def test_dashboard_snapshot_exposes_prediction_ledger_with_results(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-ledger",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "match_id": "ledger-hit",
                "league": "台账联赛",
                "home_team": "台账主队A",
                "away_team": "台账客队A",
                "kickoff_utc_plus_8": "2026-05-25T19:00:00+08:00",
                "market": "asian_handicap",
                "selection": "台账主队A -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.9,
                "model_probability": 0.62,
                "calibrated_probability": 0.61,
                "edge": 0.05,
                "recommendation": "immediate_bet",
                "stake_level": "small",
            }
        ],
        db_path=db_path,
    )
    learning_store.save_shadow_prediction_records(
        [
            {
                "run_id": "cycle-ledger",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "decision": "accepted",
                "match_id": "ledger-hit",
                "league": "台账联赛",
                "home_team": "台账主队A",
                "away_team": "台账客队A",
                "kickoff_utc_plus_8": "2026-05-25T19:00:00+08:00",
                "market": "asian_handicap",
                "selection": "台账主队A -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.9,
                "model_probability": 0.62,
                "calibrated_probability": 0.61,
                "edge": 0.05,
                "recommendation": "immediate_bet",
            },
            {
                "run_id": "cycle-ledger",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "decision": "rejected",
                "rejection_reason": "no_positive_edge",
                "match_id": "ledger-miss",
                "league": "台账联赛",
                "home_team": "台账主队B",
                "away_team": "台账客队B",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "1x2",
                "selection": "台账客队B 客胜",
                "selection_key": "away",
                "decimal_odds": 2.2,
                "model_probability": 0.45,
                "edge": -0.01,
                "recommendation": "no_value",
            },
        ],
        db_path=db_path,
    )
    results = [
        {"match_id": "ledger-hit", "home_team": "台账主队A", "away_team": "台账客队A", "home_score": 2, "away_score": 0},
        {"match_id": "ledger-miss", "home_team": "台账主队B", "away_team": "台账客队B", "home_score": 1, "away_score": 0},
    ]
    learning_store.settle_recommendations(results, db_path=db_path)
    learning_store.settle_shadow_predictions(results, db_path=db_path)
    learning_store.recompute_calibration(db_path=db_path)
    learning_store.update_strategy_state(db_path=db_path, market="asian_handicap", mode="balanced")

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=20)

    assert snapshot["prediction_kpis"]["total_count"] == 2
    assert snapshot["prediction_kpis"]["recommended_count"] == 1
    assert snapshot["prediction_kpis"]["observation_count"] == 1
    assert snapshot["prediction_kpis"]["settled_count"] == 2
    assert snapshot["prediction_kpis"]["hit_count"] == 1
    assert snapshot["prediction_kpis"]["miss_count"] == 1
    assert snapshot["prediction_kpis"]["hit_rate"] == 0.5
    assert snapshot["prediction_kpis"]["roi"] == -0.05
    assert snapshot["prediction_kpis"]["recommended_settled_count"] == 1
    assert snapshot["prediction_kpis"]["recommended_hit_count"] == 1
    assert snapshot["prediction_kpis"]["recommended_hit_rate"] == 1.0
    assert snapshot["prediction_kpis"]["recommended_roi"] == 0.9
    assert snapshot["prediction_kpis"]["observation_settled_count"] == 1
    assert snapshot["prediction_kpis"]["observation_hit_count"] == 0
    assert snapshot["prediction_kpis"]["observation_hit_rate"] == 0.0
    assert snapshot["prediction_kpis"]["observation_roi"] == -1.0
    assert [row["matchup"] for row in snapshot["prediction_ledger"]] == [
        "台账主队B vs 台账客队B",
        "台账主队A vs 台账客队A",
    ]
    assert snapshot["prediction_ledger"][0]["status_label"] == "未命中"
    assert snapshot["prediction_ledger"][0]["score"] == "1-0"
    assert snapshot["prediction_ledger"][0]["true_result"]["home_score"] == 1
    assert snapshot["prediction_ledger"][1]["status_label"] == "命中"
    assert snapshot["prediction_ledger"][1]["score"] == "2-0"


def test_dashboard_snapshot_exposes_learning_effectiveness_against_model_and_market(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-quality",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "match_id": "quality-hit",
                "league": "质量联赛",
                "home_team": "质量主队A",
                "away_team": "质量客队A",
                "kickoff_utc_plus_8": "2026-05-25T19:00:00+08:00",
                "market": "asian_handicap",
                "selection": "质量主队A -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.8,
                "model_probability": 0.60,
                "calibrated_probability": 0.75,
                "market_probability": 0.55,
                "edge": 0.20,
                "recommendation": "immediate_bet",
                "stake_level": "small",
            },
            {
                "run_id": "cycle-quality",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "quality-miss",
                "league": "质量联赛",
                "home_team": "质量主队B",
                "away_team": "质量客队B",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "质量主队B +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.9,
                "model_probability": 0.40,
                "calibrated_probability": 0.25,
                "market_probability": 0.45,
                "edge": -0.01,
                "recommendation": "condition_observe",
                "stake_level": "none",
                "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
            },
        ],
        db_path=db_path,
    )
    learning_store.settle_recommendations(
        [
            {"match_id": "quality-hit", "home_team": "质量主队A", "away_team": "质量客队A", "home_score": 2, "away_score": 0},
            {"match_id": "quality-miss", "home_team": "质量主队B", "away_team": "质量客队B", "home_score": 0, "away_score": 2},
        ],
        db_path=db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=20)
    effectiveness = snapshot["learning_effectiveness"]

    assert effectiveness["sample_count"] == 2
    assert effectiveness["status"] == "learning_improving"
    assert effectiveness["learned"]["brier_score"] == 0.0625
    assert effectiveness["model"]["brier_score"] == 0.16
    assert effectiveness["market"]["brier_score"] == 0.2025
    assert effectiveness["deltas"]["learned_brier_minus_model"] == -0.0975
    assert effectiveness["deltas"]["learned_brier_minus_market"] == -0.14
    assert effectiveness["learning_improved"] is True
    assert effectiveness["beats_market"] is True
    assert effectiveness["deployment_verdict"] == {
        "status": "paper_only_negative_roi",
        "severity": "warning",
        "title": "学习有效但收益未转正",
        "detail": "学习概率优于原始模型和市场，但已结算收益率仍为 -10.0%，只能继续纸面验证。",
        "production_ready": False,
        "action": "keep_paper_backtest",
        "sample_count": 2,
        "roi": -0.1,
        "reasons": ["settled_roi_negative"],
    }
    assert "学习后概率优于原始模型" in effectiveness["detail"]


def test_dashboard_probability_governance_uses_market_guardrail_when_learning_lags_market(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    records = [
        {
            "run_id": "cycle-governance",
            "tool": "shortlist_value_matches",
            "mode": "balanced_observation",
            "target_market": "asian_handicap",
            "match_id": "governance-hit",
            "league": "治理联赛",
            "home_team": "治理主队A",
            "away_team": "治理客队A",
            "kickoff_utc_plus_8": "2026-05-25T19:00:00+08:00",
            "market": "asian_handicap",
            "selection": "治理主队A -0.5",
            "selection_key": "home_cover",
            "line": -0.5,
            "decimal_odds": 1.9,
            "model_probability": 0.45,
            "calibrated_probability": 0.55,
            "market_probability": 0.70,
            "edge": -0.05,
            "recommendation": "no_value",
            "stake_level": "none",
            "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
        },
        {
            "run_id": "cycle-governance",
            "tool": "shortlist_value_matches",
            "mode": "balanced_observation",
            "target_market": "asian_handicap",
            "match_id": "governance-miss",
            "league": "治理联赛",
            "home_team": "治理主队B",
            "away_team": "治理客队B",
            "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
            "market": "asian_handicap",
            "selection": "治理主队B -0.5",
            "selection_key": "home_cover",
            "line": -0.5,
            "decimal_odds": 1.9,
            "model_probability": 0.55,
            "calibrated_probability": 0.45,
            "market_probability": 0.30,
            "edge": -0.05,
            "recommendation": "no_value",
            "stake_level": "none",
            "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
        },
        {
            "run_id": "cycle-governance",
            "tool": "shortlist_value_matches",
            "mode": "balanced_observation",
            "target_market": "asian_handicap",
            "match_id": "governance-open",
            "league": "治理联赛",
            "home_team": "治理主队C",
            "away_team": "治理客队C",
            "kickoff_utc_plus_8": "2026-05-26T20:00:00+08:00",
            "market": "asian_handicap",
            "selection": "治理主队C -0.5",
            "selection_key": "home_cover",
            "line": -0.5,
            "decimal_odds": 1.9,
            "model_probability": 0.60,
            "calibrated_probability": 0.70,
            "market_probability": 0.52,
            "edge": 0.18,
            "recommendation": "condition_observe",
            "stake_level": "watch_only_until_condition",
            "raw": {"kind": "learning_observation", "reason": "paper_track"},
        },
    ]
    learning_store.save_recommendation_records(records, db_path=db_path)
    learning_store.settle_recommendations(
        [
            {"match_id": "governance-hit", "home_team": "治理主队A", "away_team": "治理客队A", "home_score": 1, "away_score": 0},
            {"match_id": "governance-miss", "home_team": "治理主队B", "away_team": "治理客队B", "home_score": 0, "away_score": 1},
        ],
        db_path=db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=20)
    governance = snapshot["learning_effectiveness"]["probability_governance"]
    open_row = next(row for row in snapshot["prediction_ledger"] if row["ledger_id"].startswith("recommendation:") and row["settlement_status"] == "open")
    diagnostic = open_row["prediction_diagnostic"]

    assert snapshot["learning_effectiveness"]["learning_improved"] is True
    assert snapshot["learning_effectiveness"]["beats_market"] is False
    assert governance["status"] == "market_guardrail_active"
    assert governance["active_probability_source"] == "market_probability"
    assert governance["active_source_label"] == "市场基准"
    assert governance["production_ready"] is False
    assert governance["threshold_probability_field"] == "governed_probability"
    assert [candidate["source"] for candidate in governance["candidates"]][:3] == [
        "market_probability",
        "learned_probability",
        "model_probability",
    ]
    assert diagnostic["governed_probability"] == 0.52
    assert diagnostic["probability_source"] == "market_probability"
    assert diagnostic["probability_source_label"] == "市场基准"
    assert diagnostic["threshold_gaps"]["probability"] == -0.06
    assert diagnostic["threshold_passed"] is False


def test_dashboard_learning_effectiveness_exposes_probability_band_backtest(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    records = []
    for index, probability, home_score, away_score, odds in [
        (1, 0.40, 0, 1, 1.90),
        (2, 0.50, 1, 0, 1.90),
        (3, 0.60, 1, 0, 1.80),
        (4, 0.72, 0, 1, 1.80),
    ]:
        records.append(
            {
                "run_id": "cycle-quality-bands",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": f"quality-band-{index}",
                "league": "概率分桶联赛",
                "home_team": f"概率主队{index}",
                "away_team": f"概率客队{index}",
                "kickoff_utc_plus_8": f"2026-05-25T2{index}:00:00+08:00",
                "market": "asian_handicap",
                "selection": f"概率主队{index} -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": odds,
                "model_probability": probability,
                "calibrated_probability": probability,
                "market_probability": 1 / odds,
                "edge": probability - (1 / odds),
                "recommendation": "condition_observe",
                "stake_level": "none",
                "raw": {"kind": "learning_observation", "reason": "paper_backtest"},
            }
        )
    learning_store.save_recommendation_records(records, db_path=db_path)
    learning_store.settle_recommendations(
        [
            {
                "match_id": f"quality-band-{index}",
                "home_team": f"概率主队{index}",
                "away_team": f"概率客队{index}",
                "home_score": home_score,
                "away_score": away_score,
            }
            for index, _probability, home_score, away_score, _odds in [
                (1, 0.40, 0, 1, 1.90),
                (2, 0.50, 1, 0, 1.90),
                (3, 0.60, 1, 0, 1.80),
                (4, 0.72, 0, 1, 1.80),
            ]
        ],
        db_path=db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=20)
    bands = {band["key"]: band for band in snapshot["learning_effectiveness"]["probability_bands"]}

    assert list(bands) == ["under_45", "between_45_55", "between_55_65", "over_65"]
    assert bands["under_45"]["sample_count"] == 1
    assert bands["under_45"]["hit_rate"] == 0.0
    assert bands["under_45"]["roi"] == -1.0
    assert bands["between_45_55"]["sample_count"] == 1
    assert bands["between_45_55"]["hit_rate"] == 1.0
    assert bands["between_45_55"]["avg_probability"] == 0.5
    assert bands["between_55_65"]["brier_score"] == 0.16
    assert bands["over_65"]["sample_count"] == 1
    assert bands["over_65"]["hit_rate"] == 0.0
    assert bands["over_65"]["calibration_error"] == 0.72


def test_dashboard_detects_inverted_probability_bands_and_counter_signal_watchlist(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    records = []
    results = []
    for index in range(12):
        records.append(
            {
                "run_id": "cycle-inverted-low",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": f"inverted-low-{index}",
                "league": "校准联赛",
                "home_team": f"低概率主队{index}",
                "away_team": f"低概率客队{index}",
                "kickoff_utc_plus_8": "2026-05-25T19:00:00+08:00",
                "market": "asian_handicap",
                "selection": f"低概率主队{index} -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.9,
                "model_probability": 0.48,
                "calibrated_probability": 0.42,
                "market_probability": 0.52,
                "edge": -0.03,
                "recommendation": "no_value",
                "stake_level": "none",
                "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
            }
        )
        home_score, away_score = (2, 0) if index < 8 else (0, 2)
        results.append(
            {
                "match_id": f"inverted-low-{index}",
                "home_team": f"低概率主队{index}",
                "away_team": f"低概率客队{index}",
                "home_score": home_score,
                "away_score": away_score,
            }
        )
    for index in range(24):
        records.append(
            {
                "run_id": "cycle-inverted-mid",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": f"inverted-mid-{index}",
                "league": "校准联赛",
                "home_team": f"中概率主队{index}",
                "away_team": f"中概率客队{index}",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": f"中概率主队{index} -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.9,
                "model_probability": 0.55,
                "calibrated_probability": 0.52,
                "market_probability": 0.52,
                "edge": 0.0,
                "recommendation": "no_value",
                "stake_level": "none",
                "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
            }
        )
        home_score, away_score = (2, 0) if index < 6 else (0, 2)
        results.append(
            {
                "match_id": f"inverted-mid-{index}",
                "home_team": f"中概率主队{index}",
                "away_team": f"中概率客队{index}",
                "home_score": home_score,
                "away_score": away_score,
            }
        )
    records.append(
        {
            "run_id": "cycle-inverted-open",
            "tool": "shortlist_value_matches",
            "mode": "balanced_observation",
            "target_market": "asian_handicap",
            "match_id": "inverted-open",
            "league": "校准联赛",
            "home_team": "反向观察主队",
            "away_team": "反向观察客队",
            "kickoff_utc_plus_8": "2026-05-25T21:00:00+08:00",
            "market": "asian_handicap",
            "selection": "反向观察主队 -0.5",
            "selection_key": "home_cover",
            "line": -0.5,
            "decimal_odds": 1.9,
            "model_probability": 0.48,
            "calibrated_probability": 0.42,
            "market_probability": 0.52,
            "edge": -0.03,
            "recommendation": "no_value",
            "stake_level": "none",
            "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
        }
    )
    learning_store.save_recommendation_records(records, db_path=db_path)
    learning_store.settle_recommendations(results, db_path=db_path)
    learning_store.recompute_calibration(db_path=db_path)
    learning_store.update_strategy_state(db_path=db_path, market="asian_handicap", mode="balanced")

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=100)
    calibration_health = snapshot["learning_effectiveness"]["calibration_health"]

    assert calibration_health["status"] == "inverted_probability_bands"
    assert calibration_health["best_band_key"] == "under_45"
    assert calibration_health["candidate_band_keys"] == ["under_45"]
    assert calibration_health["meta_model"]["name"] == "probability_band_reliability"
    assert "低概率" in calibration_health["detail"]
    assert "probability_bands_inverted" in snapshot["learning_effectiveness"]["deployment_verdict"]["reasons"]
    shadow_model = snapshot["learning_effectiveness"]["shadow_recalibration"]
    assert shadow_model["status"] == "shadow_model_ready"
    assert shadow_model["method"] == "beta_binomial_probability_band_recalibrator_v1"
    assert shadow_model["selected_band_keys"] == ["under_45"]
    assert shadow_model["quality"]["sample_count"] == 36
    assert shadow_model["quality"]["recalibrated_brier_score"] < shadow_model["quality"]["learned_brier_score"]
    assert shadow_model["quality"]["validation_mode"] == "walk_forward_prequential"
    assert shadow_model["quality"]["walk_forward_sample_count"] == 36
    assert shadow_model["quality"]["walk_forward_recalibrated_brier_score"] is not None
    assert shadow_model["quality"]["walk_forward_brier_delta"] is not None
    assert shadow_model["validation"]["sample_count"] == 12
    assert shadow_model["validation"]["mode"] == "walk_forward_prequential"
    assert shadow_model["validation"]["hit_rate"] == 0.666667
    assert shadow_model["validation"]["roi"] > 0

    opportunity = snapshot["recommendation_opportunity"]
    assert opportunity["counter_signal_count"] == 1
    assert opportunity["counter_signal_candidates"][0]["ledger_id"].startswith("recommendation:")
    assert opportunity["counter_signal_candidates"][0]["meta_signal_label"] == "反向校准观察"
    assert opportunity["counter_signal_candidates"][0]["meta_probability"] == shadow_model["bands"][0]["posterior_probability"]
    assert opportunity["counter_signal_candidates"][0]["meta_edge"] > 0
    assert opportunity["counter_signal_candidates"][0]["meta_sample_count"] == 12
    assert opportunity["counter_signal_candidates"][0]["meta_confidence"] == "thin_sample"
    assert opportunity["release_gate"]["status"] == "paper_only_calibration_guardrail"
    gates = {gate["key"]: gate for gate in opportunity["release_gate"]["gates"]}
    assert gates["calibration_health"]["status"] == "blocked"


def test_dashboard_backtest_curve_tracks_profit_drawdown_and_rolling_hit_rate():
    curve = sources_module._dashboard_backtest_curve(
        [
            {
                "ledger_id": "recommendation:1",
                "matchup": "曲线主队A vs 曲线客队A",
                "prediction_type_label": "纸面预测",
                "settlement_status": "settled",
                "hit": 1,
                "profit_units": 0.8,
                "settled_at_utc": "2026-05-25T10:00:00+00:00",
            },
            {
                "ledger_id": "recommendation:2",
                "matchup": "曲线主队B vs 曲线客队B",
                "prediction_type_label": "纸面预测",
                "settlement_status": "settled",
                "hit": 0,
                "profit_units": -1.0,
                "settled_at_utc": "2026-05-25T11:00:00+00:00",
            },
            {
                "ledger_id": "recommendation:3",
                "matchup": "曲线主队C vs 曲线客队C",
                "prediction_type_label": "纸面预测",
                "settlement_status": "settled",
                "hit": 0,
                "profit_units": -1.0,
                "settled_at_utc": "2026-05-25T12:00:00+00:00",
            },
            {
                "ledger_id": "recommendation:4",
                "matchup": "曲线主队D vs 曲线客队D",
                "prediction_type_label": "纸面预测",
                "settlement_status": "settled",
                "hit": 1,
                "profit_units": 0.9,
                "settled_at_utc": "2026-05-25T13:00:00+00:00",
            },
        ],
        rolling_window=3,
    )

    assert curve["status"] == "negative_roi"
    assert curve["summary"] == {
        "settled_count": 4,
        "hit_count": 2,
        "miss_count": 2,
        "hit_rate": 0.5,
        "profit_units": -0.3,
        "roi": -0.075,
        "max_drawdown_units": -2.0,
        "longest_loss_streak": 2,
        "current_streak_type": "hit",
        "current_streak_count": 1,
        "rolling_window": 3,
    }
    assert [point["cumulative_profit"] for point in curve["points"]] == [0.8, -0.2, -1.2, -0.3]
    assert [point["drawdown_units"] for point in curve["points"]] == [0.0, -1.0, -2.0, -1.1]
    assert [point["rolling_hit_rate"] for point in curve["points"]] == [1.0, 0.5, 0.333333, 0.333333]
    assert curve["points"][-1]["matchup"] == "曲线主队D vs 曲线客队D"


def test_dashboard_prediction_quality_segments_backtest_by_reason(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    records = [
        {
            "run_id": "cycle-quality-segment",
            "tool": "shortlist_value_matches",
            "mode": "balanced_observation",
            "target_market": "asian_handicap",
            "match_id": "segment-edge-hit",
            "league": "分组联赛",
            "home_team": "边际主队A",
            "away_team": "边际客队A",
            "market": "asian_handicap",
            "selection": "边际主队A -0.5",
            "selection_key": "home_cover",
            "line": -0.5,
            "decimal_odds": 1.8,
            "model_probability": 0.56,
            "calibrated_probability": 0.56,
            "market_probability": 0.52,
            "edge": -0.01,
            "recommendation": "no_value",
            "stake_level": "none",
            "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
        },
        {
            "run_id": "cycle-quality-segment",
            "tool": "shortlist_value_matches",
            "mode": "balanced_observation",
            "target_market": "asian_handicap",
            "match_id": "segment-edge-miss",
            "league": "分组联赛",
            "home_team": "边际主队B",
            "away_team": "边际客队B",
            "market": "asian_handicap",
            "selection": "边际主队B -0.5",
            "selection_key": "home_cover",
            "line": -0.5,
            "decimal_odds": 1.8,
            "model_probability": 0.54,
            "calibrated_probability": 0.54,
            "market_probability": 0.52,
            "edge": -0.02,
            "recommendation": "no_value",
            "stake_level": "none",
            "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
        },
        {
            "run_id": "cycle-quality-segment",
            "tool": "shortlist_value_matches",
            "mode": "balanced_observation",
            "target_market": "asian_handicap",
            "match_id": "segment-snapshot-miss",
            "league": "分组联赛",
            "home_team": "快照主队",
            "away_team": "快照客队",
            "market": "asian_handicap",
            "selection": "快照主队 -0.5",
            "selection_key": "home_cover",
            "line": -0.5,
            "decimal_odds": 1.9,
            "model_probability": 0.61,
            "calibrated_probability": 0.61,
            "market_probability": 0.50,
            "edge": 0.05,
            "recommendation": "immediate_bet",
            "stake_level": "small",
            "raw": {"kind": "learning_observation", "reason": "multi_bookmaker_snapshot_missing"},
        },
        {
            "run_id": "cycle-quality-segment",
            "tool": "shortlist_value_matches",
            "mode": "balanced_observation",
            "target_market": "asian_handicap",
            "match_id": "segment-edge-open",
            "league": "分组联赛",
            "home_team": "边际主队C",
            "away_team": "边际客队C",
            "market": "asian_handicap",
            "selection": "边际主队C -0.5",
            "selection_key": "home_cover",
            "line": -0.5,
            "decimal_odds": 1.8,
            "model_probability": 0.53,
            "calibrated_probability": 0.53,
            "market_probability": 0.52,
            "edge": -0.03,
            "recommendation": "no_value",
            "stake_level": "none",
            "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
        },
    ]
    learning_store.save_recommendation_records(records, db_path=db_path)
    learning_store.settle_recommendations(
        [
            {"match_id": "segment-edge-hit", "home_team": "边际主队A", "away_team": "边际客队A", "home_score": 1, "away_score": 0},
            {"match_id": "segment-edge-miss", "home_team": "边际主队B", "away_team": "边际客队B", "home_score": 0, "away_score": 1},
            {"match_id": "segment-snapshot-miss", "home_team": "快照主队", "away_team": "快照客队", "home_score": 0, "away_score": 1},
        ],
        db_path=db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=20)
    quality = snapshot["prediction_quality"]
    segments = {segment["reason"]: segment for segment in quality["segments"]}

    assert quality["summary"]["total_count"] == 4
    assert quality["summary"]["settled_count"] == 3
    assert segments["no_positive_edge"]["label"] == "无正向边际"
    assert segments["no_positive_edge"]["total_count"] == 3
    assert segments["no_positive_edge"]["open_count"] == 1
    assert segments["no_positive_edge"]["settled_count"] == 2
    assert segments["no_positive_edge"]["hit_rate"] == 0.5
    assert segments["no_positive_edge"]["roi"] == -0.1
    assert segments["no_positive_edge"]["avg_edge"] == -0.02
    assert segments["multi_bookmaker_snapshot_missing"]["label"] == "缺少多公司赔率快照"
    assert segments["multi_bookmaker_snapshot_missing"]["settled_count"] == 1
    assert segments["multi_bookmaker_snapshot_missing"]["hit_rate"] == 0.0
    assert segments["multi_bookmaker_snapshot_missing"]["roi"] == -1.0


def test_dashboard_prediction_quality_exposes_machine_readable_adjustments(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    records = []
    results = []
    for index in range(20):
        records.append(
            {
                "run_id": "cycle-quality-adjustment",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": f"adjustment-no-edge-{index}",
                "league": "调整联赛",
                "home_team": f"降权主队{index}",
                "away_team": f"降权客队{index}",
                "kickoff_utc_plus_8": "2026-05-25T19:00:00+08:00",
                "market": "asian_handicap",
                "selection": f"降权主队{index} +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.8,
                "model_probability": 0.55,
                "calibrated_probability": 0.54,
                "market_probability": 0.53,
                "edge": -0.03,
                "recommendation": "no_value",
                "stake_level": "none",
                "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
            }
        )
        results.append(
            {
                "match_id": f"adjustment-no-edge-{index}",
                "home_team": f"降权主队{index}",
                "away_team": f"降权客队{index}",
                "home_score": 0,
                "away_score": 1,
            }
        )
    learning_store.save_recommendation_records(records, db_path=db_path)
    learning_store.settle_recommendations(results, db_path=db_path)

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=50)
    segment = snapshot["prediction_quality"]["segments"][0]

    assert segment["reason"] == "no_positive_edge"
    assert segment["sample_quality"] == "enough_sample"
    assert segment["adjustment"]["action"] == "suppress_reason"
    assert segment["adjustment"]["label"] == "降权过滤"
    assert segment["adjustment"]["weight_multiplier"] == 0.5
    assert segment["adjustment"]["formal_gate_eligible"] is False
    assert "负收益" in segment["adjustment"]["detail"]


def test_dashboard_prediction_ledger_exposes_paper_prediction_diagnostic(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    settled_records = []
    results = []
    for index in range(20):
        match_id = f"diag-settled-{index}"
        settled_records.append(
            {
                "run_id": "cycle-diagnostic",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "match_id": match_id,
                "league": "诊断联赛",
                "home_team": f"阈值主队{index}",
                "away_team": f"阈值客队{index}",
                "kickoff_utc_plus_8": "2026-05-25T19:00:00+08:00",
                "market": "asian_handicap",
                "selection": f"阈值主队{index} -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.86,
                "model_probability": 0.61,
                "calibrated_probability": 0.60,
                "market_probability": 0.538,
                "edge": 0.04,
                "recommendation": "immediate_bet",
                "stake_level": "small",
            }
        )
        results.append(
            {
                "match_id": match_id,
                "home_team": f"阈值主队{index}",
                "away_team": f"阈值客队{index}",
                "home_score": 0,
                "away_score": 1,
            }
        )
    learning_store.save_recommendation_records(settled_records, db_path=db_path)
    learning_store.settle_recommendations(results, db_path=db_path)
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-diagnostic",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "diag-paper",
                "league": "诊断联赛",
                "home_team": "纸面主队",
                "away_team": "纸面客队",
                "kickoff_utc_plus_8": "2026-05-26T19:00:00+08:00",
                "market": "asian_handicap",
                "selection": "纸面主队 +0.25",
                "selection_key": "home_cover",
                "line": 0.25,
                "decimal_odds": 1.72,
                "model_probability": 0.61,
                "calibrated_probability": 0.59,
                "market_probability": 0.581,
                "edge": -0.01,
                "expected_multiplier": 1.0148,
                "recommendation": "condition_observe",
                "stake_level": "none",
                "raw": {
                    "kind": "learning_observation",
                    "reason": "no_positive_edge",
                },
            }
        ],
        db_path=db_path,
    )
    learning_store.recompute_calibration(db_path=db_path)
    strategy_state = learning_store.update_strategy_state(db_path=db_path, market="asian_handicap", mode="balanced")

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=50)
    ledger_row = next(row for row in snapshot["prediction_ledger"] if row["matchup"] == "纸面主队 vs 纸面客队")
    diagnostic = ledger_row["prediction_diagnostic"]

    assert strategy_state["active"] is True
    assert ledger_row["prediction_type_label"] == "纸面预测"
    assert diagnostic["actionability"] == "paper_prediction"
    assert diagnostic["actionability_label"] == "纸面预测"
    assert diagnostic["recommended"] is False
    assert diagnostic["paper_tracked"] is True
    assert diagnostic["backtest_eligible"] is True
    assert diagnostic["learning_active"] is True
    assert diagnostic["primary_reason"] == "no_positive_edge"
    assert diagnostic["primary_reason_label"] == "无正向边际"
    assert diagnostic["thresholds"]["min_calibrated_probability"] == strategy_state["min_calibrated_probability"]
    assert diagnostic["threshold_gaps"]["probability"] < 0
    assert diagnostic["threshold_gaps"]["value_edge"] < 0
    assert diagnostic["threshold_passed"] is False
    assert diagnostic["learned_adjustment"] == -0.02
    assert diagnostic["learning_application_status"] == "down_weight_only"
    assert diagnostic["learning_application_label"] == "学习校准仅降权"
    assert "降低" in diagnostic["learning_application_detail"]
    assert "纸面预测" in diagnostic["diagnostic_summary"]
    assert "无正向边际" in diagnostic["diagnostic_summary"]
    explanation_labels = [item["label"] for item in diagnostic["feature_explanations"]]
    assert explanation_labels == ["概率来源", "学习校准", "价值边际", "赔率覆盖", "情报完整度"]
    explanation_by_key = {item["key"]: item for item in diagnostic["feature_explanations"]}
    assert explanation_by_key["probability_source"]["value"] == "市场基准 58.1%"
    assert "模型 61.0%" in explanation_by_key["learning_adjustment"]["detail"]
    assert explanation_by_key["value_edge"]["tone"] == "bad"
    assert explanation_by_key["odds_coverage"]["tone"] == "caution"
    assert explanation_by_key["data_quality"]["tone"] == "caution"

    detail = sources_module.dashboard_match_detail(ledger_row["ledger_id"], db_path=db_path)

    assert detail["record"]["prediction_type_label"] == "纸面预测"
    assert detail["record"]["prediction_diagnostic"]["actionability"] == "paper_prediction"
    assert detail["record"]["prediction_diagnostic"]["learning_active"] is True
    assert detail["record"]["prediction_diagnostic"]["learning_application_label"] == "学习校准仅降权"
    assert detail["record"]["prediction_diagnostic"]["probability_source_label"] == "市场基准"
    assert detail["record"]["prediction_diagnostic"]["feature_explanations"][0]["value"] == "市场基准 58.1%"
    assert detail["evidence"]["prediction_diagnostic"]["threshold_passed"] is False
    assert detail["evidence"]["prediction_diagnostic"]["learning_active"] is True
    assert detail["evidence"]["prediction_diagnostic"]["learning_application_status"] == "down_weight_only"
    assert detail["evidence"]["prediction_diagnostic"]["feature_explanations"][0]["value"] == "市场基准 58.1%"
    assert detail["evidence"]["final_execution_advice"]["source"] == "dashboard_synthesized_advice"
    assert detail["evidence"]["final_execution_advice"]["action"] == "paper_track"
    assert detail["evidence"]["final_execution_advice"]["action_label"] == "纸面预测"
    assert detail["evidence"]["final_execution_advice"]["formal_recommendation"] is False
    assert detail["evidence"]["final_execution_advice"]["backtest_eligible"] is True
    assert "无正向边际" in detail["evidence"]["final_execution_advice"]["headline"]


def test_dashboard_snapshot_summarizes_open_match_phases(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    monkeypatch.setattr(
        sources_module,
        "now_utc",
        lambda: datetime(2026, 5, 28, 4, 0, tzinfo=timezone.utc),
    )
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "phase-live",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "phase-live",
                "league": "阶段联赛",
                "home_team": "进行主队",
                "away_team": "进行客队",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "进行主队 +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.9,
                "model_probability": 0.55,
                "recommendation": "condition_observe",
                "raw": {"match_state": {"phase": "live", "label": "比赛进行中", "score": "1-0"}},
            },
            {
                "run_id": "phase-scheduled",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "phase-scheduled",
                "league": "阶段联赛",
                "home_team": "未赛主队",
                "away_team": "未赛客队",
                "kickoff_utc_plus_8": "2026-05-28T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "未赛主队 +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.9,
                "model_probability": 0.55,
                "recommendation": "condition_observe",
                "raw": {"match_state": {"phase": "scheduled", "label": "未开赛"}},
            },
            {
                "run_id": "phase-stale-scheduled",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "phase-stale-scheduled",
                "league": "阶段联赛",
                "home_team": "旧状态主队",
                "away_team": "旧状态客队",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "旧状态主队 +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.9,
                "model_probability": 0.55,
                "recommendation": "condition_observe",
                "raw": {"match_state": {"phase": "scheduled", "label": "未开赛", "status": "Fixture"}},
            },
            {
                "run_id": "phase-postponed",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "phase-postponed",
                "league": "阶段联赛",
                "home_team": "延期主队",
                "away_team": "延期客队",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "延期主队 +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.9,
                "model_probability": 0.55,
                "recommendation": "condition_observe",
                "raw": {"match_state": {"phase": "unknown", "label": "", "status": "Postponed"}},
            },
            {
                "run_id": "phase-final-pending",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "phase-final-pending",
                "league": "阶段联赛",
                "home_team": "完场主队",
                "away_team": "完场客队",
                "kickoff_utc_plus_8": "2026-05-25T18:00:00+08:00",
                "market": "asian_handicap",
                "selection": "完场主队 +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.9,
                "model_probability": 0.55,
                "recommendation": "condition_observe",
                "raw": {"match_state": {"phase": "final", "label": "已完场待结算", "score": "2-1"}},
            },
        ],
        db_path=db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=10)

    assert snapshot["prediction_kpis"]["live_count"] == 1
    assert snapshot["prediction_kpis"]["scheduled_count"] == 1
    assert snapshot["prediction_kpis"]["final_pending_count"] == 1
    assert snapshot["prediction_kpis"]["result_pending_count"] == 1
    assert snapshot["prediction_kpis"]["postponed_count"] == 1
    assert snapshot["prediction_kpis"]["match_phase_counts"] == {
        "final": 1,
        "live": 1,
        "postponed": 1,
        "result_pending": 1,
        "scheduled": 1,
    }
    rows_by_match = {row["home_team"]: row for row in snapshot["prediction_ledger"]}
    assert rows_by_match["旧状态主队"]["status_label"] == "赛果待确认"
    assert rows_by_match["延期主队"]["status_label"] == "比赛延期"
    assert snapshot["learning_diagnostics"]["live_count"] == 1
    assert snapshot["learning_diagnostics"]["scheduled_count"] == 1
    assert snapshot["learning_diagnostics"]["final_pending_count"] == 1


def test_dashboard_snapshot_exposes_decision_audit_for_no_recommendations(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-audit",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "league": "审计联赛",
                "home_team": "审计主队A",
                "away_team": "审计客队A",
                "kickoff_utc_plus_8": "2026-05-25T19:00:00+08:00",
                "market": "asian_handicap",
                "selection": "审计主队A +0.25",
                "selection_key": "home_cover",
                "line": 0.25,
                "decimal_odds": 1.76,
                "model_probability": 0.55,
                "calibrated_probability": 0.55,
                "edge": -0.03,
                "recommendation": "no_value",
                "stake_level": "none",
                "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
            },
            {
                "run_id": "cycle-audit",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "league": "审计联赛",
                "home_team": "审计主队B",
                "away_team": "审计客队B",
                "kickoff_utc_plus_8": "2026-05-25T19:05:00+08:00",
                "market": "asian_handicap",
                "selection": "审计客队B +1.25",
                "selection_key": "away_cover",
                "line": 1.25,
                "decimal_odds": 1.82,
                "model_probability": 0.56,
                "calibrated_probability": 0.56,
                "edge": -0.01,
                "recommendation": "no_value",
                "stake_level": "none",
                "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
            },
        ],
        db_path=db_path,
    )
    learning_store.recompute_calibration(db_path=db_path)
    learning_store.update_strategy_state(db_path=db_path, market="asian_handicap", mode="balanced")

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=20)

    audit = snapshot["decision_audit"]
    assert audit["prediction"]["status"] == "ok"
    assert audit["prediction"]["total_count"] == 2
    assert audit["prediction"]["evaluation_count"] == 2
    assert audit["prediction"]["detail"] == "已形成 2 条预测样本，其中正式推荐 0 条、纸面预测 2 条；所有可结算样本都会进入回测。"
    assert audit["recommendation"]["status"] == "warning"
    assert audit["recommendation"]["detail"] == "2 场进入纸面预测，主要原因：无正向边际。"
    assert audit["recommendation"]["recommended_count"] == 0
    assert audit["recommendation"]["observation_count"] == 2
    assert audit["recommendation"]["top_rejection_reasons"][0] == {
        "reason": "no_positive_edge",
        "count": 2,
    }
    assert audit["learning"]["status"] == "warning"
    assert audit["learning"]["active"] is False
    assert audit["learning"]["settled_count"] == 0
    assert audit["learning"]["sample_count"] == 0
    assert audit["learning"]["min_sample_count"] == 20
    assert audit["settlement"]["status"] == "warning"
    assert audit["settlement"]["open_count"] == 2
    assert audit["odds"]["status"] == "warning"
    assert audit["odds"]["coverage_ratio"] == 0.0
    assert [item["key"] for item in audit["health_items"]] == [
        "prediction",
        "recommendation",
        "learning",
        "settlement",
        "odds",
    ]
    diagnostics = snapshot["learning_diagnostics"]
    assert diagnostics["status"] == "waiting_results"
    assert diagnostics["title"] == "等待赛果形成回测样本"
    assert diagnostics["prediction_total"] == 2
    assert diagnostics["formal_count"] == 0
    assert diagnostics["observation_count"] == 2
    assert diagnostics["waiting_result_count"] == 2
    assert diagnostics["backtested_count"] == 0
    assert diagnostics["remaining_to_live_calibration"] == 20
    assert diagnostics["odds_covered_count"] == 0
    assert [item["key"] for item in diagnostics["readiness_items"]] == [
        "prediction_samples",
        "settled_backtest",
        "odds_snapshots",
        "reanalysis_queue",
        "recommendation_gate",
    ]


def test_dashboard_prediction_ledger_keeps_formal_recommendations_when_observations_are_newer(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-priority",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "match_id": "formal-pick",
                "league": "澳维超",
                "home_team": "南墨尔本",
                "away_team": "埃文代尔",
                "kickoff_utc_plus_8": "2026-05-25T17:30:00+08:00",
                "market": "asian_handicap",
                "selection": "南墨尔本 +3",
                "selection_key": "home_cover",
                "line": 3.0,
                "decimal_odds": 1.82,
                "model_probability": 0.593,
                "calibrated_probability": 0.593,
                "edge": 0.08,
                "recommendation": "immediate_bet",
                "stake_level": "small",
                "created_at_utc": "2026-05-25T08:31:00+00:00",
            },
            *[
                {
                    "run_id": f"cycle-observation-{index}",
                    "tool": "shortlist_value_matches",
                    "mode": "balanced_observation",
                    "target_market": "asian_handicap",
                    "match_id": f"observation-{index}",
                    "league": "观察联赛",
                    "home_team": f"观察主队{index}",
                    "away_team": f"观察客队{index}",
                    "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                    "market": "asian_handicap",
                    "selection": f"观察主队{index} +0.5",
                    "selection_key": "home_cover",
                    "line": 0.5,
                    "decimal_odds": 1.9,
                    "model_probability": 0.52,
                    "edge": -0.01,
                    "recommendation": "no_value",
                    "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
                    "created_at_utc": f"2026-05-25T09:{index:02d}:00+00:00",
                }
                for index in range(12)
            ],
        ],
        db_path=db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=10)
    ledger = snapshot["prediction_ledger"]

    assert len(ledger) == 10
    formal = [row for row in ledger if row["matchup"] == "南墨尔本 vs 埃文代尔"]
    assert len(formal) == 1
    assert formal[0]["prediction_type_label"] == "正式推荐"
    assert formal[0]["status_label"] == "赛果待确认"
    assert snapshot["prediction_kpis"]["recommended_count"] == 1
    assert snapshot["prediction_kpis"]["observation_count"] == 12


def test_dashboard_snapshot_default_ledger_includes_all_collected_samples(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-all-ledger",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": f"ledger-full-{index}",
                "league": "完整台账联赛",
                "home_team": f"完整主队{index}",
                "away_team": f"完整客队{index}",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": f"完整主队{index} +0",
                "selection_key": "home_cover",
                "line": 0,
                "decimal_odds": 1.9,
                "model_probability": 0.5,
                "calibrated_probability": 0.5,
                "edge": -0.02,
                "recommendation": "no_value",
                "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
            }
            for index in range(120)
        ],
        db_path=db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path)

    assert snapshot["prediction_kpis"]["total_count"] == 120
    assert len(snapshot["prediction_ledger"]) == 120


def test_dashboard_snapshot_filters_open_formal_picks_against_current_policy(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")

    def record(match_id, home, away, selection, line, *, raw=None, caution_flags=None):
        return {
            "run_id": "cycle-policy-audit",
            "tool": "shortlist_value_matches",
            "mode": "balanced",
            "target_market": "asian_handicap",
            "match_id": match_id,
            "league": "复核联赛",
            "home_team": home,
            "away_team": away,
            "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
            "market": "asian_handicap",
            "selection": selection,
            "selection_key": "home_cover",
            "line": line,
            "decimal_odds": 1.88,
            "model_probability": 0.62,
            "calibrated_probability": 0.62,
            "edge": 0.08,
            "recommendation": "immediate_bet",
            "stake_level": "small",
            "caution_flags": caution_flags or [],
            "raw": raw or {},
        }

    learning_store.save_recommendation_records(
        [
            record(
                "policy-wide",
                "大盘主队",
                "大盘客队",
                "大盘主队 +2.5",
                2.5,
                raw={"data_completeness": {"available_blocks": ["multi_bookmaker_snapshot", "lineup"], "missing_blocks": []}},
            ),
            record(
                "policy-multi",
                "单公司主队",
                "单公司客队",
                "单公司主队 +0.5",
                0.5,
                raw={"data_completeness": {"available_blocks": ["lineup"], "missing_blocks": ["multi_bookmaker_snapshot"]}},
            ),
            record(
                "policy-lineup",
                "阵容缺失主队",
                "阵容缺失客队",
                "阵容缺失主队 +0.5",
                0.5,
                caution_flags=["lineup_unavailable"],
                raw={"data_completeness": {"available_blocks": ["multi_bookmaker_snapshot"], "missing_blocks": ["lineup"]}},
            ),
            record(
                "policy-clean",
                "干净主队",
                "干净客队",
                "干净主队 -0.25",
                -0.25,
                raw={"data_completeness": {"available_blocks": ["multi_bookmaker_snapshot", "lineup"], "missing_blocks": []}},
            ),
        ],
        db_path=db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=20)

    assert snapshot["kpis"]["asian_pick_count"] == 1
    assert [row["matchup"] for row in snapshot["asian_picks"]] == ["干净主队 vs 干净客队"]
    filter_counts = {item["reason"]: item["count"] for item in snapshot["candidate_filters"]}
    assert filter_counts["large_handicap_requires_backtest"] == 1
    assert filter_counts["multi_bookmaker_snapshot_missing"] == 1
    assert filter_counts["lineup_context_missing"] == 1


def test_dashboard_snapshot_rechecks_current_snapshot_coverage_before_policy_filter(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-current-coverage",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "match_id": "current-coverage",
                "league": "复核联赛",
                "home_team": "已补主队",
                "away_team": "已补客队",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "已补主队 -0.25",
                "selection_key": "home_cover",
                "line": -0.25,
                "decimal_odds": 1.88,
                "model_probability": 0.62,
                "calibrated_probability": 0.62,
                "edge": 0.08,
                "recommendation": "immediate_bet",
                "stake_level": "small",
                "raw": {
                    "data_completeness": {
                        "available_blocks": ["lineup"],
                        "missing_blocks": ["multi_bookmaker_snapshot"],
                    }
                },
            }
        ],
        db_path=db_path,
    )
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:current-coverage",
                event_id="current-coverage",
                league="复核联赛",
                home_team="已补主队",
                away_team="已补客队",
                kickoff_utc="2026-05-25T12:00:00+00:00",
                bookmaker="公司A",
                market_type="asian_handicap",
                selection="已补主队 -0.25",
                decimal_odds=1.88,
                line=-0.25,
                source_time_utc="2026-05-25T11:50:00+00:00",
                fetched_at_utc="2026-05-25T11:55:00+00:00",
                raw={},
            )
        ],
        db_path=market_db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, market_db_path=market_db_path, limit=20)

    assert snapshot["kpis"]["asian_pick_count"] == 1
    assert [row["matchup"] for row in snapshot["asian_picks"]] == ["已补主队 vs 已补客队"]
    assert snapshot["prediction_ledger"][0]["has_odds_snapshot"] is True
    assert snapshot["prediction_ledger"][0]["rejection_reason"] == ""
    filter_counts = {item["reason"]: item["count"] for item in snapshot["candidate_filters"]}
    assert "multi_bookmaker_snapshot_missing" not in filter_counts


def test_dashboard_snapshot_marks_snapshot_backfilled_observations_for_reanalysis(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-backfilled-observation",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "backfilled-observation",
                "league": "复核联赛",
                "home_team": "补快照主队",
                "away_team": "补快照客队",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "补快照主队 +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.85,
                "model_probability": 0.56,
                "calibrated_probability": 0.56,
                "edge": 0.03,
                "recommendation": "condition_observe",
                "stake_level": "none",
                "raw": {
                    "kind": "learning_observation",
                    "reason": "multi_bookmaker_snapshot_missing",
                    "data_completeness": {
                        "available_blocks": ["lineup"],
                        "missing_blocks": ["multi_bookmaker_snapshot"],
                    },
                },
            }
        ],
        db_path=db_path,
    )
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:backfilled-observation",
                event_id="backfilled-observation",
                league="复核联赛",
                home_team="补快照主队",
                away_team="补快照客队",
                kickoff_utc="2026-05-25T12:00:00+00:00",
                bookmaker="公司A",
                market_type="asian_handicap",
                selection="补快照主队 +0.5",
                decimal_odds=1.85,
                line=0.5,
                source_time_utc="2026-05-25T11:50:00+00:00",
                fetched_at_utc="2026-05-25T11:55:00+00:00",
                raw={},
            )
        ],
        db_path=market_db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, market_db_path=market_db_path, limit=20)

    ledger_row = snapshot["prediction_ledger"][0]
    assert ledger_row["has_odds_snapshot"] is True
    assert ledger_row["rejection_reason"] == "awaiting_reanalysis_after_snapshot"
    filter_counts = {item["reason"]: item["count"] for item in snapshot["candidate_filters"]}
    assert filter_counts["awaiting_reanalysis_after_snapshot"] == 1
    assert "multi_bookmaker_snapshot_missing" not in filter_counts


def test_dashboard_snapshot_exposes_recommendation_opportunity_audit(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-opportunity",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "opp-ready",
                "league": "机会联赛",
                "home_team": "机会主队",
                "away_team": "机会客队",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "机会主队 +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.88,
                "model_probability": 0.62,
                "calibrated_probability": 0.62,
                "market_probability": 0.51,
                "edge": 0.055,
                "expected_multiplier": 1.1656,
                "recommendation": "immediate_bet",
                "stake_level": "small",
                "raw": {
                    "kind": "learning_observation",
                    "reason": "multi_bookmaker_snapshot_missing",
                    "data_completeness": {
                        "available_blocks": ["lineup"],
                        "missing_blocks": ["multi_bookmaker_snapshot"],
                    },
                },
            },
            {
                "run_id": "cycle-opportunity",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "opp-missing",
                "league": "机会联赛",
                "home_team": "缺快照主队",
                "away_team": "缺快照客队",
                "kickoff_utc_plus_8": "2026-05-25T20:10:00+08:00",
                "market": "asian_handicap",
                "selection": "缺快照客队 +0.25",
                "selection_key": "away_cover",
                "line": 0.25,
                "decimal_odds": 1.9,
                "model_probability": 0.6,
                "calibrated_probability": 0.6,
                "market_probability": 0.5,
                "edge": 0.03,
                "expected_multiplier": 1.14,
                "recommendation": "condition_observe",
                "stake_level": "watch_only_until_condition",
                "raw": {
                    "kind": "learning_observation",
                    "reason": "multi_bookmaker_snapshot_missing",
                    "data_completeness": {
                        "available_blocks": ["lineup"],
                        "missing_blocks": ["multi_bookmaker_snapshot"],
                    },
                },
            },
            {
                "run_id": "cycle-opportunity",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "opp-no-value",
                "league": "机会联赛",
                "home_team": "无边际主队",
                "away_team": "无边际客队",
                "kickoff_utc_plus_8": "2026-05-25T20:20:00+08:00",
                "market": "asian_handicap",
                "selection": "无边际主队 +0",
                "selection_key": "home_cover",
                "line": 0.0,
                "decimal_odds": 1.92,
                "model_probability": 0.53,
                "calibrated_probability": 0.53,
                "market_probability": 0.52,
                "edge": -0.015,
                "expected_multiplier": 1.0176,
                "recommendation": "no_value",
                "stake_level": "none",
                "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
            },
        ],
        db_path=db_path,
    )
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:opp-ready",
                event_id="opp-ready",
                league="机会联赛",
                home_team="机会主队",
                away_team="机会客队",
                kickoff_utc="2026-05-25T12:00:00+00:00",
                bookmaker="公司A",
                market_type="asian_handicap",
                selection="机会主队 +0.5",
                decimal_odds=1.88,
                line=0.5,
                source_time_utc="2026-05-25T11:50:00+00:00",
                fetched_at_utc="2026-05-25T11:55:00+00:00",
                raw={},
            )
        ],
        db_path=market_db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, market_db_path=market_db_path, limit=50)
    opportunity = snapshot["recommendation_opportunity"]

    assert opportunity["status"] == "paper_signals_pending"
    assert opportunity["title"] == "有纸面信号，尚未升为正式推荐"
    assert opportunity["formal_count"] == 0
    assert opportunity["paper_count"] == 3
    assert opportunity["paper_signal_count"] == 2
    assert opportunity["no_value_count"] == 1
    assert opportunity["threshold_ready_count"] == 2
    assert opportunity["reanalysis_backlog_count"] == 1
    assert opportunity["missing_snapshot_count"] == 1
    assert opportunity["gate_thresholds"]["min_calibrated_probability"] == 0.58
    assert opportunity["gate_thresholds"]["min_value_edge"] == 0.02
    assert opportunity["top_candidates"][0]["ledger_id"].startswith("recommendation:")
    assert opportunity["top_candidates"][0]["recommendation"] == "immediate_bet"
    assert opportunity["top_candidates"][0]["primary_blocker"] == "awaiting_reanalysis_after_snapshot"
    assert opportunity["top_candidates"][0]["threshold_ready"] is True
    assert opportunity["top_candidates"][0]["has_odds_snapshot"] is True


def test_dashboard_recommendation_opportunity_counts_only_open_current_candidates(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-current-opportunity",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "settled-signal",
                "league": "机会联赛",
                "home_team": "已结信号主队",
                "away_team": "已结信号客队",
                "kickoff_utc_plus_8": "2026-05-25T18:00:00+08:00",
                "market": "asian_handicap",
                "selection": "已结信号主队 +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.88,
                "model_probability": 0.62,
                "calibrated_probability": 0.62,
                "market_probability": 0.51,
                "edge": 0.055,
                "expected_multiplier": 1.1656,
                "recommendation": "immediate_bet",
                "stake_level": "small",
                "settlement_status": "settled",
                "raw": {"kind": "learning_observation", "reason": "multi_bookmaker_snapshot_missing"},
            },
            {
                "run_id": "cycle-current-opportunity",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "open-no-value",
                "league": "机会联赛",
                "home_team": "当前无边际主队",
                "away_team": "当前无边际客队",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "当前无边际主队 +0",
                "selection_key": "home_cover",
                "line": 0.0,
                "decimal_odds": 1.92,
                "model_probability": 0.53,
                "calibrated_probability": 0.53,
                "market_probability": 0.52,
                "edge": -0.015,
                "expected_multiplier": 1.0176,
                "recommendation": "no_value",
                "stake_level": "none",
                "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
            },
        ],
        db_path=db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, market_db_path=market_db_path, limit=50)
    opportunity = snapshot["recommendation_opportunity"]

    assert opportunity["status"] == "no_positive_opportunity"
    assert opportunity["formal_count"] == 0
    assert opportunity["paper_count"] == 1
    assert opportunity["paper_signal_count"] == 0
    assert opportunity["historical_paper_signal_count"] == 1
    assert opportunity["settled_signal_count"] == 1
    assert opportunity["top_candidates"] == []
    assert "当前 1 场" in opportunity["detail"]


def test_dashboard_recommendation_opportunity_explains_negative_roi_paper_only_gate(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": f"cycle-negative-roi-{index}",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": f"negative-roi-{index}",
                "league": "策略联赛",
                "home_team": f"负收益主队{index}",
                "away_team": f"负收益客队{index}",
                "market": "asian_handicap",
                "selection": f"负收益主队{index} -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.8,
                "model_probability": 0.62,
                "calibrated_probability": 0.62,
                "market_probability": 0.55,
                "edge": 0.06,
                "recommendation": "immediate_bet",
                "stake_level": "small",
            }
            for index in range(20)
        ],
        db_path=db_path,
    )
    learning_store.settle_recommendations(
        [
            {
                "match_id": f"negative-roi-{index}",
                "home_team": f"负收益主队{index}",
                "away_team": f"负收益客队{index}",
                "home_score": 0,
                "away_score": 1,
            }
            for index in range(20)
        ],
        db_path=db_path,
    )
    learning_store.recompute_calibration(db_path=db_path)
    learning_store.update_strategy_state(db_path=db_path, market="asian_handicap", mode="balanced")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-negative-roi-open",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "negative-roi-open",
                "league": "策略联赛",
                "home_team": "负收益当前主队",
                "away_team": "负收益当前客队",
                "market": "asian_handicap",
                "selection": "负收益当前主队 -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.8,
                "model_probability": 0.7,
                "calibrated_probability": 0.7,
                "market_probability": 0.55,
                "edge": 0.08,
                "recommendation": "immediate_bet",
                "stake_level": "small",
            }
        ],
        db_path=db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=50)
    release_gate = snapshot["recommendation_opportunity"]["release_gate"]

    assert release_gate["status"] == "paper_only_negative_signal_roi"
    assert release_gate["formal_enabled"] is False
    assert release_gate["sample_count"] == 20
    assert release_gate["roi"] < 0
    assert release_gate["signal_settled_count"] == 20
    assert release_gate["signal_roi"] < 0
    assert "继续预测并回测" in release_gate["detail"]
    gates = {gate["key"]: gate for gate in release_gate["gates"]}
    assert gates["prediction_policy"]["status"] == "ok"
    assert gates["prediction_policy"]["title"] == "持续预测回测"
    assert gates["sample_count"]["status"] == "ok"
    assert gates["signal_backtest"]["status"] == "blocked"
    assert gates["global_backtest_roi"]["status"] == "warning"
    assert gates["market_quality"]["status"] == "blocked"
    assert gates["candidate_threshold"]["status"] == "warning"
    assert all(gate["label"] for gate in release_gate["gates"])


def test_recommendation_release_gate_uses_signal_cohort_not_global_no_value_roi():
    rows = []
    for index in range(40):
        rows.append(
            {
                "ledger_id": f"observation:no-value-{index}",
                "prediction_type": "observation",
                "settlement_status": "settled",
                "recommendation": "no_value",
                "hit": 0,
                "profit_units": -1.0,
            }
        )
    for index in range(20):
        rows.append(
            {
                "ledger_id": f"observation:signal-{index}",
                "prediction_type": "observation",
                "settlement_status": "settled",
                "recommendation": "immediate_bet",
                "hit": 1,
                "profit_units": 0.12,
            }
        )
    rows.append(
        {
            "ledger_id": "observation:open-signal",
            "prediction_type": "observation",
            "settlement_status": "open",
            "recommendation": "immediate_bet",
            "edge": 0.08,
            "learned_probability": 0.68,
            "decimal_odds": 1.88,
            "has_odds_snapshot": True,
            "prediction_diagnostic": {
                "threshold_gaps": {
                    "probability": 0.02,
                    "value_edge": 0.04,
                    "min_decimal_odds": 0.18,
                    "max_decimal_odds": 0.17,
                }
            },
        }
    )

    opportunity = sources_module._dashboard_recommendation_opportunity(
        rows,
        strategy_state={
            "sample_count": 60,
            "min_live_sample_count": 20,
            "roi": -0.62,
            "hit_rate": 0.33,
            "min_calibrated_probability": 0.66,
            "min_value_edge": 0.04,
            "min_decimal_odds": 1.7,
            "max_decimal_odds": 2.05,
        },
        candidate_filters=[],
        learning_effectiveness={"learning_improved": True, "beats_market": True},
    )
    release_gate = opportunity["release_gate"]
    gates = {gate["key"]: gate for gate in release_gate["gates"]}

    assert release_gate["status"] == "formal_gate_open"
    assert release_gate["formal_enabled"] is True
    assert release_gate["signal_settled_count"] == 20
    assert release_gate["signal_roi"] == 0.12
    assert gates["signal_backtest"]["status"] == "ok"
    assert gates["global_backtest_roi"]["status"] == "warning"
    assert gates["candidate_threshold"]["status"] == "ok"


def test_recommendation_release_gate_blocks_negative_quality_segment_candidate():
    rows = []
    for index in range(20):
        rows.append(
            {
                "ledger_id": f"observation:signal-{index}",
                "prediction_type": "observation",
                "settlement_status": "settled",
                "recommendation": "immediate_bet",
                "hit": 1,
                "profit_units": 0.12,
            }
        )
    rows.append(
        {
            "ledger_id": "observation:open-negative-segment",
            "prediction_type": "observation",
            "settlement_status": "open",
            "recommendation": "immediate_bet",
            "edge": 0.08,
            "learned_probability": 0.68,
            "decimal_odds": 1.88,
            "has_odds_snapshot": True,
            "prediction_diagnostic": {
                "primary_reason": "no_positive_edge",
                "threshold_gaps": {
                    "probability": 0.02,
                    "value_edge": 0.04,
                    "min_decimal_odds": 0.18,
                    "max_decimal_odds": 0.17,
                },
            },
        }
    )
    prediction_quality = {
        "segments": [
            {
                "reason": "no_positive_edge",
                "label": "无正向边际",
                "settled_count": 25,
                "roi": -0.18,
                "sample_quality": "enough_sample",
                "adjustment": {
                    "action": "suppress_reason",
                    "formal_gate_eligible": False,
                },
            }
        ]
    }

    opportunity = sources_module._dashboard_recommendation_opportunity(
        rows,
        strategy_state={
            "sample_count": 40,
            "min_live_sample_count": 20,
            "roi": 0.08,
            "hit_rate": 0.62,
            "min_calibrated_probability": 0.66,
            "min_value_edge": 0.04,
            "min_decimal_odds": 1.7,
            "max_decimal_odds": 2.05,
        },
        candidate_filters=[],
        learning_effectiveness={"learning_improved": True, "beats_market": True},
        prediction_quality=prediction_quality,
    )
    release_gate = opportunity["release_gate"]
    gates = {gate["key"]: gate for gate in release_gate["gates"]}

    assert opportunity["paper_signal_count"] == 1
    assert opportunity["negative_segment_blocked_count"] == 1
    assert opportunity["threshold_ready_count"] == 0
    assert opportunity["top_candidates"] == []
    assert release_gate["status"] == "paper_only_negative_segment"
    assert release_gate["formal_enabled"] is False
    assert "无正向边际" in release_gate["detail"]
    assert release_gate["signal_roi"] == 0.12
    assert gates["signal_backtest"]["status"] == "ok"
    assert gates["prediction_quality_segment"]["status"] == "blocked"
    assert gates["candidate_threshold"]["status"] == "warning"


def test_shadow_walk_forward_failure_blocks_formal_gate_and_production_readiness():
    rows = []
    for index in range(20):
        rows.append(
            {
                "ledger_id": f"observation:signal-{index}",
                "prediction_type": "observation",
                "settlement_status": "settled",
                "recommendation": "immediate_bet",
                "hit": 1,
                "profit_units": 0.14,
            }
        )
    rows.append(
        {
            "ledger_id": "observation:open-signal",
            "prediction_type": "observation",
            "settlement_status": "open",
            "recommendation": "immediate_bet",
            "edge": 0.08,
            "learned_probability": 0.68,
            "decimal_odds": 1.88,
            "has_odds_snapshot": True,
            "prediction_diagnostic": {
                "threshold_gaps": {
                    "probability": 0.02,
                    "value_edge": 0.04,
                    "min_decimal_odds": 0.18,
                    "max_decimal_odds": 0.17,
                }
            },
        }
    )
    learning_effectiveness = {
        "learning_improved": True,
        "beats_market": True,
        "detail": "学习后概率样本内优于原始模型和市场。",
        "shadow_recalibration": {
            "status": "shadow_model_watch_only",
            "title": "影子模型观察中",
            "detail": "影子模型样本内改善，但走步验证尚未优于原学习概率。",
            "quality": {
                "sample_count": 40,
                "validation_mode": "walk_forward_prequential",
                "walk_forward_sample_count": 40,
                "walk_forward_recalibrated_brier_score": 0.258,
                "walk_forward_brier_delta": 0.006,
            },
            "validation": {
                "mode": "walk_forward_prequential",
                "sample_count": 20,
                "walk_forward_brier_score": 0.278,
            },
        },
    }

    opportunity = sources_module._dashboard_recommendation_opportunity(
        rows,
        strategy_state={
            "sample_count": 40,
            "min_live_sample_count": 20,
            "roi": 0.08,
            "hit_rate": 0.62,
            "min_calibrated_probability": 0.66,
            "min_value_edge": 0.04,
            "min_decimal_odds": 1.7,
            "max_decimal_odds": 2.05,
        },
        candidate_filters=[],
        learning_effectiveness=learning_effectiveness,
    )
    release_gate = opportunity["release_gate"]
    release_gates = {gate["key"]: gate for gate in release_gate["gates"]}

    assert release_gate["status"] == "paper_only_shadow_walk_forward"
    assert release_gate["formal_enabled"] is False
    assert release_gates["shadow_walk_forward"]["status"] == "blocked"
    assert "走步验证" in release_gates["shadow_walk_forward"]["detail"]

    readiness = sources_module._dashboard_production_readiness(
        prediction_kpis={
            "total_count": 41,
            "settled_count": 40,
            "open_count": 1,
            "hit_rate": 0.62,
            "roi": 0.08,
        },
        learning_effectiveness=learning_effectiveness,
        recommendation_opportunity=opportunity,
        dashboard_contract={"status": "ok", "detail": "数据契约可用。"},
    )
    readiness_gates = {gate["key"]: gate for gate in readiness["gates"]}

    assert readiness["production_ready"] is False
    assert readiness_gates["shadow_walk_forward"]["status"] == "blocked"
    assert "走步验证" in readiness_gates["shadow_walk_forward"]["detail"]


def test_clv_guard_blocks_production_readiness_after_formal_gate_opens():
    readiness = sources_module._dashboard_production_readiness(
        prediction_kpis={
            "total_count": 32,
            "settled_count": 30,
            "open_count": 2,
            "hit_rate": 0.6,
            "roi": 0.08,
        },
        learning_effectiveness={
            "learning_improved": True,
            "beats_market": True,
            "detail": "学习后概率已优于原始模型和市场。",
        },
        recommendation_opportunity={
            "release_gate": {
                "formal_enabled": True,
                "detail": "正式推荐闸门已开放。",
                "gates": [],
            },
        },
        dashboard_contract={"status": "ok", "detail": "数据契约可用。"},
        clv_tracking={
            "tracked_count": 30,
            "available_count": 22,
            "avg_clv_return": -0.004,
            "positive_clv_rate": 0.45,
        },
    )
    gates = {gate["key"]: gate for gate in readiness["gates"]}

    assert readiness["production_ready"] is False
    assert readiness["summary"]["avg_clv_return"] == -0.004
    assert readiness["summary"]["clv_ready"] is False
    assert gates["closing_line_value"]["status"] == "blocked"
    assert gates["closing_line_value"]["title"] == "平均 CLV 为负"
    assert "生产发布至少需要 20 条可计算 CLV" in gates["closing_line_value"]["detail"]


def test_probability_governance_explains_shadow_guardrail_after_beating_market():
    rows = [
        {
            "settlement_status": "settled",
            "hit": hit,
            "learned_probability": learned,
            "market_probability": market,
            "model_probability": model,
        }
        for hit, learned, market, model in [
            (1, 0.80, 0.55, 0.52),
            (1, 0.76, 0.54, 0.52),
            (0, 0.18, 0.48, 0.55),
            (0, 0.22, 0.49, 0.56),
        ]
    ]

    governance = sources_module._dashboard_probability_governance(
        rows,
        learning_improved=True,
        beats_market=True,
        shadow_recalibration={
            "quality": {
                "walk_forward_brier_delta": 0.0068,
            }
        },
    )

    assert governance["status"] == "shadow_walk_forward_guardrail_active"
    assert governance["title"] == "走步验证保护"
    assert "学习概率已优于市场" in governance["detail"]
    assert "尚未跑赢市场" not in governance["detail"]
    assert governance["guardrails"] == ["影子模型走步验证未过"]
    assert governance["active_probability_source"] == "market_probability"
    assert governance["policy_mode"] == "shadow_walk_forward_guardrail"
    assert governance["production_ready"] is False


def test_adaptive_learning_plan_turns_quality_gaps_into_actions():
    learning_effectiveness = {
        "learning_improved": False,
        "beats_market": False,
        "deltas": {
            "learned_brier_minus_model": 0.0001,
            "learned_brier_minus_market": 0.0034,
        },
        "shadow_recalibration": {
            "status": "shadow_model_watch_only",
            "quality": {
                "walk_forward_sample_count": 36,
                "walk_forward_brier_delta": 0.0072,
            },
        },
    }
    prediction_quality = {
        "segments": [
            {
                "reason": "no_positive_edge",
                "label": "无正向边际",
                "settled_count": 63,
                "roi": -0.1583,
                "adjustment": {
                    "action": "suppress_reason",
                    "label": "降权过滤",
                    "weight_multiplier": 0.5,
                },
            },
            {
                "reason": "multi_bookmaker_snapshot_missing",
                "label": "缺少多公司赔率快照",
                "settled_count": 13,
                "roi": -0.0446,
                "adjustment": {
                    "action": "collect_more_samples",
                    "label": "继续采样",
                    "weight_multiplier": 1.0,
                },
            },
        ]
    }
    recommendation_opportunity = {
        "release_gate": {
            "formal_enabled": False,
            "signal_settled_count": 17,
            "min_signal_sample_count": 20,
            "gates": [
                {
                    "key": "shadow_walk_forward",
                    "status": "blocked",
                    "current": 0.0072,
                    "target": 0,
                    "detail": "走步验证未过。",
                }
            ],
        }
    }

    plan = sources_module._dashboard_adaptive_learning_plan(
        learning_effectiveness=learning_effectiveness,
        prediction_quality=prediction_quality,
        recommendation_opportunity=recommendation_opportunity,
    )
    actions = {action["key"]: action for action in plan["actions"]}

    assert plan["status"] == "retrain_required"
    assert plan["summary"]["blocked_action_count"] >= 2
    assert actions["freeze_shadow_recalibration"]["status"] == "blocked"
    assert actions["freeze_shadow_recalibration"]["evidence"] == "走步 Brier 变化 +0.0072"
    assert actions["keep_market_baseline"]["status"] == "blocked"
    assert actions["suppress_no_positive_edge"]["policy_effect"] == "正式推荐前权重 0.50"
    assert actions["collect_more_multi_bookmaker_snapshot_missing"]["current"] == 13
    assert actions["collect_signal_samples"]["current"] == 17
    assert actions["collect_signal_samples"]["target"] == 20


def test_dashboard_snapshot_exposes_contract_health_for_frontend_sections(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-contract-health",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": f"contract-health-{index}",
                "league": "契约联赛",
                "home_team": f"契约主队{index}",
                "away_team": f"契约客队{index}",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": f"契约主队{index} +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.86,
                "model_probability": 0.54,
                "calibrated_probability": 0.53,
                "market_probability": 0.52,
                "edge": -0.02,
                "recommendation": "no_value",
                "stake_level": "none",
                "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
            }
            for index in range(2)
        ],
        db_path=db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=20)
    contract = snapshot["dashboard_contract"]
    adaptive_plan = snapshot["adaptive_learning_plan"]
    sections = {section["key"]: section for section in contract["sections"]}

    assert contract["contract_version"] == "dashboard_contract_v1"
    assert contract["status"] == "warning"
    assert contract["summary"]["required_count"] == 9
    assert contract["summary"]["missing_required_count"] == 0
    assert adaptive_plan["status"] in {"collecting_samples", "retrain_required"}
    assert adaptive_plan["summary"]["action_count"] >= 1
    assert contract["policy"]["prediction_policy"] == "always_predict_and_backtest"
    assert contract["policy"]["formal_recommendation_enabled"] is False
    assert list(sections) == [
        "prediction_policy",
        "prediction_ledger",
        "settlement_backtest",
        "learning_effectiveness",
        "prediction_quality",
        "adaptive_learning_plan",
        "recommendation_gate",
        "odds_snapshots",
        "context_coverage",
    ]
    assert sections["prediction_policy"]["status"] == "ok"
    assert sections["prediction_policy"]["title"] == "持续预测回测"
    assert sections["prediction_ledger"]["current"] == 2
    assert sections["prediction_ledger"]["target"] == 1
    assert sections["prediction_ledger"]["frontend_visible"] is True
    assert sections["adaptive_learning_plan"]["frontend_visible"] is True
    assert "自学习" in sections["adaptive_learning_plan"]["label"]
    assert sections["settlement_backtest"]["status"] == "warning"
    assert sections["recommendation_gate"]["status"] == "warning"
    assert "继续预测" in sections["recommendation_gate"]["detail"]
    assert all(section["label"] for section in contract["sections"])


def test_dashboard_model_governance_reads_legacy_candidate_model_evidence(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-legacy-model-evidence",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "legacy-model-evidence-1",
                "league": "旧样本联赛",
                "home_team": "旧样本主队",
                "away_team": "旧样本客队",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "旧样本主队 +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.9,
                "model_probability": 0.57,
                "calibrated_probability": 0.55,
                "market_probability": 0.526316,
                "edge": 0.045,
                "recommendation": "condition_observe",
                "stake_level": "watch",
                "raw": {
                    "kind": "learning_observation",
                    "best_candidate": {
                        "market": "asian_handicap",
                        "selection": "旧样本主队 +0.5",
                        "selection_key": "home_cover",
                        "line": 0.5,
                        "decimal_odds": 1.9,
                        "model_probability": 0.57,
                        "market_probability": 0.526316,
                        "edge": 0.045,
                        "edge_source": "model_engine",
                        "probability_source": "MCP Dixon-Coles adjusted scoreline distribution",
                        "recommendation": "condition_observe",
                    },
                },
            }
        ],
        db_path=db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=20)
    governance = snapshot["model_governance"]
    checks = {item["key"]: item for item in governance["checks"]}

    assert governance["summary"]["record_count"] == 1
    assert governance["summary"]["model_engine_count"] == 1
    assert governance["summary"]["model_available_count"] == 1
    assert governance["summary"]["market_anchor_count"] == 1
    assert governance["summary"]["historical_rho_count"] == 0
    assert governance["method_counts"][sources_module.model_engine.MODEL_ENGINE_METHOD] == 1
    assert governance["rho"]["source_counts"]["not_persisted_legacy_candidate"] == 1
    assert checks["market_anchoring"]["status"] == "ok"
    assert checks["dixon_coles_rho"]["status"] == "warning"


def test_shortlist_pick_carries_compact_model_engine_evidence():
    pick = sources_module._shortlist_pick_from_analysis(
        {
            "match": {"home_team": "模型主队", "away_team": "模型客队"},
            "best_candidate": {
                "market": "asian_handicap",
                "selection": "模型主队 -0.5",
                "selection_key": "home_cover",
                "decimal_odds": 1.9,
                "model_probability": 0.61,
                "calibrated_probability": 0.61,
                "edge": 0.08,
                "recommendation": "immediate_bet",
            },
            "betting_decision_support": {
                "confidence": 0.61,
                "model_engine": {
                    "available": True,
                    "version": "scoreline-model-v1",
                    "method": "dixon_coles_market_anchored_grid",
                    "dixon_coles": {"rho": -0.04, "rho_source": "market_snapshot_grid_fit"},
                    "fitted_market_targets": {"asian_handicap": True},
                    "scoreline_distribution": [{"home_goals": 0, "away_goals": 0, "probability": 0.1}],
                    "model_quality": {"fallback_used": False},
                },
            },
        },
        mode="balanced",
    )

    assert pick["model_engine"]["method"] == "dixon_coles_market_anchored_grid"
    assert pick["model_engine"]["dixon_coles"]["rho"] == -0.04
    assert pick["model_engine"]["fitted_market_targets"]["asian_handicap"] is True
    assert "scoreline_distribution" not in pick["model_engine"]


def test_dashboard_shadow_predictions_with_snapshots_are_not_marked_as_reanalysis_backlog(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_shadow_prediction_records(
        [
            {
                "run_id": "cycle-shadow-snapshot",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "decision": "rejected",
                "rejection_reason": "multi_bookmaker_snapshot_missing",
                "match_id": "shadow-with-snapshot",
                "league": "影子联赛",
                "home_team": "影子主队",
                "away_team": "影子客队",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "影子主队 +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.88,
                "model_probability": 0.62,
                "calibrated_probability": 0.62,
                "market_probability": 0.51,
                "edge": 0.055,
                "recommendation": "immediate_bet",
                "stake_level": "small",
            }
        ],
        db_path=db_path,
    )
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:shadow-with-snapshot",
                event_id="shadow-with-snapshot",
                league="影子联赛",
                home_team="影子主队",
                away_team="影子客队",
                kickoff_utc="2026-05-25T12:00:00+00:00",
                bookmaker="公司A",
                market_type="asian_handicap",
                selection="影子主队 +0.5",
                decimal_odds=1.88,
                line=0.5,
                source_time_utc="2026-05-25T11:50:00+00:00",
                fetched_at_utc="2026-05-25T11:55:00+00:00",
                raw={},
            )
        ],
        db_path=market_db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, market_db_path=market_db_path, limit=20)
    row = snapshot["prediction_ledger"][0]
    candidate = snapshot["recommendation_opportunity"]["top_candidates"][0]

    assert row["source"] == "shadow_prediction"
    assert row["has_odds_snapshot"] is True
    assert row["rejection_reason"] == "shadow_prediction_reference_only"
    assert candidate["primary_blocker"] == "shadow_prediction_reference_only"
    assert snapshot["recommendation_opportunity"]["reanalysis_backlog_count"] == 0


def test_reanalyze_snapshot_backlog_promotes_observation_when_odds_are_now_complete(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-reanalysis-before",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "reanalyze-ready",
                "league": "复算联赛",
                "home_team": "复算主队",
                "away_team": "复算客队",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "复算主队 +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.88,
                "model_probability": 0.61,
                "calibrated_probability": 0.61,
                "market_probability": 0.51,
                "edge": 0.04,
                "expected_multiplier": 1.1468,
                "recommendation": "immediate_bet",
                "stake_level": "small",
                "raw": {
                    "kind": "learning_observation",
                    "reason": "multi_bookmaker_snapshot_missing",
                    "data_completeness": {
                        "available_blocks": ["schedule", "moneyline_1x2", "asian_handicap", "over_under", "lineup"],
                        "missing_blocks": ["multi_bookmaker_snapshot"],
                    },
                },
            }
        ],
        db_path=db_path,
    )
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:reanalyze-ready",
                event_id="reanalyze-ready",
                league="复算联赛",
                home_team="复算主队",
                away_team="复算客队",
                kickoff_utc="2026-05-25T12:00:00+00:00",
                bookmaker="公司A",
                market_type="asian_handicap",
                selection="复算主队 +0.5",
                decimal_odds=1.88,
                line=0.5,
                source_time_utc="2026-05-25T11:50:00+00:00",
                fetched_at_utc="2026-05-25T11:55:00+00:00",
                raw={},
            )
        ],
        db_path=market_db_path,
    )
    calls = []

    async def fake_analyze_single_match(query, **kwargs):
        calls.append((query, kwargs))
        return {
            "status": "ok",
            "match": {
                "match_id": "reanalyze-ready",
                "source_name": "dongqiudi",
                "league": "复算联赛",
                "home_team": "复算主队",
                "away_team": "复算客队",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
            },
            "final_decision": {"headline": "复算后可正式跟踪", "recommendation": "immediate_bet"},
            "final_execution_advice": {"headline": "最终执行：正式跟踪", "action": "bet_now"},
            "best_candidate": {
                "market": "asian_handicap",
                "selection": "复算主队 +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "recommendation": "immediate_bet",
                "edge": 0.055,
                "model_probability": 0.63,
                "calibrated_probability": 0.63,
                "market_probability": 0.51,
                "expected_multiplier": 1.1844,
                "stake_level": "small",
                "decimal_odds": 1.88,
            },
            "market_candidates": [],
            "betting_decision_support": {"blocking_flags": [], "caution_flags": [], "confidence": 0.63},
            "analysis_pack": {
                "data_coverage": {
                    "blocks": {
                        "schedule": True,
                        "moneyline_1x2": True,
                        "asian_handicap": True,
                        "over_under": True,
                        "multi_bookmaker_snapshot": True,
                        "lineup": True,
                    }
                }
            },
            "quality": {"is_bettable_input": True},
            "match_context": {"source_name": "dongqiudi", "match_id": "reanalyze-ready"},
        }

    monkeypatch.setattr(sources_module, "analyze_single_match", fake_analyze_single_match)

    result = asyncio.run(
        sources_module.reanalyze_snapshot_backlog(
            as_of="2026-05-25T19:55:00+08:00",
            db_path=db_path,
            market_db_path=market_db_path,
            limit=5,
        )
    )
    records = learning_store.list_recommendation_records(db_path=db_path, limit=10)
    record = records[0]
    snapshot = sources_module.dashboard_snapshot(db_path=db_path, market_db_path=market_db_path, limit=10)

    assert result["status"] == "ok"
    assert result["reanalyzed_count"] == 1
    assert result["formal_promoted_count"] == 1
    assert result["still_observation_count"] == 0
    assert calls[0][0] == "复算主队 vs 复算客队"
    assert calls[0][1]["include_source_probe"] is False
    assert record["mode"] == "balanced"
    assert record["raw"]["kind"] == "snapshot_reanalysis"
    assert record["raw"]["previous_reason"] == "multi_bookmaker_snapshot_missing"
    assert snapshot["recommendation_opportunity"]["formal_count"] == 1
    assert snapshot["recommendation_opportunity"]["reanalysis_backlog_count"] == 0


def test_reanalyze_snapshot_backlog_skips_records_outside_near_kickoff_window(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-reanalysis-too-early",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "too-early-reanalysis",
                "league": "复算联赛",
                "home_team": "远期主队",
                "away_team": "远期客队",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "远期客队 +0.5",
                "selection_key": "away_cover",
                "line": 0.5,
                "decimal_odds": 1.88,
                "model_probability": 0.53,
                "recommendation": "no_value",
                "raw": {
                    "kind": "learning_observation",
                    "reason": "multi_bookmaker_snapshot_missing",
                    "data_completeness": {
                        "available_blocks": ["schedule", "asian_handicap"],
                        "missing_blocks": ["multi_bookmaker_snapshot"],
                    },
                },
            }
        ],
        db_path=db_path,
    )
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:too-early-reanalysis",
                event_id="too-early-reanalysis",
                league="复算联赛",
                home_team="远期主队",
                away_team="远期客队",
                kickoff_utc="2026-05-25T12:00:00+00:00",
                bookmaker="公司A",
                market_type="asian_handicap",
                selection="远期客队 +0.5",
                decimal_odds=1.88,
                line=0.5,
                source_time_utc="2026-05-25T07:00:00+00:00",
                fetched_at_utc="2026-05-25T07:00:00+00:00",
                raw={},
            )
        ],
        db_path=market_db_path,
    )

    async def fake_analyze_single_match(*args, **kwargs):
        raise AssertionError("far-future reanalysis should not call analysis")

    monkeypatch.setattr(sources_module, "analyze_single_match", fake_analyze_single_match)

    result = asyncio.run(
        sources_module.reanalyze_snapshot_backlog(
            as_of="2026-05-25T15:00:00+08:00",
            db_path=db_path,
            market_db_path=market_db_path,
            limit=5,
        )
    )

    assert result["reanalyzed_count"] == 0
    assert result["skipped_count"] == 1
    assert result["results"][0]["reason"] == "outside_near_kickoff_window"


def test_reanalyze_snapshot_backlog_uses_fuzzy_snapshot_coverage(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-reanalysis-fuzzy-before",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "boca-fuzzy",
                "league": "阿甲女",
                "home_team": "博卡青年女足",
                "away_team": "飓风女足",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "博卡青年女足 -1.5",
                "selection_key": "home_cover",
                "line": -1.5,
                "decimal_odds": 1.86,
                "model_probability": 0.62,
                "calibrated_probability": 0.62,
                "market_probability": 0.52,
                "edge": 0.04,
                "expected_multiplier": 1.1532,
                "recommendation": "immediate_bet",
                "stake_level": "small",
                "raw": {
                    "kind": "learning_observation",
                    "reason": "multi_bookmaker_snapshot_missing",
                    "data_completeness": {
                        "available_blocks": ["schedule", "moneyline_1x2", "asian_handicap", "over_under", "lineup"],
                        "missing_blocks": ["multi_bookmaker_snapshot"],
                    },
                },
            }
        ],
        db_path=db_path,
    )
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:boca-fuzzy",
                event_id="boca-fuzzy",
                league="阿甲女",
                home_team="博卡女足",
                away_team="飓风女足",
                kickoff_utc="2026-05-25T12:00:00+00:00",
                bookmaker="公司A",
                market_type="asian_handicap",
                selection="博卡女足 -1.5",
                decimal_odds=1.86,
                line=-1.5,
                source_time_utc="2026-05-25T11:50:00+00:00",
                fetched_at_utc="2026-05-25T11:55:00+00:00",
                raw={},
            )
        ],
        db_path=market_db_path,
    )
    calls = []

    async def fake_analyze_single_match(query, **kwargs):
        calls.append((query, kwargs))
        return {
            "status": "ok",
            "match": {
                "match_id": "boca-fuzzy",
                "source_name": "dongqiudi",
                "league": "阿甲女",
                "home_team": "博卡青年女足",
                "away_team": "飓风女足",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
            },
            "best_candidate": {
                "market": "asian_handicap",
                "selection": "博卡青年女足 -1.5",
                "selection_key": "home_cover",
                "line": -1.5,
                "recommendation": "immediate_bet",
                "edge": 0.055,
                "model_probability": 0.64,
                "calibrated_probability": 0.64,
                "market_probability": 0.52,
                "expected_multiplier": 1.1904,
                "stake_level": "small",
                "decimal_odds": 1.86,
            },
            "market_candidates": [],
            "betting_decision_support": {"blocking_flags": [], "caution_flags": [], "confidence": 0.64},
            "analysis_pack": {
                "data_coverage": {
                    "blocks": {
                        "schedule": True,
                        "moneyline_1x2": True,
                        "asian_handicap": True,
                        "over_under": True,
                        "multi_bookmaker_snapshot": True,
                        "lineup": True,
                    }
                }
            },
            "quality": {"is_bettable_input": True},
            "match_context": {"source_name": "dongqiudi", "match_id": "boca-fuzzy"},
        }

    monkeypatch.setattr(sources_module, "analyze_single_match", fake_analyze_single_match)

    result = asyncio.run(
        sources_module.reanalyze_snapshot_backlog(
            as_of="2026-05-25T19:55:00+08:00",
            db_path=db_path,
            market_db_path=market_db_path,
            limit=5,
        )
    )

    assert result["reanalyzed_count"] == 1
    assert calls[0][0] == "博卡青年女足 vs 飓风女足"


def test_reanalyze_snapshot_backlog_does_not_blank_record_when_analysis_fails(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-reanalysis-failure-before",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "failure-preserve",
                "league": "保留联赛",
                "home_team": "保留主队",
                "away_team": "保留客队",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "保留主队 +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.88,
                "model_probability": 0.61,
                "calibrated_probability": 0.61,
                "market_probability": 0.51,
                "edge": 0.04,
                "expected_multiplier": 1.1468,
                "recommendation": "immediate_bet",
                "stake_level": "small",
                "raw": {
                    "kind": "learning_observation",
                    "reason": "multi_bookmaker_snapshot_missing",
                    "match_context": {
                        "source_name": "dongqiudi",
                        "match_id": "failure-preserve",
                        "lineup": {
                            "base": {"weather": "小雨", "referee": "测试裁判"},
                            "lineup_status": {"lineup_basis": "official_lineups"},
                            "lineup_analysis": {"available": True, "can_use_for_analysis": True, "warnings": []},
                            "official_lineups": {
                                "home": {"lineups": [{"name": "保留前锋"}]},
                                "away": {"lineups": [{"name": "保留门将"}]},
                            },
                        },
                    },
                    "data_completeness": {
                        "available_blocks": ["schedule", "moneyline_1x2", "asian_handicap", "over_under", "lineup"],
                        "missing_blocks": ["multi_bookmaker_snapshot"],
                    },
                },
            }
        ],
        db_path=db_path,
    )
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:failure-preserve",
                event_id="failure-preserve",
                league="保留联赛",
                home_team="保留主队",
                away_team="保留客队",
                kickoff_utc="2026-05-25T12:00:00+00:00",
                bookmaker="公司A",
                market_type="asian_handicap",
                selection="保留主队 +0.5",
                decimal_odds=1.88,
                line=0.5,
                source_time_utc="2026-05-25T11:50:00+00:00",
                fetched_at_utc="2026-05-25T11:55:00+00:00",
                raw={},
            )
        ],
        db_path=market_db_path,
    )

    async def fake_analyze_single_match(query, **kwargs):
        return {"status": "error", "error": "upstream timeout"}

    monkeypatch.setattr(sources_module, "analyze_single_match", fake_analyze_single_match)

    result = asyncio.run(
        sources_module.reanalyze_snapshot_backlog(
            as_of="2026-05-25T19:55:00+08:00",
            db_path=db_path,
            market_db_path=market_db_path,
            limit=5,
        )
    )
    record = learning_store.list_recommendation_records(db_path=db_path, limit=1)[0]
    detail = sources_module.dashboard_match_detail(f"recommendation:{record['id']}", db_path=db_path)

    assert result["reanalyzed_count"] == 0
    assert result["failed_count"] == 1
    assert record["league"] == "保留联赛"
    assert record["home_team"] == "保留主队"
    assert record["away_team"] == "保留客队"
    assert record["raw"]["kind"] == "learning_observation"
    assert detail["match_context"]["weather"]["text"] == "小雨"
    assert detail["match_context"]["referee"]["text"] == "测试裁判"


def test_dashboard_snapshot_hides_blank_snapshot_reanalysis_records(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-visible-good",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "visible-good",
                "league": "有效联赛",
                "home_team": "有效主队",
                "away_team": "有效客队",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "有效主队 +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.88,
                "model_probability": 0.61,
                "calibrated_probability": 0.61,
                "market_probability": 0.51,
                "edge": 0.04,
                "expected_multiplier": 1.1468,
                "recommendation": "immediate_bet",
                "stake_level": "small",
                "raw": {
                    "kind": "learning_observation",
                    "reason": "multi_bookmaker_snapshot_missing",
                    "match_context": {"source_name": "dongqiudi", "match_id": "visible-good"},
                },
            },
            {
                "run_id": "cycle-corrupt-reanalysis",
                "tool": "snapshot_reanalysis",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "",
                "league": "",
                "home_team": "",
                "away_team": "",
                "market": "",
                "selection": "",
                "recommendation": "",
                "raw": {
                    "kind": "snapshot_reanalysis",
                    "result": "still_observation",
                    "reason": "analysis_failed",
                    "match": {},
                    "match_context": {},
                },
            },
        ],
        db_path=db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=10)
    detail = sources_module.dashboard_match_detail("recommendation:2", db_path=db_path)

    assert snapshot["context_coverage"]["total_count"] == 1
    assert all(row["matchup"] != "vs" for row in snapshot["prediction_ledger"])
    assert snapshot["kpis"]["observation_count"] == 1
    assert detail["status"] == "not_found"


def test_dashboard_does_not_label_settled_rows_as_waiting_reanalysis(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-settled-reanalysis-label",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "settled-with-late-snapshot",
                "league": "测试联赛",
                "home_team": "已结主队",
                "away_team": "已结客队",
                "kickoff_utc_plus_8": "2026-05-25T18:00:00+08:00",
                "market": "asian_handicap",
                "selection": "已结主队 +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.88,
                "model_probability": 0.61,
                "calibrated_probability": 0.61,
                "market_probability": 0.51,
                "edge": 0.04,
                "expected_multiplier": 1.1468,
                "recommendation": "immediate_bet",
                "stake_level": "small",
                "settlement_status": "settled",
                "raw": {
                    "kind": "learning_observation",
                    "reason": "multi_bookmaker_snapshot_missing",
                    "data_completeness": {
                        "available_blocks": ["schedule", "moneyline_1x2", "asian_handicap", "over_under"],
                        "missing_blocks": ["multi_bookmaker_snapshot"],
                    },
                },
            }
        ],
        db_path=db_path,
    )
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:settled-with-late-snapshot",
                event_id="settled-with-late-snapshot",
                league="测试联赛",
                home_team="已结主队",
                away_team="已结客队",
                kickoff_utc="2026-05-25T10:00:00+00:00",
                bookmaker="公司A",
                market_type="asian_handicap",
                selection="已结主队 +0.5",
                decimal_odds=1.88,
                line=0.5,
                source_time_utc="2026-05-25T09:50:00+00:00",
                fetched_at_utc="2026-05-25T09:55:00+00:00",
                raw={},
            )
        ],
        db_path=market_db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, market_db_path=market_db_path, limit=10)
    row = snapshot["prediction_ledger"][0]

    assert snapshot["recommendation_opportunity"]["reanalysis_backlog_count"] == 0
    assert row["settlement_status"] == "settled"
    assert row["rejection_reason"] == "multi_bookmaker_snapshot_missing"
    assert row["prediction_diagnostic"]["primary_reason"] == "multi_bookmaker_snapshot_missing"


def test_dashboard_learning_events_surface_snapshot_reanalysis_status(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    previous = sources_module.AUTO_LEARNING_STATE.get("last_snapshot_reanalysis")
    sources_module.AUTO_LEARNING_STATE["last_snapshot_reanalysis"] = {
        "status": "ok",
        "reanalyzed_count": 3,
        "formal_promoted_count": 1,
        "still_observation_count": 2,
        "failed_count": 0,
        "at_utc": "2026-05-25T12:10:00+00:00",
    }
    try:
        snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=10)
    finally:
        if previous is None:
            sources_module.AUTO_LEARNING_STATE.pop("last_snapshot_reanalysis", None)
        else:
            sources_module.AUTO_LEARNING_STATE["last_snapshot_reanalysis"] = previous

    events = [event for event in snapshot["learning_events"] if event["kind"] == "snapshot_reanalysis"]

    assert events
    assert events[0]["title"] == "赔率补齐复算"
    assert events[0]["detail"] == "已复算 3 场，升级正式推荐 1 场，继续观察 2 场，失败 0 场。"


def test_dashboard_record_detail_exposes_persisted_pick_evidence(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-detail",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "match_id": "detail-pick",
                "league": "日职联",
                "home_team": "清水鼓动",
                "away_team": "大阪钢巴",
                "kickoff_utc_plus_8": "2026-05-25T19:00:00+08:00",
                "market": "asian_handicap",
                "selection": "大阪钢巴 +0.25",
                "selection_key": "away_cover",
                "line": 0.25,
                "decimal_odds": 1.82,
                "model_probability": 0.586,
                "calibrated_probability": 0.569,
                "market_probability": 0.549,
                "edge": 0.02,
                "expected_multiplier": 1.035,
                "recommendation": "immediate_bet",
                "stake_level": "small",
                "risk_flags": ["lineup_unavailable"],
                "caution_flags": ["low_settled_sample"],
                "raw": {
                    "final_execution_advice": {
                        "action": "paper_track",
                        "reason": "balanced threshold passed",
                    },
                    "data_completeness": {
                        "odds": True,
                        "schedule": True,
                        "lineup": False,
                    },
                    "learning_policy": {
                        "live_calibration": {
                            "active": False,
                            "sample_count": 2,
                        }
                    },
                    "market_candidates": [
                        {
                            "selection": "大阪钢巴 +0.25",
                            "decimal_odds": 1.82,
                            "calibrated_probability": 0.569,
                            "edge": 0.02,
                        },
                        {
                            "selection": "清水鼓动 -0.25",
                            "decimal_odds": 2.01,
                            "calibrated_probability": 0.493,
                            "edge": -0.01,
                        },
                    ],
                },
            }
        ],
        db_path=db_path,
    )
    record = learning_store.list_recommendation_records(db_path=db_path, status="open", limit=1)[0]

    detail = sources_module.dashboard_record_detail(record["id"], db_path=db_path)

    assert detail["status"] == "ok"
    assert detail["record"]["matchup"] == "清水鼓动 vs 大阪钢巴"
    assert detail["evidence"]["final_execution_advice"]["action"] == "paper_track"
    assert detail["evidence"]["data_completeness"]["odds"] is True
    assert detail["evidence"]["live_calibration"]["sample_count"] == 2
    assert detail["evidence"]["market_candidates"][0]["selection"] == "大阪钢巴 +0.25"
    assert detail["evidence"]["core_metrics"]["expected_multiplier"] == 1.035
    assert detail["strategy_state"]["market"] == "asian_handicap"
    assert detail["policy"]["read_only"] is True


def test_dashboard_record_detail_returns_not_found_for_unknown_id(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")

    detail = sources_module.dashboard_record_detail(404, db_path=db_path)

    assert detail["status"] == "not_found"
    assert detail["record_id"] == "404"


def test_dashboard_match_detail_downgrades_context_coverage_without_persisted_context(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-context-gap",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "league": "资料联赛",
                "home_team": "缺上下文主队",
                "away_team": "缺上下文客队",
                "kickoff_utc_plus_8": "2026-05-25T19:00:00+08:00",
                "market": "asian_handicap",
                "selection": "缺上下文主队 -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.88,
                "model_probability": 0.62,
                "calibrated_probability": 0.61,
                "market_probability": 0.532,
                "edge": 0.078,
                "expected_multiplier": 1.1468,
                "recommendation": "immediate_bet",
                "stake_level": "small",
                "raw": {
                    "data_completeness": {
                        "available_blocks": [
                            "schedule",
                            "moneyline_1x2",
                            "asian_handicap",
                            "over_under",
                            "weather",
                            "referee",
                        ],
                        "missing_blocks": ["lineup"],
                        "core_markets_ready": True,
                        "ratio": 0.857143,
                    }
                },
            }
        ],
        db_path=db_path,
    )
    record = learning_store.list_recommendation_records(db_path=db_path, limit=1)[0]

    detail = sources_module.dashboard_match_detail(f"recommendation:{record['id']}", db_path=db_path)

    assert detail["match_context"]["weather"]["available"] is False
    assert detail["match_context"]["referee"]["available"] is False
    assert "weather" not in detail["evidence"]["data_completeness"]["available_blocks"]
    assert "referee" not in detail["evidence"]["data_completeness"]["available_blocks"]
    assert "weather" in detail["evidence"]["data_completeness"]["missing_blocks"]
    assert "referee" in detail["evidence"]["data_completeness"]["missing_blocks"]


def test_dashboard_match_detail_reads_dongqiudi_lineup_field_as_venue(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-dongqiudi-context",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "league": "保甲",
                "home_team": "瓦尔纳黑海",
                "away_team": "阿尔达",
                "kickoff_utc_plus_8": "2026-05-25T22:45:00+08:00",
                "market": "asian_handicap",
                "selection": "瓦尔纳黑海 -0.25",
                "selection_key": "home_cover",
                "line": -0.25,
                "decimal_odds": 2.04,
                "model_probability": 0.51,
                "calibrated_probability": 0.51,
                "market_probability": 0.49,
                "edge": 0.02,
                "expected_multiplier": 1.0404,
                "recommendation": "condition_observe",
                "stake_level": "none",
                "raw": {
                    "kind": "learning_observation",
                    "match_context": {
                        "lineup": {
                            "base": {
                                "field": "提查球场",
                                "weather": "局部有云",
                                "temperature": "24°C",
                                "referee": "Kristiyan Kolev",
                            },
                            "lineup_status": {"lineup_basis": "official_lineups"},
                            "lineup_analysis": {
                                "available": True,
                                "can_use_for_analysis": True,
                                "home": {"formation": "4-2-3-1", "starter_count": 11},
                                "away": {"formation": "4-3-3", "starter_count": 11},
                                "warnings": [],
                            },
                            "official_lineups": {
                                "home": {"lineups": [{"name": "主队前锋", "position": "前锋"}]},
                                "away": {"lineups": [{"name": "客队门将", "position": "门将"}]},
                            },
                        }
                    },
                },
            }
        ],
        db_path=db_path,
    )
    record = learning_store.list_recommendation_records(db_path=db_path, limit=1)[0]

    detail = sources_module.dashboard_match_detail(f"recommendation:{record['id']}", db_path=db_path)

    assert detail["match_context"]["venue"]["text"] == "提查球场"
    assert detail["match_context"]["weather"]["text"] == "局部有云"
    assert detail["match_context"]["referee"]["text"] == "Kristiyan Kolev"
    assert detail["match_context"]["lineup"]["available"] is True


def test_dashboard_match_detail_marks_source_empty_context_separately(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-dongqiudi-source-empty",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "league": "资料联赛",
                "home_team": "资料主队",
                "away_team": "资料客队",
                "match_id": "543210",
                "kickoff_utc_plus_8": "2026-05-25T22:45:00+08:00",
                "market": "asian_handicap",
                "selection": "资料主队 -0.25",
                "selection_key": "home_cover",
                "line": -0.25,
                "decimal_odds": 1.92,
                "model_probability": 0.52,
                "calibrated_probability": 0.52,
                "market_probability": 0.50,
                "edge": 0.02,
                "expected_multiplier": 0.9984,
                "recommendation": "condition_observe",
                "stake_level": "none",
                "raw": {
                    "context_source_name": "dongqiudi",
                    "context_match_id": "543210",
                    "match_context": {
                        "match_id": "543210",
                        "lineup": {
                            "base": {
                                "field": "暂无信息",
                                "weather": "晴",
                                "referee": "暂无信息",
                            },
                            "lineup_status": {"lineup_basis": "not_available"},
                            "lineup_analysis": {"available": False, "warnings": ["lineup_unavailable"]},
                            "official_lineups": {},
                        }
                    },
                },
            }
        ],
        db_path=db_path,
    )
    record = learning_store.list_recommendation_records(db_path=db_path, limit=1)[0]

    detail = sources_module.dashboard_match_detail(f"recommendation:{record['id']}", db_path=db_path)

    assert detail["match_context"]["source"]["status"] == "matched"
    assert detail["match_context"]["source"]["label"] == "懂球帝"
    assert detail["match_context"]["source"]["match_id"] == "543210"
    assert detail["match_context"]["venue"]["available"] is False
    assert detail["match_context"]["venue"]["status"] == "source_empty"
    assert detail["match_context"]["venue"]["text"] == "源站暂无信息"
    assert detail["match_context"]["weather"]["available"] is True
    assert detail["match_context"]["referee"]["status"] == "source_empty"


def test_dashboard_match_detail_explains_source_attempts_when_leisu_has_only_odds(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-source-attempts",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "league": "乌兹杯",
                "home_team": "纳萨夫",
                "away_team": "古佐尔警察",
                "match_id": "54435613",
                "kickoff_utc_plus_8": "2026-05-26T03:51:00+08:00",
                "market": "asian_handicap",
                "selection": "纳萨夫 -1.5",
                "selection_key": "home_cover",
                "line": -1.5,
                "decimal_odds": 1.90,
                "model_probability": 0.52,
                "calibrated_probability": 0.52,
                "market_probability": 0.50,
                "edge": 0.02,
                "expected_multiplier": 0.988,
                "recommendation": "no_value",
                "stake_level": "none",
                "raw": {
                    "context_source_name": "dongqiudi",
                    "context_match_id": "54435613",
                    "match_context": {
                        "match_id": "54435613",
                        "lineup": {
                            "base": {
                                "field": "暂无信息",
                                "weather": "暂无信息",
                                "referee": "暂无信息",
                            },
                            "lineup_status": {"lineup_basis": "unavailable"},
                            "lineup_analysis": {"available": False, "warnings": ["lineup_unavailable"]},
                        },
                    },
                },
            }
        ],
        db_path=db_path,
    )
    record = learning_store.list_recommendation_records(db_path=db_path, limit=1)[0]
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:4528570",
                event_id="4528570",
                league="乌兹杯",
                home_team="纳萨夫",
                away_team="古佐尔警察",
                kickoff_utc="",
                bookmaker="公司A",
                market_type="asian_handicap",
                selection="纳萨夫 -1.5",
                decimal_odds=1.90,
                line=-1.5,
                source_time_utc="2026-05-25T19:50:00+00:00",
                fetched_at_utc="2026-05-25T19:55:00+00:00",
                raw={"match_resolution_reason": "direct_snapshot_match"},
            )
        ],
        db_path=market_db_path,
    )

    detail = sources_module.dashboard_match_detail(
        f"recommendation:{record['id']}",
        db_path=db_path,
        market_db_path=market_db_path,
    )

    attempts = detail["match_context"]["source_attempts"]
    assert attempts[0]["label"] == "懂球帝"
    assert attempts[0]["status"] == "matched"
    assert attempts[0]["match_id"] == "54435613"
    assert attempts[0]["field_statuses"]["venue"] == "source_empty"
    assert attempts[0]["field_statuses"]["lineup"] == "source_empty"
    leisu_attempt = next(item for item in attempts if item["provider"] == "leisu")
    assert leisu_attempt["status"] == "odds_matched_context_not_collected"
    assert leisu_attempt["match_id"] == "4528570"
    assert "赔率快照 1 条" in leisu_attempt["detail"]
    assert "本条记录尚未保存雷速赛事情报" in leisu_attempt["detail"]
    assert leisu_attempt["urls"]["mobile_detail"].endswith("/live/detail-4528570")


def test_dashboard_match_detail_does_not_call_live_context_by_default(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-no-live-detail-context",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "league": "乌兹杯",
                "home_team": "纳萨夫",
                "away_team": "古佐尔警察",
                "match_id": "54435613",
                "kickoff_utc_plus_8": "2026-05-26T03:51:00+08:00",
                "market": "asian_handicap",
                "selection": "纳萨夫 -1.5",
                "selection_key": "home_cover",
                "line": -1.5,
                "decimal_odds": 1.90,
                "model_probability": 0.52,
                "calibrated_probability": 0.52,
                "market_probability": 0.50,
                "recommendation": "no_value",
                "raw": {
                    "context_source_name": "dongqiudi",
                    "match_context": {
                        "match_id": "54435613",
                        "lineup": {
                            "base": {
                                "field": "暂无信息",
                                "weather": "暂无信息",
                                "referee": "暂无信息",
                            },
                            "lineup_status": {"lineup_basis": "unavailable"},
                            "lineup_analysis": {"available": False},
                        },
                    },
                },
            }
        ],
        db_path=db_path,
    )
    record = learning_store.list_recommendation_records(db_path=db_path, limit=1)[0]
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:4528570",
                event_id="4528570",
                league="乌兹杯",
                home_team="纳萨夫",
                away_team="古佐尔警察",
                kickoff_utc="",
                bookmaker="公司A",
                market_type="asian_handicap",
                selection="纳萨夫 -1.5",
                decimal_odds=1.90,
                line=-1.5,
                source_time_utc="2026-05-25T19:50:00+00:00",
                fetched_at_utc="2026-05-25T19:55:00+00:00",
                raw={"match_resolution_reason": "direct_snapshot_match"},
            )
        ],
        db_path=market_db_path,
    )

    async def fail_if_called(match_id):
        raise AssertionError(f"unexpected live context fetch: {match_id}")

    monkeypatch.setenv("FOOTBALL_DATA_LEISU_CONTEXT_ENABLED", "true")
    monkeypatch.setattr(sources_module, "leisu_match_context", fail_if_called)

    detail = sources_module.dashboard_match_detail(
        f"recommendation:{record['id']}",
        db_path=db_path,
        market_db_path=market_db_path,
    )

    assert detail["policy"]["data_rule"] == "Match details read persisted prediction samples, context, and odds snapshots only."
    leisu_attempt = next(item for item in detail["match_context"]["source_attempts"] if item["provider"] == "leisu")
    assert leisu_attempt["status"] == "odds_matched_context_not_collected"


def test_dashboard_match_detail_enriches_missing_context_from_leisu_snapshot(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-live-leisu-context",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "league": "乌兹杯",
                "home_team": "纳萨夫",
                "away_team": "古佐尔警察",
                "match_id": "54435613",
                "kickoff_utc_plus_8": "2026-05-26T03:51:00+08:00",
                "market": "asian_handicap",
                "selection": "纳萨夫 -1.5",
                "selection_key": "home_cover",
                "line": -1.5,
                "decimal_odds": 1.90,
                "model_probability": 0.52,
                "calibrated_probability": 0.52,
                "market_probability": 0.50,
                "edge": 0.02,
                "expected_multiplier": 0.988,
                "recommendation": "no_value",
                "stake_level": "none",
                "raw": {
                    "context_source_name": "dongqiudi",
                    "context_match_id": "54435613",
                    "match_context": {
                        "match_id": "54435613",
                        "source_name": "dongqiudi",
                        "lineup": {
                            "base": {
                                "field": "暂无信息",
                                "weather": "暂无信息",
                                "referee": "暂无信息",
                            },
                            "lineup_status": {"lineup_basis": "unavailable"},
                            "lineup_analysis": {"available": False, "warnings": ["lineup_unavailable"]},
                        },
                    },
                },
            }
        ],
        db_path=db_path,
    )
    record = learning_store.list_recommendation_records(db_path=db_path, limit=1)[0]
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:4528570",
                event_id="4528570",
                league="乌兹杯",
                home_team="纳萨夫",
                away_team="古佐尔警察",
                kickoff_utc="",
                bookmaker="公司A",
                market_type="asian_handicap",
                selection="纳萨夫 -1.5",
                decimal_odds=1.90,
                line=-1.5,
                source_time_utc="2026-05-25T19:50:00+00:00",
                fetched_at_utc="2026-05-25T19:55:00+00:00",
                raw={"match_resolution_reason": "direct_snapshot_match"},
            )
        ],
        db_path=market_db_path,
    )

    async def fake_leisu_match_context(match_id):
        assert match_id == "4528570"
        return sources_module.normalize_leisu_match_context(
            match_id,
            lineup_payload={
                "venue": {"name": "纳萨夫体育场", "city": "卡尔希"},
                "referee": {},
                "home": [],
                "away": [],
            },
            detail_payload={"tlive": [{"data": "本场比赛天气情况：晴"}]},
        )

    monkeypatch.setenv("FOOTBALL_DATA_LEISU_CONTEXT_ENABLED", "true")
    monkeypatch.setattr(sources_module, "leisu_match_context", fake_leisu_match_context)

    detail = sources_module.dashboard_match_detail(
        f"recommendation:{record['id']}",
        db_path=db_path,
        market_db_path=market_db_path,
        enrich_live_context=True,
    )

    assert detail["match_context"]["source"]["label"] == "多源融合"
    assert detail["match_context"]["venue"]["text"] == "纳萨夫体育场 · 卡尔希"
    assert detail["match_context"]["weather"]["text"] == "晴"
    attempts = detail["match_context"]["source_attempts"]
    leisu_attempt = next(item for item in attempts if item["provider"] == "leisu")
    assert leisu_attempt["status"] == "matched"
    assert leisu_attempt["match_id"] == "4528570"
    assert leisu_attempt["field_statuses"]["venue"] == "available"
    assert leisu_attempt["field_statuses"]["weather"] == "available"


def test_dashboard_match_detail_marks_blocked_leisu_context_access(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-leisu-context-blocked",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "league": "乌兹杯",
                "home_team": "纳萨夫",
                "away_team": "古佐尔警察",
                "match_id": "54435613",
                "kickoff_utc_plus_8": "2026-05-26T03:51:00+08:00",
                "market": "asian_handicap",
                "selection": "纳萨夫 -1.5",
                "selection_key": "home_cover",
                "line": -1.5,
                "decimal_odds": 1.90,
                "model_probability": 0.52,
                "calibrated_probability": 0.52,
                "market_probability": 0.50,
                "edge": 0.02,
                "expected_multiplier": 0.988,
                "recommendation": "no_value",
                "stake_level": "none",
                "raw": {
                    "context_source_name": "dongqiudi",
                    "context_match_id": "54435613",
                    "match_context": {
                        "match_id": "54435613",
                        "source_name": "dongqiudi",
                        "lineup": {
                            "base": {
                                "field": "暂无信息",
                                "weather": "暂无信息",
                                "referee": "暂无信息",
                            },
                            "lineup_status": {"lineup_basis": "unavailable"},
                            "lineup_analysis": {"available": False, "warnings": ["lineup_unavailable"]},
                        },
                    },
                },
            }
        ],
        db_path=db_path,
    )
    record = learning_store.list_recommendation_records(db_path=db_path, limit=1)[0]
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:4528570",
                event_id="4528570",
                league="乌兹杯",
                home_team="纳萨夫",
                away_team="古佐尔警察",
                kickoff_utc="",
                bookmaker="公司A",
                market_type="asian_handicap",
                selection="纳萨夫 -1.5",
                decimal_odds=1.90,
                line=-1.5,
                source_time_utc="2026-05-25T19:50:00+00:00",
                fetched_at_utc="2026-05-25T19:55:00+00:00",
                raw={"match_resolution_reason": "direct_snapshot_match"},
            )
        ],
        db_path=market_db_path,
    )

    async def fake_leisu_match_context(match_id):
        assert match_id == "4528570"
        return sources_module.normalize_leisu_match_context(
            match_id,
            lineup_source={
                "access": {
                    "blocked": True,
                    "requires_cookie_or_proxy": True,
                    "reason": "403 forbidden",
                }
            },
            detail_source={
                "access": {
                    "blocked": True,
                    "requires_cookie_or_proxy": True,
                    "reason": "403 forbidden",
                }
            },
        )

    monkeypatch.setenv("FOOTBALL_DATA_LEISU_CONTEXT_ENABLED", "true")
    monkeypatch.setattr(sources_module, "leisu_match_context", fake_leisu_match_context)

    detail = sources_module.dashboard_match_detail(
        f"recommendation:{record['id']}",
        db_path=db_path,
        market_db_path=market_db_path,
        enrich_live_context=True,
    )

    leisu_attempt = next(item for item in detail["match_context"]["source_attempts"] if item["provider"] == "leisu")
    assert leisu_attempt["status"] == "access_blocked"
    assert leisu_attempt["field_statuses"] == {
        "venue": "access_blocked",
        "weather": "access_blocked",
        "referee": "access_blocked",
        "lineup": "access_blocked",
    }
    assert "访问受限" in leisu_attempt["detail"]
    assert "Cookie 或代理" in leisu_attempt["detail"]


def test_dashboard_match_detail_uses_persisted_multi_source_context_attempts(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-multi-source-context",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "league": "乌兹杯",
                "home_team": "纳萨夫",
                "away_team": "古佐尔警察",
                "match_id": "54435613",
                "kickoff_utc_plus_8": "2026-05-26T03:51:00+08:00",
                "market": "asian_handicap",
                "selection": "纳萨夫 -1.5",
                "selection_key": "home_cover",
                "line": -1.5,
                "decimal_odds": 1.90,
                "model_probability": 0.52,
                "calibrated_probability": 0.52,
                "market_probability": 0.50,
                "edge": 0.02,
                "expected_multiplier": 0.988,
                "recommendation": "no_value",
                "stake_level": "none",
                "raw": {
                    "match_context": {
                        "source_name": "multi_source",
                        "provider": "multi_source",
                        "source_ids": {"dongqiudi": "54435613", "leisu": "4528570"},
                        "venue": {"name": "纳萨夫体育场", "city": "卡尔希"},
                        "weather": "晴",
                        "referee": "暂无信息",
                        "lineup": {
                            "base": {
                                "field": "纳萨夫体育场",
                                "weather": "晴",
                                "referee": "暂无信息",
                            },
                            "lineup_status": {"lineup_basis": "unavailable"},
                            "lineup_analysis": {"available": False, "warnings": ["lineup_unavailable"]},
                        },
                        "available_blocks": ["venue", "weather"],
                        "source_attempts": [
                            {
                                "provider": "dongqiudi",
                                "label": "懂球帝",
                                "status": "matched",
                                "match_id": "54435613",
                                "field_statuses": {
                                    "venue": "source_empty",
                                    "weather": "source_empty",
                                    "referee": "source_empty",
                                    "lineup": "source_empty",
                                },
                            },
                            {
                                "provider": "leisu",
                                "label": "雷速体育",
                                "status": "matched",
                                "match_id": "4528570",
                                "field_statuses": {
                                    "venue": "available",
                                    "weather": "available",
                                    "referee": "source_empty",
                                    "lineup": "source_empty",
                                },
                            },
                        ],
                    },
                },
            }
        ],
        db_path=db_path,
    )
    record = learning_store.list_recommendation_records(db_path=db_path, limit=1)[0]
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:4528570",
                event_id="4528570",
                league="乌兹杯",
                home_team="纳萨夫",
                away_team="古佐尔警察",
                kickoff_utc="",
                bookmaker="雷速",
                market_type="asian_handicap",
                selection="纳萨夫 -1.5",
                decimal_odds=1.90,
                line=-1.5,
                source_time_utc="2026-05-25T19:50:00+00:00",
                fetched_at_utc="2026-05-25T19:55:00+00:00",
                raw={},
            )
        ],
        db_path=market_db_path,
    )

    detail = sources_module.dashboard_match_detail(
        f"recommendation:{record['id']}",
        db_path=db_path,
        market_db_path=market_db_path,
    )

    assert detail["match_context"]["source"]["label"] == "多源融合"
    assert detail["match_context"]["venue"]["text"] == "纳萨夫体育场 · 卡尔希"
    assert detail["match_context"]["weather"]["text"] == "晴"
    attempts = detail["match_context"]["source_attempts"]
    assert [attempt["provider"] for attempt in attempts] == ["dongqiudi", "leisu"]
    assert attempts[1]["field_statuses"]["venue"] == "available"
    assert "odds_matched_context_not_collected" not in {attempt["status"] for attempt in attempts}


def test_dashboard_match_detail_marks_empty_collected_context_as_source_empty(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-dongqiudi-empty-context",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "league": "资料联赛",
                "home_team": "空字段主队",
                "away_team": "空字段客队",
                "match_id": "543211",
                "kickoff_utc_plus_8": "2026-05-25T22:45:00+08:00",
                "market": "asian_handicap",
                "selection": "空字段主队 -0.25",
                "selection_key": "home_cover",
                "line": -0.25,
                "decimal_odds": 1.92,
                "model_probability": 0.52,
                "calibrated_probability": 0.52,
                "market_probability": 0.50,
                "edge": 0.02,
                "expected_multiplier": 0.9984,
                "recommendation": "condition_observe",
                "stake_level": "none",
                "raw": {
                    "match_context": {
                        "match_id": "543211",
                        "lineup": {
                            "available": True,
                            "base": {
                                "field": "",
                                "weather": "",
                                "referee": None,
                            },
                            "lineup_status": {"lineup_basis": "unavailable"},
                            "lineup_analysis": {"available": False, "warnings": ["lineup_unavailable"]},
                        },
                    },
                },
            }
        ],
        db_path=db_path,
    )
    record = learning_store.list_recommendation_records(db_path=db_path, limit=1)[0]

    detail = sources_module.dashboard_match_detail(f"recommendation:{record['id']}", db_path=db_path)

    assert detail["match_context"]["source"]["label"] == "懂球帝"
    assert detail["match_context"]["venue"]["status"] == "source_empty"
    assert detail["match_context"]["weather"]["status"] == "source_empty"
    assert detail["match_context"]["referee"]["status"] == "source_empty"


def test_dashboard_snapshot_exposes_match_context_coverage(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-context-coverage",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "ctx-rich",
                "league": "资料联赛",
                "home_team": "情报主队",
                "away_team": "情报客队",
                "kickoff_utc_plus_8": "2026-05-25T22:45:00+08:00",
                "market": "asian_handicap",
                "selection": "情报主队 -0.25",
                "selection_key": "home_cover",
                "line": -0.25,
                "decimal_odds": 1.92,
                "model_probability": 0.52,
                "calibrated_probability": 0.52,
                "market_probability": 0.50,
                "edge": 0.02,
                "expected_multiplier": 0.9984,
                "recommendation": "condition_observe",
                "stake_level": "none",
                "raw": {
                    "match_context": {
                        "source_name": "dongqiudi",
                        "match_id": "ctx-rich",
                        "lineup": {
                            "base": {
                                "field": "资料体育场",
                                "weather": "晴",
                                "referee": "资料裁判",
                            },
                            "lineup_status": {"lineup_basis": "official_lineups"},
                            "lineup_analysis": {"available": True, "warnings": []},
                            "official_lineups": {
                                "home": {"lineups": [{"name": "主队前锋"}]},
                                "away": {"lineups": [{"name": "客队门将"}]},
                            },
                        },
                    },
                },
            },
            {
                "run_id": "cycle-context-coverage",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "ctx-empty",
                "league": "资料联赛",
                "home_team": "源站空主队",
                "away_team": "源站空客队",
                "kickoff_utc_plus_8": "2026-05-25T23:45:00+08:00",
                "market": "asian_handicap",
                "selection": "源站空主队 +0.25",
                "selection_key": "home_cover",
                "line": 0.25,
                "decimal_odds": 1.86,
                "model_probability": 0.51,
                "calibrated_probability": 0.51,
                "market_probability": 0.50,
                "edge": 0.01,
                "expected_multiplier": 0.9486,
                "recommendation": "no_value",
                "stake_level": "none",
                "raw": {
                    "context_source_name": "dongqiudi",
                    "context_match_id": "ctx-empty",
                    "match_context": {
                        "match_id": "ctx-empty",
                        "lineup": {
                            "base": {
                                "field": "暂无信息",
                                "weather": "暂无信息",
                                "referee": "暂无信息",
                            },
                            "lineup_status": {"lineup_basis": "unavailable"},
                            "lineup_analysis": {"available": False, "warnings": ["lineup_unavailable"]},
                        },
                    },
                },
            },
            {
                "run_id": "cycle-context-coverage",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "ctx-missing",
                "league": "资料联赛",
                "home_team": "本地缺主队",
                "away_team": "本地缺客队",
                "kickoff_utc_plus_8": "2026-05-26T00:45:00+08:00",
                "market": "asian_handicap",
                "selection": "本地缺主队 +0.25",
                "selection_key": "home_cover",
                "line": 0.25,
                "decimal_odds": 1.86,
                "model_probability": 0.51,
                "calibrated_probability": 0.51,
                "market_probability": 0.50,
                "edge": 0.01,
                "expected_multiplier": 0.9486,
                "recommendation": "no_value",
                "stake_level": "none",
                "raw": {"kind": "learning_observation"},
            },
        ],
        db_path=db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=50)
    coverage = snapshot["context_coverage"]

    assert coverage["total_count"] == 3
    assert coverage["source_counts"][0]["label"] == "懂球帝"
    assert coverage["source_counts"][0]["count"] == 2
    assert coverage["source_counts"][1]["label"] == "暂未采集"
    assert coverage["source_counts"][1]["count"] == 1
    field_counts = {item["key"]: item for item in coverage["fields"]}
    assert field_counts["venue"]["available_count"] == 1
    assert field_counts["venue"]["source_empty_count"] == 1
    assert field_counts["venue"]["not_collected_count"] == 1
    assert field_counts["lineup"]["available_count"] == 1
    assert field_counts["lineup"]["source_empty_count"] == 1
    assert field_counts["lineup"]["not_collected_count"] == 1
    assert "懂球帝已匹配 2/3 场" in coverage["summary"]
    assert "天气 1/3 场有值" in coverage["summary"]


def test_dashboard_context_coverage_matches_full_prediction_ledger_scope(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-contract-scope",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "contract-rec",
                "league": "契约联赛",
                "home_team": "推荐主队",
                "away_team": "推荐客队",
                "kickoff_utc_plus_8": "2026-05-25T22:45:00+08:00",
                "market": "asian_handicap",
                "selection": "推荐主队 -0.25",
                "selection_key": "home_cover",
                "line": -0.25,
                "decimal_odds": 1.92,
                "model_probability": 0.52,
                "calibrated_probability": 0.52,
                "market_probability": 0.50,
                "edge": 0.02,
                "recommendation": "no_value",
                "raw": {
                    "match_context": {
                        "source_name": "dongqiudi",
                        "match_id": "contract-rec",
                        "lineup": {"base": {"weather": "晴"}},
                    },
                },
            }
        ],
        db_path=db_path,
    )
    learning_store.save_shadow_prediction_records(
        [
            {
                "run_id": "cycle-contract-scope",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "decision": "rejected",
                "rejection_reason": "edge_below_threshold",
                "match": {
                    "match_id": "contract-shadow",
                    "league": "契约联赛",
                    "home_team": "影子主队",
                    "away_team": "影子客队",
                    "kickoff_utc_plus_8": "2026-05-25T23:45:00+08:00",
                },
                "best_candidate": {
                    "market": "asian_handicap",
                    "selection": "影子客队 +0.25",
                    "selection_key": "away_cover",
                    "line": 0.25,
                    "decimal_odds": 1.86,
                    "model_probability": 0.51,
                    "calibrated_probability": 0.51,
                    "market_probability": 0.50,
                    "edge": 0.01,
                    "recommendation": "no_value",
                },
                "raw": {
                    "kind": "shadow_prediction",
                    "match_context": {
                        "source_name": "dongqiudi",
                        "match_id": "contract-shadow",
                        "lineup": {"base": {"weather": "阴"}},
                    },
                },
            }
        ],
        db_path=db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=50)

    assert snapshot["prediction_kpis"]["total_count"] == 2
    assert snapshot["context_coverage"]["total_count"] == 2
    assert snapshot["dashboard_contract"]["sections"][-1]["current"] == 2


def test_dashboard_context_coverage_counts_leisu_odds_snapshot_attempts(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-context-leisu-coverage",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "54435613",
                "league": "乌兹杯",
                "home_team": "纳萨夫",
                "away_team": "古佐尔警察",
                "kickoff_utc_plus_8": "2026-05-25T22:45:00+08:00",
                "market": "asian_handicap",
                "selection": "纳萨夫 -1.5",
                "selection_key": "home_cover",
                "line": -1.5,
                "decimal_odds": 1.9,
                "model_probability": 0.52,
                "calibrated_probability": 0.52,
                "market_probability": 0.50,
                "edge": 0.02,
                "recommendation": "no_value",
                "raw": {
                    "context_source_name": "dongqiudi",
                    "context_match_id": "54435613",
                    "match_context": {
                        "source_name": "dongqiudi",
                        "match_id": "54435613",
                        "lineup": {
                            "base": {
                                "field": "暂无信息",
                                "weather": "晴",
                                "referee": "暂无信息",
                            },
                            "lineup_status": {"lineup_basis": "unavailable"},
                            "lineup_analysis": {"available": False, "warnings": ["lineup_unavailable"]},
                        },
                    },
                },
            }
        ],
        db_path=db_path,
    )
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:4528570",
                event_id="4528570",
                league="乌兹杯",
                home_team="纳萨夫",
                away_team="古佐尔警察",
                kickoff_utc="",
                bookmaker="公司A",
                market_type="asian_handicap",
                selection="纳萨夫 -1.5",
                decimal_odds=1.90,
                line=-1.5,
                source_time_utc="2026-05-25T19:50:00+00:00",
                fetched_at_utc="2026-05-25T19:55:00+00:00",
                raw={"match_resolution_reason": "direct_snapshot_match"},
            )
        ],
        db_path=market_db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, market_db_path=market_db_path, limit=50)
    source_counts = {
        (item["provider"], item["status"]): item["count"]
        for item in snapshot["context_coverage"]["source_counts"]
    }

    assert source_counts[("dongqiudi", "matched")] == 1
    assert source_counts[("leisu", "odds_matched_context_not_collected")] == 1
    assert "雷速体育赔率已匹配 1/1 场" in snapshot["context_coverage"]["summary"]


def test_dashboard_context_coverage_counts_leisu_snapshot_attempts_for_shadow_predictions(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_shadow_prediction_records(
        [
            {
                "run_id": "cycle-shadow-context-leisu-coverage",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "decision": "rejected",
                "rejection_reason": "edge_below_threshold",
                "match": {
                    "match_id": "shadow-4528570",
                    "league": "乌兹杯",
                    "home_team": "纳萨夫",
                    "away_team": "古佐尔警察",
                    "kickoff_utc_plus_8": "2026-05-25T22:45:00+08:00",
                },
                "best_candidate": {
                    "market": "asian_handicap",
                    "selection": "纳萨夫 -1.5",
                    "selection_key": "home_cover",
                    "line": -1.5,
                    "decimal_odds": 1.9,
                    "model_probability": 0.52,
                    "calibrated_probability": 0.52,
                    "market_probability": 0.50,
                    "edge": 0.02,
                    "recommendation": "no_value",
                },
                "raw": {
                    "kind": "shadow_prediction",
                    "match_context": {
                        "source_name": "dongqiudi",
                        "match_id": "shadow-ctx",
                        "lineup": {"base": {"weather": "晴"}},
                    },
                },
            }
        ],
        db_path=db_path,
    )
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:4528570",
                event_id="4528570",
                league="乌兹杯",
                home_team="纳萨夫",
                away_team="古佐尔警察",
                kickoff_utc="",
                bookmaker="公司A",
                market_type="asian_handicap",
                selection="纳萨夫 -1.5",
                decimal_odds=1.90,
                line=-1.5,
                source_time_utc="2026-05-25T19:50:00+00:00",
                fetched_at_utc="2026-05-25T19:55:00+00:00",
                raw={"match_resolution_reason": "direct_snapshot_match"},
            )
        ],
        db_path=market_db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, market_db_path=market_db_path, limit=50)
    source_counts = {
        (item["provider"], item["status"]): item["count"]
        for item in snapshot["context_coverage"]["source_counts"]
    }

    assert snapshot["prediction_kpis"]["total_count"] == 1
    assert source_counts[("leisu", "odds_matched_context_not_collected")] == 1


def test_dashboard_snapshot_exposes_production_readiness_verdict(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": f"cycle-readiness-{index}",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": f"readiness-{index}",
                "league": "生产审计联赛",
                "home_team": f"审计主队{index}",
                "away_team": f"审计客队{index}",
                "market": "asian_handicap",
                "selection": f"审计主队{index} -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.9,
                "model_probability": 0.62,
                "calibrated_probability": 0.62,
                "market_probability": 0.52,
                "recommendation": "no_value",
            }
            for index in range(24)
        ],
        db_path=db_path,
    )
    learning_store.settle_recommendations(
        [
            {
                "match_id": f"readiness-{index}",
                "home_team": f"审计主队{index}",
                "away_team": f"审计客队{index}",
                "home_score": 0,
                "away_score": 1,
            }
            for index in range(24)
        ],
        db_path=db_path,
    )
    learning_store.recompute_calibration(db_path=db_path)
    learning_store.update_strategy_state(db_path=db_path, market="asian_handicap", mode="balanced")

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, limit=50)
    readiness = snapshot["production_readiness"]

    assert readiness["is_toy"] is False
    assert readiness["production_ready"] is False
    assert readiness["status"] == "paper_validation"
    assert readiness["summary"]["prediction_total"] == 24
    assert readiness["summary"]["settled_count"] == 24
    assert readiness["summary"]["roi"] < 0
    assert {gate["key"]: gate["status"] for gate in readiness["gates"]}["learning_effectiveness"] == "blocked"
    assert "已有 24 条预测和 24 条回测" in readiness["detail"]


def test_dashboard_snapshot_does_not_fuzzy_scan_snapshots_for_each_ledger_row(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-dashboard-fast",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "league": "快速联赛",
                "home_team": "快速主队",
                "away_team": "快速客队",
                "kickoff_utc_plus_8": "2026-05-25T22:45:00+08:00",
                "market": "asian_handicap",
                "selection": "快速主队 -0.25",
                "selection_key": "home_cover",
                "line": -0.25,
                "decimal_odds": 1.92,
                "model_probability": 0.52,
                "calibrated_probability": 0.52,
                "market_probability": 0.50,
                "edge": 0.02,
                "expected_multiplier": 0.9984,
                "recommendation": "condition_observe",
                "stake_level": "none",
                "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
            }
        ],
        db_path=db_path,
    )

    def unexpected_fuzzy_lookup(*args, **kwargs):
        raise AssertionError("dashboard list should not run per-row fuzzy snapshot scans")

    monkeypatch.setattr(sources_module.snapshot_store, "market_snapshot_coverage_for_match", unexpected_fuzzy_lookup)

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, market_db_path=market_db_path)

    assert snapshot["prediction_ledger"][0]["odds_snapshot_count"] == 0


def test_dashboard_match_detail_exposes_context_and_odds_snapshots(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-match-detail",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "match_id": "rich-detail",
                "league": "资料联赛",
                "home_team": "资料主队",
                "away_team": "资料客队",
                "kickoff_utc_plus_8": "2026-05-25T19:00:00+08:00",
                "market": "asian_handicap",
                "selection": "资料主队 -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.88,
                "model_probability": 0.62,
                "calibrated_probability": 0.61,
                "market_probability": 0.532,
                "edge": 0.078,
                "expected_multiplier": 1.1468,
                "recommendation": "immediate_bet",
                "stake_level": "small",
                "raw": {
                    "model_engine": {
                        "available": True,
                        "version": "scoreline-model-v1",
                        "method": "dixon_coles_market_anchored_grid",
                        "dixon_coles": {
                            "rho": -0.08,
                            "rho_source": "historical_league_mle",
                            "historical_rho": {
                                "rho": -0.08,
                                "sample_count": 120,
                            },
                        },
                        "fitted_market_targets": {
                            "moneyline_1x2": True,
                            "asian_handicap": True,
                            "over_under": False,
                        },
                        "model_quality": {"fallback_used": False},
                    },
                    "match_context": {
                        "venue": {"name": "资料体育场", "city": "上海"},
                        "lineup": {
                            "base": {
                                "weather": "多云 18C",
                                "referee": "王裁判",
                            },
                            "lineup_status": {"lineup_basis": "official_lineups"},
                            "lineup_analysis": {
                                "available": True,
                                "can_use_for_analysis": True,
                                "home": {"formation": "4-3-3", "starter_count": 11},
                                "away": {"formation": "4-2-3-1", "starter_count": 11},
                                "warnings": [],
                            },
                            "official_lineups": {
                                "home": {
                                    "lineups": [
                                        {"name": "资料前锋", "position": "F", "shirt_number": "9"},
                                    ]
                                },
                                "away": {
                                    "lineups": [
                                        {"name": "客队门将", "position": "G", "shirt_number": "1"},
                                    ]
                                },
                            },
                        },
                    },
                    "market_candidates": [
                        {
                            "selection": "资料主队 -0.5",
                            "decimal_odds": 1.88,
                            "calibrated_probability": 0.61,
                            "edge": 0.078,
                        }
                    ],
                },
            }
        ],
        db_path=db_path,
    )
    record = learning_store.list_recommendation_records(db_path=db_path, limit=1)[0]
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:rich-detail",
                event_id="rich-detail",
                league="资料联赛",
                home_team="资料主队",
                away_team="资料客队",
                kickoff_utc="2026-05-25T11:00:00+00:00",
                bookmaker="公司A",
                market_type="asian_handicap",
                selection="资料主队 -0.5",
                decimal_odds=1.88,
                line=-0.5,
                source_time_utc="2026-05-25T08:00:00+00:00",
                fetched_at_utc="2026-05-25T08:05:00+00:00",
                raw={"company_id": 1},
            ),
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:rich-detail",
                event_id="rich-detail",
                league="资料联赛",
                home_team="资料主队",
                away_team="资料客队",
                kickoff_utc="2026-05-25T11:00:00+00:00",
                bookmaker="公司B",
                market_type="asian_handicap",
                selection="资料客队 +0.5",
                decimal_odds=1.96,
                line=0.5,
                source_time_utc="2026-05-25T08:10:00+00:00",
                fetched_at_utc="2026-05-25T08:15:00+00:00",
                raw={"company_id": 2},
            ),
            *[
                snapshot_store.MarketSnapshot(
                    provider="leisu",
                    source_key=f"leisu:noise-{index}",
                    event_id=f"noise-{index}",
                    league="噪声联赛",
                    home_team=f"噪声主队{index}",
                    away_team=f"噪声客队{index}",
                    kickoff_utc="2026-05-25T12:00:00+00:00",
                    bookmaker="噪声公司",
                    market_type="asian_handicap",
                    selection=f"噪声主队{index} +0",
                    decimal_odds=1.9,
                    line=0,
                    source_time_utc=f"2026-05-25T09:{index % 60:02d}:00+00:00",
                    fetched_at_utc=f"2026-05-25T09:{index % 60:02d}:30+00:00",
                    raw={"noise": index},
                )
                for index in range(1005)
            ],
        ],
        db_path=market_db_path,
    )

    detail = sources_module.dashboard_match_detail(
        f"recommendation:{record['id']}",
        db_path=db_path,
        market_db_path=market_db_path,
    )
    snapshot = sources_module.dashboard_snapshot(db_path=db_path, market_db_path=market_db_path)
    ledger_row = next(row for row in snapshot["prediction_ledger"] if row["ledger_id"] == f"recommendation:{record['id']}")

    assert detail["status"] == "ok"
    assert detail["record"]["ledger_id"] == f"recommendation:{record['id']}"
    assert detail["match_context"]["venue"]["text"] == "资料体育场 · 上海"
    assert detail["match_context"]["weather"]["text"] == "多云 18C"
    assert detail["match_context"]["referee"]["text"] == "王裁判"
    assert detail["match_context"]["lineup"]["available"] is True
    assert detail["match_context"]["lineup"]["home"]["starters"][0]["name"] == "资料前锋"
    assert detail["odds_snapshot"]["snapshot_count"] == 2
    assert detail["odds_snapshot"]["bookmaker_count"] == 2
    assert detail["odds_snapshot"]["latest_rows"][0]["bookmaker"] == "公司B"
    assert detail["clv_tracking"]["available_count"] == 1
    assert detail["clv_tracking"]["records"][0]["clv"]["closing_decimal_odds"] == 1.88
    assert detail["evidence"]["market_candidates"][0]["selection"] == "资料主队 -0.5"
    assert ledger_row["odds_snapshot_count"] == 2
    assert ledger_row["odds_bookmaker_count"] == 2
    assert ledger_row["has_odds_snapshot"] is True
    assert snapshot["clv_tracking"]["available_count"] == 1
    assert snapshot["model_governance"]["summary"]["model_engine_count"] == 1
    assert snapshot["model_governance"]["summary"]["historical_rho_count"] == 1
    assert snapshot["model_governance"]["rho"]["source_counts"]["historical_league_mle"] == 1


def test_dashboard_match_detail_matches_leisu_alias_snapshot_names(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-alias-detail",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "match_id": "alias-detail",
                "league": "丹甲",
                "home_team": "赫维多夫",
                "away_team": "埃斯比约",
                "kickoff_utc_plus_8": "2026-05-25T21:00:00+08:00",
                "market": "asian_handicap",
                "selection": "赫维多夫 -0.25",
                "selection_key": "home_cover",
                "line": -0.25,
                "decimal_odds": 1.99,
                "model_probability": 0.5,
                "calibrated_probability": 0.5,
                "market_probability": 0.5,
                "edge": 0,
                "expected_multiplier": 0.995,
                "recommendation": "no_value",
                "stake_level": "none",
                "raw": {},
            }
        ],
        db_path=db_path,
    )
    record = learning_store.list_recommendation_records(db_path=db_path, limit=1)[0]
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:4523318",
                event_id="4523318",
                league="丹麦甲",
                home_team="哈维德夫",
                away_team="埃斯比约",
                kickoff_utc="",
                bookmaker="韦*",
                market_type="asian_handicap",
                selection="哈维德夫 -0.25",
                decimal_odds=1.99,
                line=-0.25,
                source_time_utc="2026-05-25T12:59:00+00:00",
                fetched_at_utc="2026-05-25T12:59:30+00:00",
                raw={},
            )
        ],
        db_path=market_db_path,
    )

    detail = sources_module.dashboard_match_detail(
        f"recommendation:{record['id']}",
        db_path=db_path,
        market_db_path=market_db_path,
    )
    snapshot = sources_module.dashboard_snapshot(db_path=db_path, market_db_path=market_db_path)
    ledger_row = next(row for row in snapshot["prediction_ledger"] if row["ledger_id"] == f"recommendation:{record['id']}")

    assert detail["odds_snapshot"]["snapshot_count"] == 1
    assert detail["odds_snapshot"]["resolution"]["status"] == "matched"
    assert detail["odds_snapshot"]["resolution"]["source_home_team"] == "哈维德夫"
    assert ledger_row["odds_snapshot_count"] == 1
    assert ledger_row["has_odds_snapshot"] is True


def test_dashboard_match_detail_reconciles_stale_advice_after_snapshot_arrives(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-stale-advice",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": "stale-advice",
                "league": "复核联赛",
                "home_team": "补快照主队",
                "away_team": "补快照客队",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "补快照主队 +0.5",
                "selection_key": "home_cover",
                "line": 0.5,
                "decimal_odds": 1.85,
                "model_probability": 0.61,
                "calibrated_probability": 0.61,
                "market_probability": 0.54,
                "edge": 0.07,
                "expected_multiplier": 1.1285,
                "recommendation": "immediate_bet",
                "stake_level": "small",
                "raw": {
                    "kind": "learning_observation",
                    "reason": "multi_bookmaker_snapshot_missing",
                    "final_execution_advice": {
                        "source": "mcp",
                        "action": "paper_track",
                        "headline": "纸面预测：补快照主队 +0.5，缺少多公司赔率快照，继续进入回测但不升级为正式推荐。",
                        "reason": "multi_bookmaker_snapshot_missing",
                    },
                    "data_completeness": {
                        "available_blocks": ["lineup"],
                        "missing_blocks": ["multi_bookmaker_snapshot"],
                    },
                },
            }
        ],
        db_path=db_path,
    )
    record = learning_store.list_recommendation_records(db_path=db_path, limit=1)[0]
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:stale-advice",
                event_id="stale-advice",
                league="复核联赛",
                home_team="补快照主队",
                away_team="补快照客队",
                kickoff_utc="2026-05-25T12:00:00+00:00",
                bookmaker="公司A",
                market_type="asian_handicap",
                selection="补快照主队 +0.5",
                decimal_odds=1.85,
                line=0.5,
                source_time_utc="2026-05-25T11:50:00+00:00",
                fetched_at_utc="2026-05-25T11:55:00+00:00",
                raw={},
            )
        ],
        db_path=market_db_path,
    )

    detail = sources_module.dashboard_match_detail(
        f"recommendation:{record['id']}",
        db_path=db_path,
        market_db_path=market_db_path,
    )
    advice = detail["evidence"]["final_execution_advice"]

    assert detail["record"]["rejection_reason"] == "awaiting_reanalysis_after_snapshot"
    assert detail["evidence"]["prediction_diagnostic"]["primary_reason"] == "awaiting_reanalysis_after_snapshot"
    assert advice["source"] == "dashboard_synthesized_advice"
    assert advice["reason"] == "awaiting_reanalysis_after_snapshot"
    assert "赔率快照已补齐" in advice["headline"]
    assert "缺少多公司赔率" not in advice["headline"]


def test_dashboard_match_detail_uses_best_candidate_as_candidate_odds_when_snapshot_missing(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-candidate-odds",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "match_id": "caps-platinum",
                "league": "津巴超",
                "home_team": "CAPS联队",
                "away_team": "铂金",
                "kickoff_utc_plus_8": "2026-05-25T21:00:00+08:00",
                "market": "asian_handicap",
                "selection": "铂金 +0.25",
                "selection_key": "away_cover",
                "line": 0.25,
                "decimal_odds": 1.86,
                "model_probability": 0.498419,
                "calibrated_probability": 0.498419,
                "market_probability": 0.494565,
                "edge": -0.0729,
                "expected_multiplier": 0.927059,
                "recommendation": "no_value",
                "stake_level": "none",
                "raw": {
                    "best_candidate": {
                        "provider": "乐天*",
                        "market": "asian_handicap",
                        "selection": "铂金 +0.25",
                        "line": 0.25,
                        "decimal_odds": 1.86,
                        "model_probability": 0.498419,
                        "edge": -0.0729,
                    },
                    "data_completeness": {
                        "missing_blocks": ["multi_bookmaker_snapshot"],
                    },
                },
            }
        ],
        db_path=db_path,
    )
    record = learning_store.list_recommendation_records(db_path=db_path, limit=1)[0]

    detail = sources_module.dashboard_match_detail(f"recommendation:{record['id']}", db_path=db_path)

    assert detail["odds_snapshot"]["snapshot_count"] == 0
    assert detail["evidence"]["market_candidates"][0]["provider"] == "乐天*"
    assert detail["evidence"]["market_candidates"][0]["selection"] == "铂金 +0.25"
    assert detail["evidence"]["market_candidates"][0]["decimal_odds"] == 1.86


def test_learning_result_from_dongqiudi_row_reads_nested_full_time_score():
    result = sources_module._learning_result_from_dongqiudi_row(
        {
            "match_id": "54408599",
            "status": "Played",
            "start_play": "2026-05-24 09:00:00",
            "competition": {"name": "越南甲"},
            "team_A": {"name": "北宁交通", "fs": "8"},
            "team_B": {"name": "胡志明市二队", "fs": "0"},
        },
        {"source": "dongqiudi.com"},
    )

    assert result is not None
    assert result["home_score"] == 8
    assert result["away_score"] == 0


def test_dongqiudi_match_state_reads_top_level_live_score():
    state = sources_module._dongqiudi_match_state_from_sample(
        {
            "match_id": "live-score-1",
            "status": "Playing",
            "minute": "42",
            "minute_period": "1H",
            "fs_A": "1",
            "fs_B": "0",
        },
        {"source": "dongqiudi.com"},
    )

    assert state["phase"] == "live"
    assert state["score"] == "1-0"
    assert state["home_score"] == 1
    assert state["away_score"] == 0


def test_fetch_learning_results_uses_dongqiudi_result_tab(monkeypatch):
    calls = []

    async def fake_load_dongqiudi_matches_for_date(local_date, *, tab_type="fixture"):
        calls.append(tab_type)
        return (
            [
                {
                    "match_id": "54408599",
                    "status": "Played",
                    "start_play": "2026-05-24 09:00:00",
                    "competition": {"name": "越南甲"},
                    "team_A": {"name": "北宁交通", "fs": "8"},
                    "team_B": {"name": "胡志明市二队", "fs": "0"},
                }
            ],
            {"source": "dongqiudi.com"},
        )

    monkeypatch.setattr(sources_module, "load_dongqiudi_matches_for_date", fake_load_dongqiudi_matches_for_date)

    fetched = asyncio.run(
        sources_module._fetch_learning_results_from_public_sources(
            as_of="2026-05-25T10:00:00+08:00",
            timezone_name="Asia/Shanghai",
            days_back=1,
            days_forward=0,
        )
    )

    assert set(calls) == {"result"}
    assert fetched["fetched_count"] == 2
    assert fetched["results"][0]["home_score"] == 8


def test_settle_learning_recommendations_exposes_live_match_state_from_detail(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "live-state-cycle",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "match_id": "live-dqd-1",
                "league": "测试联赛",
                "home_team": "实时主队",
                "away_team": "实时客队",
                "kickoff_utc_plus_8": "2026-05-25T23:00:00+08:00",
                "market": "asian_handicap",
                "selection": "实时客队 +0.5",
                "selection_key": "away_cover",
                "line": 0.5,
                "decimal_odds": 1.9,
                "model_probability": 0.58,
                "calibrated_probability": 0.58,
                "market_probability": 0.52,
                "edge": 0.06,
                "recommendation": "condition_observe",
                "raw": {"best_candidate": {"market": "asian_handicap"}},
            }
        ],
        db_path=db_path,
    )

    async def fake_fetch_results(**kwargs):
        return {"source": "test", "fetched_count": 0, "results": [], "errors": []}

    async def fake_load_dongqiudi_detail(match_id):
        assert match_id == "live-dqd-1"
        return (
            {
                "matchSample": {
                    "match_id": "live-dqd-1",
                    "status": "Playing",
                    "minute": "42",
                    "minute_period": "1H",
                    "start_play": "2026-05-25 15:00:00",
                    "team_A": {"name": "实时主队", "fs": "1"},
                    "team_B": {"name": "实时客队", "fs": "0"},
                }
            },
            {"source": "dongqiudi.com"},
        )

    monkeypatch.setattr(sources_module, "_fetch_learning_results_from_public_sources", fake_fetch_results)
    monkeypatch.setattr(sources_module, "load_dongqiudi_detail", fake_load_dongqiudi_detail)

    result = asyncio.run(
        sources_module.settle_learning_recommendations(
            auto_fetch=True,
            as_of="2026-05-25T23:42:00+08:00",
            timezone_name="Asia/Shanghai",
            db_path=db_path,
        )
    )

    assert result["settlement"]["settled_count"] == 0
    assert result["match_state_refresh"]["updated_count"] == 1

    record = learning_store.list_recommendation_records(db_path=db_path, limit=1)[0]
    detail = sources_module.dashboard_match_detail(f"recommendation:{record['id']}", db_path=db_path)

    assert detail["record"]["settlement_status"] == "open"
    assert detail["record"]["status_label"] == "比赛进行中"
    assert detail["record"]["score"] == "1-0"
    assert detail["record"]["score_type"] == "live"
    assert detail["record"]["true_result"]["score"] == ""
    assert detail["record"]["match_state"]["phase"] == "live"
    assert detail["record"]["match_state"]["minute"] == "42"
    assert detail["record"]["match_state"]["label"] == "比赛进行中"


def test_settle_learning_recommendations_uses_finished_detail_when_result_tab_lags(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "final-detail-cycle",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "match_id": "final-dqd-1",
                "league": "测试联赛",
                "home_team": "完场主队",
                "away_team": "完场客队",
                "kickoff_utc_plus_8": "2026-05-25T21:00:00+08:00",
                "market": "asian_handicap",
                "selection": "完场主队 -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.86,
                "model_probability": 0.61,
                "calibrated_probability": 0.61,
                "market_probability": 0.54,
                "edge": 0.07,
                "recommendation": "immediate_bet",
                "raw": {"best_candidate": {"market": "asian_handicap"}},
            }
        ],
        db_path=db_path,
    )

    async def fake_fetch_results(**kwargs):
        return {"source": "test", "fetched_count": 0, "results": [], "errors": []}

    async def fake_load_dongqiudi_detail(match_id):
        assert match_id == "final-dqd-1"
        return (
            {
                "matchSample": {
                    "match_id": "final-dqd-1",
                    "status": "Played",
                    "minute": "90",
                    "start_play": "2026-05-25 13:00:00",
                    "competition": {"name": "测试联赛"},
                    "team_A": {"name": "完场主队", "fs": "2"},
                    "team_B": {"name": "完场客队", "fs": "1"},
                }
            },
            {"source": "dongqiudi.com"},
        )

    monkeypatch.setattr(sources_module, "_fetch_learning_results_from_public_sources", fake_fetch_results)
    monkeypatch.setattr(sources_module, "load_dongqiudi_detail", fake_load_dongqiudi_detail)

    result = asyncio.run(
        sources_module.settle_learning_recommendations(
            auto_fetch=True,
            as_of="2026-05-25T23:30:00+08:00",
            timezone_name="Asia/Shanghai",
            db_path=db_path,
        )
    )

    assert result["match_state_refresh"]["final_result_count"] == 1
    assert result["settlement"]["settled_count"] == 1

    record = learning_store.list_recommendation_records(db_path=db_path, limit=1)[0]
    detail = sources_module.dashboard_match_detail(f"recommendation:{record['id']}", db_path=db_path)

    assert detail["record"]["settlement_status"] == "settled"
    assert detail["record"]["status_label"] == "命中"
    assert detail["record"]["score"] == "2-1"
    assert detail["record"]["score_type"] == "final"
    assert detail["record"]["true_result"]["score"] == "2-1"
    assert detail["record"]["match_state"]["phase"] == "final"


def test_auto_learning_daemon_passes_background_sampling_windows(monkeypatch):
    calls = []

    async def fake_run_auto_learning_cycle(**kwargs):
        calls.append(kwargs)
        return {
            "run_id": "cycle-test",
            "saved_record_count": 3,
            "learning_phase": "collecting_samples",
            "asian_shortlist": {"record_count": 2},
            "jingcai_parlay": {"record_count": 1},
            "settlement": {"settlement": {"settled_count": 0}},
        }

    class StopLoop(Exception):
        pass

    async def fake_sleep(seconds):
        raise StopLoop()

    monkeypatch.setattr(sources_module, "run_auto_learning_cycle", fake_run_auto_learning_cycle)
    monkeypatch.setattr(sources_module.asyncio, "sleep", fake_sleep)

    with pytest.raises(StopLoop):
        asyncio.run(
            sources_module.auto_learning_daemon(
                interval_seconds=60,
                timezone_name="Asia/Shanghai",
                top_n=12,
                limit=80,
                asian_window_minutes=24 * 60,
                parlay_window_minutes=24 * 60,
                learning_observation_limit=40,
                market_snapshot_window_minutes=12 * 60,
                market_snapshot_limit=16,
                market_snapshot_concurrency=3,
                analysis_timeout_seconds=30,
            )
        )

    assert calls[0]["top_n"] == 12
    assert calls[0]["limit"] == 80
    assert calls[0]["asian_window_minutes"] == 24 * 60
    assert calls[0]["parlay_window_minutes"] == 24 * 60
    assert calls[0]["learning_observation_limit"] == 40
    assert calls[0]["analysis_timeout_seconds"] == 30
    assert calls[0]["include_market_snapshot_sync"] is True
    assert calls[0]["market_snapshot_window_minutes"] == 12 * 60
    assert calls[0]["market_snapshot_limit"] == 16
    assert calls[0]["market_snapshot_concurrency"] == 3
    assert sources_module.AUTO_LEARNING_STATE["asian_window_minutes"] == 24 * 60
    assert sources_module.AUTO_LEARNING_STATE["parlay_window_minutes"] == 24 * 60
    assert sources_module.AUTO_LEARNING_STATE["learning_observation_limit"] == 40
    assert sources_module.AUTO_LEARNING_STATE["market_snapshot_sync_enabled"] is True
    assert sources_module.AUTO_LEARNING_STATE["market_snapshot_limit"] == 16


def test_auto_learning_daemon_defaults_to_near_kickoff_predictions_and_wide_snapshot_collection(monkeypatch):
    calls = []

    async def fake_run_auto_learning_cycle(**kwargs):
        calls.append(kwargs)
        return {
            "run_id": "cycle-default-window-test",
            "saved_record_count": 0,
            "learning_phase": "collecting_samples",
        }

    class StopLoop(Exception):
        pass

    async def fake_sleep(seconds):
        raise StopLoop()

    monkeypatch.setattr(sources_module, "run_auto_learning_cycle", fake_run_auto_learning_cycle)
    monkeypatch.setattr(sources_module.asyncio, "sleep", fake_sleep)

    with pytest.raises(StopLoop):
        asyncio.run(sources_module.auto_learning_daemon(interval_seconds=120))

    assert calls[0]["asian_window_minutes"] == 10
    assert calls[0]["parlay_window_minutes"] == 10
    assert calls[0]["market_snapshot_window_minutes"] == 24 * 60
    assert calls[0]["market_snapshot_limit"] == 80


def test_auto_learning_daemon_times_out_stuck_cycle_and_resets_state(monkeypatch):
    class StopLoop(Exception):
        pass

    async def fake_run_auto_learning_cycle(**kwargs):
        sources_module.AUTO_LEARNING_STATE["current_step"] = "asian_shortlist"
        await asyncio.sleep(3600)
        return {"saved_record_count": 1}

    async def fake_sleep(seconds):
        if seconds >= 3600:
            await asyncio.Future()
        raise StopLoop()

    monkeypatch.setattr(sources_module, "run_auto_learning_cycle", fake_run_auto_learning_cycle)
    monkeypatch.setattr(sources_module.asyncio, "sleep", fake_sleep)

    with pytest.raises(StopLoop):
        asyncio.run(
            sources_module.auto_learning_daemon(
                interval_seconds=60,
                cycle_timeout_seconds=1,
            )
        )

    assert sources_module.AUTO_LEARNING_STATE["current_step"] == "idle"
    assert sources_module.AUTO_LEARNING_STATE["last_finished_at_utc"] is not None
    assert sources_module.AUTO_LEARNING_STATE["last_error"].startswith("TimeoutError:")

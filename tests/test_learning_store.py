from __future__ import annotations

from football_data_mcp import learning_store


def test_learning_store_configures_sqlite_for_concurrent_dashboard_reads(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")

    with learning_store._connect(db_path) as conn:
        learning_store.ensure_schema(conn)
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert str(journal_mode).lower() == "wal"
    assert int(busy_timeout) >= 10000


def test_learning_store_records_settles_and_recomputes_calibration(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    saved = learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-1",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
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
                "edge": 0.05,
                "recommendation": "immediate_bet",
                "stake_level": "small",
            },
            {
                "run_id": "cycle-1",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "1x2",
                "league": "测试联赛",
                "home_team": "主队B",
                "away_team": "客队B",
                "market": "1x2",
                "selection": "客队B 客胜",
                "selection_key": "away",
                "decimal_odds": 2.2,
                "model_probability": 0.47,
                "edge": 0.034,
                "recommendation": "condition_observe",
                "stake_level": "watch_only_until_condition",
            },
        ],
        db_path=db_path,
    )

    assert saved == 2
    settled = learning_store.settle_recommendations(
        [
            {"home_team": "主队A", "away_team": "客队A", "home_score": 2, "away_score": 0},
            {"home_team": "主队B", "away_team": "客队B", "home_score": 1, "away_score": 0},
        ],
        db_path=db_path,
    )
    assert settled["settled_count"] == 2

    status = learning_store.recompute_calibration(db_path=db_path)

    assert status["settled_count"] == 2
    assert status["calibration_bucket_count"] >= 2
    asian_bucket = next(item for item in status["buckets"] if item["market"] == "asian_handicap")
    assert asian_bucket["sample_count"] == 1
    assert asian_bucket["hit_count"] == 1
    assert asian_bucket["hit_rate"] == 1.0
    assert asian_bucket["roi"] == 0.9
    one_x_two_bucket = next(item for item in status["buckets"] if item["market"] == "1x2")
    assert one_x_two_bucket["hit_count"] == 0
    assert one_x_two_bucket["roi"] == -1.0


def test_learning_store_settles_asian_quarter_line_half_win(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-2",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "league": "测试联赛",
                "home_team": "主队C",
                "away_team": "客队C",
                "market": "asian_handicap",
                "selection": "主队C +0.25",
                "selection_key": "home_cover",
                "line": 0.25,
                "decimal_odds": 1.8,
                "model_probability": 0.6,
                "recommendation": "immediate_bet",
            }
        ],
        db_path=db_path,
    )

    settled = learning_store.settle_recommendations(
        [{"home_team": "主队C", "away_team": "客队C", "home_score": 1, "away_score": 1}],
        db_path=db_path,
    )

    assert settled["settled_count"] == 1
    record = learning_store.list_recommendation_records(db_path=db_path)[0]
    assert record["settlement_status"] == "settled"
    assert record["payout_multiplier"] == 1.4
    assert record["profit_units"] == 0.4
    assert record["hit"] == 1


def test_learning_store_refreshes_open_recommendation_across_cycles(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    record = {
        "run_id": "cycle-1",
        "tool": "shortlist_value_matches",
        "mode": "balanced",
        "target_market": "asian_handicap",
        "match_id": "match-1",
        "league": "测试联赛",
        "home_team": "主队D",
        "away_team": "客队D",
        "kickoff_utc_plus_8": "2026-05-24T20:00:00+08:00",
        "market": "asian_handicap",
        "selection": "主队D -0.5",
        "selection_key": "home_cover",
        "line": -0.5,
        "decimal_odds": 1.9,
        "model_probability": 0.62,
        "created_at_utc": "2026-05-24T11:50:00+00:00",
    }

    assert learning_store.save_recommendation_records([record], db_path=db_path) == 1
    assert learning_store.save_recommendation_records(
        [
            {
                **record,
                "run_id": "cycle-2",
                "decimal_odds": 1.85,
                "model_probability": 0.64,
                "created_at_utc": "2026-05-24T11:58:00+00:00",
            }
        ],
        db_path=db_path,
    ) == 1

    records = learning_store.list_recommendation_records(db_path=db_path)
    assert len(records) == 1
    assert records[0]["run_id"] == "cycle-2"
    assert records[0]["decimal_odds"] == 1.85
    assert records[0]["model_probability"] == 0.64
    assert records[0]["created_at_utc"] == "2026-05-24T11:58:00+00:00"


def test_learning_store_promotes_open_observation_when_later_cycle_recommends_same_pick(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    base = {
        "tool": "shortlist_value_matches",
        "target_market": "asian_handicap",
        "match_id": "promotion-match",
        "league": "测试联赛",
        "home_team": "晋级主队",
        "away_team": "晋级客队",
        "kickoff_utc_plus_8": "2026-05-24T20:00:00+08:00",
        "market": "asian_handicap",
        "selection": "晋级主队 -0.5",
        "selection_key": "home_cover",
        "line": -0.5,
        "decimal_odds": 1.9,
    }
    observation = {
        **base,
        "run_id": "cycle-observe",
        "mode": "balanced_observation",
        "model_probability": 0.57,
        "recommendation": "condition_observe",
        "raw": {
            "kind": "learning_observation",
            "reason": "multi_bookmaker_snapshot_missing",
        },
    }
    formal = {
        **base,
        "run_id": "cycle-promote",
        "mode": "balanced",
        "model_probability": 0.63,
        "calibrated_probability": 0.61,
        "edge": 0.05,
        "recommendation": "immediate_bet",
        "stake_level": "small",
        "raw": {
            "kind": "shortlist_pick",
            "final_execution_advice": {"action": "bet_now"},
        },
    }

    assert learning_store.save_recommendation_records([observation], db_path=db_path) == 1
    assert learning_store.save_recommendation_records([formal], db_path=db_path) == 1

    records = learning_store.list_recommendation_records(db_path=db_path)
    assert len(records) == 1
    assert records[0]["run_id"] == "cycle-promote"
    assert records[0]["mode"] == "balanced"
    assert records[0]["recommendation"] == "immediate_bet"
    assert records[0]["calibrated_probability"] == 0.61
    assert records[0]["raw"]["kind"] == "shortlist_pick"


def test_learning_store_prefers_match_id_when_settling_repeated_team_pair(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": "cycle-1",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "match_id": "real-match",
                "league": "测试联赛",
                "home_team": "主队E",
                "away_team": "客队E",
                "kickoff_utc_plus_8": "2026-05-24T20:00:00+08:00",
                "market": "asian_handicap",
                "selection": "主队E -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.9,
                "model_probability": 0.62,
            }
        ],
        db_path=db_path,
    )

    learning_store.settle_recommendations(
        [
            {
                "match_id": "other-match",
                "home_team": "主队E",
                "away_team": "客队E",
                "kickoff_utc_plus_8": "2026-05-25T20:00:00+08:00",
                "home_score": 0,
                "away_score": 2,
            },
            {
                "match_id": "real-match",
                "home_team": "主队E",
                "away_team": "客队E",
                "kickoff_utc_plus_8": "2026-05-24T20:00:00+08:00",
                "home_score": 2,
                "away_score": 0,
            },
        ],
        db_path=db_path,
    )

    record = learning_store.list_recommendation_records(db_path=db_path)[0]
    assert record["settlement_status"] == "settled"
    assert record["home_score"] == 2
    assert record["away_score"] == 0
    assert record["hit"] == 1


def test_learning_store_parlay_records_are_tracked_but_not_open_for_single_match_settlement(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    records = learning_store.build_records_from_parlay(
        {
            "tool": "recommend_jingcai_parlay",
            "parlay_mode": "confidence",
            "recommended_tickets": [
                {
                    "parlay_type": "2串1",
                    "recommendation": "parlay_recommended",
                    "stake_level": "tiny",
                    "combined_decimal_odds": 1.8,
                    "estimated_hit_probability": 0.42,
                    "legs": [{"selection": "主胜"}, {"selection": "客胜"}],
                }
            ],
        },
        run_id="cycle-parlay",
    )

    assert learning_store.save_recommendation_records(records, db_path=db_path) == 1
    saved = learning_store.list_recommendation_records(db_path=db_path)[0]
    assert saved["market"] == "parlay"
    assert saved["settlement_status"] == "tracked_only"
    assert learning_store.list_recommendation_records(db_path=db_path, status="open") == []


def test_shadow_prediction_store_records_settles_and_reports_metrics(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    records = [
        {
            "run_id": "shadow-cycle-1",
            "tool": "shortlist_value_matches",
            "mode": "balanced",
            "target_market": "asian_handicap",
            "decision": "accepted",
            "match_id": "shadow-hit",
            "league": "影子联赛",
            "home_team": "影子主队A",
            "away_team": "影子客队A",
            "market": "asian_handicap",
            "selection": "影子主队A -0.5",
            "selection_key": "home_cover",
            "line": -0.5,
            "decimal_odds": 1.9,
            "model_probability": 0.62,
            "calibrated_probability": 0.61,
            "edge": 0.05,
            "recommendation": "immediate_bet",
        },
        {
            "run_id": "shadow-cycle-1",
            "tool": "shortlist_value_matches",
            "mode": "balanced",
            "target_market": "asian_handicap",
            "decision": "rejected",
            "rejection_reason": "no_positive_edge",
            "match_id": "shadow-miss",
            "league": "影子联赛",
            "home_team": "影子主队B",
            "away_team": "影子客队B",
            "market": "1x2",
            "selection": "影子客队B 客胜",
            "selection_key": "away",
            "decimal_odds": 2.2,
            "model_probability": 0.45,
            "edge": -0.01,
            "recommendation": "no_value",
        },
    ]

    assert learning_store.save_shadow_prediction_records(records, db_path=db_path) == 2
    assert learning_store.save_shadow_prediction_records(records, db_path=db_path) == 0

    open_records = learning_store.list_shadow_prediction_records(db_path=db_path, status="open")
    assert len(open_records) == 2
    assert {record["decision"] for record in open_records} == {"accepted", "rejected"}

    settlement = learning_store.settle_shadow_predictions(
        [
            {"match_id": "shadow-hit", "home_team": "影子主队A", "away_team": "影子客队A", "home_score": 2, "away_score": 0},
            {"match_id": "shadow-miss", "home_team": "影子主队B", "away_team": "影子客队B", "home_score": 1, "away_score": 0},
        ],
        db_path=db_path,
    )

    assert settlement["settled_count"] == 2
    metrics = learning_store.shadow_prediction_metrics(db_path=db_path)
    assert metrics["record_counts"]["settled"] == 2
    assert metrics["by_decision"]["accepted"]["hit_rate"] == 1.0
    assert metrics["by_decision"]["accepted"]["roi"] == 0.9
    assert metrics["by_decision"]["rejected"]["hit_rate"] == 0.0
    assert metrics["by_decision"]["rejected"]["roi"] == -1.0
    assert metrics["by_rejection_reason"]["no_positive_edge"]["total_count"] == 1


def test_build_shadow_prediction_records_from_shortlist_includes_picks_and_rejections():
    result = {
        "tool": "shortlist_value_matches",
        "mode": "balanced",
        "target_market": "asian_handicap",
        "balanced_thresholds": {
            "min_calibrated_probability": 0.58,
            "min_decimal_odds": 1.65,
            "max_decimal_odds": 2.05,
            "min_value_edge": 0.02,
        },
        "picks": [
            {
                "match": {"match_id": "shadow-pick", "league": "影子联赛", "home_team": "主队A", "away_team": "客队A"},
                "best_candidate": {
                    "market": "asian_handicap",
                    "selection": "主队A -0.5",
                    "selection_key": "home_cover",
                    "line": -0.5,
                    "decimal_odds": 1.88,
                    "model_probability": 0.62,
                    "calibrated_probability": 0.61,
                    "edge": 0.05,
                    "recommendation": "immediate_bet",
                },
                "selection_confidence": {"calibrated_probability": 0.61},
            }
        ],
        "rejected": [
            {
                "reason": "calibrated_probability_below_threshold",
                "match": {"match_id": "shadow-reject", "league": "影子联赛", "home_team": "主队B", "away_team": "客队B"},
                "best_candidate": {
                    "market": "asian_handicap",
                    "selection": "客队B +0.5",
                    "selection_key": "away_cover",
                    "line": 0.5,
                    "decimal_odds": 1.82,
                    "model_probability": 0.55,
                    "edge": 0.03,
                    "recommendation": "immediate_bet",
                },
            }
        ],
    }

    records = learning_store.build_shadow_prediction_records_from_shortlist(result, run_id="shadow-cycle", limit=10)

    assert [record["decision"] for record in records] == ["accepted", "rejected"]
    assert records[0]["thresholds"]["min_calibrated_probability"] == 0.58
    assert records[0]["raw"]["kind"] == "shadow_prediction"
    assert records[1]["rejection_reason"] == "calibrated_probability_below_threshold"
    assert records[1]["settlement_status"] == "open"


def test_recompute_calibration_builds_exact_and_broad_buckets(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    learning_store.save_recommendation_records(
        [
            {
                "run_id": f"cycle-{index}",
                "tool": "shortlist_value_matches",
                "mode": "balanced",
                "target_market": "asian_handicap",
                "match_id": f"cal-match-{index}",
                "league": "测试联赛A" if index == 0 else "测试联赛B",
                "home_team": f"主队F{index}",
                "away_team": f"客队F{index}",
                "market": "asian_handicap",
                "selection": f"主队F{index} -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.9,
                "model_probability": 0.62,
            }
            for index in range(2)
        ],
        db_path=db_path,
    )
    learning_store.settle_recommendations(
        [
            {"match_id": "cal-match-0", "home_team": "主队F0", "away_team": "客队F0", "home_score": 2, "away_score": 0},
            {"match_id": "cal-match-1", "home_team": "主队F1", "away_team": "客队F1", "home_score": 0, "away_score": 1},
        ],
        db_path=db_path,
    )

    status = learning_store.recompute_calibration(db_path=db_path)
    broad_line_bucket = next(
        bucket
        for bucket in status["buckets"]
        if bucket["market"] == "asian_handicap"
        and bucket["league_bucket"] == "ALL"
        and bucket["line_bucket"] == "line:-0.5"
    )
    broad_market_bucket = next(
        bucket
        for bucket in status["buckets"]
        if bucket["market"] == "asian_handicap"
        and bucket["league_bucket"] == "ALL"
        and bucket["line_bucket"] == "line:ALL"
        and bucket["probability_bucket"] == "prob:ALL"
    )

    assert broad_line_bucket["sample_count"] == 2
    assert broad_market_bucket["sample_count"] == 2


def test_update_strategy_state_tightens_balanced_policy_after_poor_settled_results(tmp_path):
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
                "match_id": f"strategy-match-{index}",
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
        )
        results.append(
            {
                "match_id": f"strategy-match-{index}",
                "home_team": f"策略主队{index}",
                "away_team": f"策略客队{index}",
                "home_score": 0,
                "away_score": 1,
            }
        )

    learning_store.save_recommendation_records(records, db_path=db_path)
    learning_store.settle_recommendations(results, db_path=db_path)
    learning_store.recompute_calibration(db_path=db_path)

    state = learning_store.update_strategy_state(db_path=db_path, market="asian_handicap", mode="balanced")

    assert state["status"] == "live_calibration_active"
    assert state["active"] is True
    assert state["sample_count"] == 20
    assert state["min_calibrated_probability"] > 0.60  # base default was raised from 0.58 to 0.60
    assert state["min_value_edge"] > 0.02
    assert state["min_decimal_odds"] >= 1.55  # base default was lowered from 1.65 to 1.55

    persisted = learning_store.get_strategy_state(db_path=db_path, market="asian_handicap", mode="balanced")
    assert persisted["status"] == "live_calibration_active"
    assert persisted["min_calibrated_probability"] == state["min_calibrated_probability"]


def test_update_strategy_state_ignores_no_value_observations_but_keeps_calibration(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    records = []
    results = []
    for index in range(20):
        records.append(
            {
                "run_id": f"no-value-observation-{index}",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": f"no-value-observation-{index}",
                "league": "观察联赛",
                "home_team": f"观察主队{index}",
                "away_team": f"观察客队{index}",
                "market": "asian_handicap",
                "selection": f"观察主队{index} -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.8,
                "model_probability": 0.44,
                "calibrated_probability": 0.44,
                "edge": -0.04,
                "recommendation": "no_value",
                "raw": {"kind": "learning_observation", "reason": "no_positive_edge"},
            }
        )
        results.append(
            {
                "match_id": f"no-value-observation-{index}",
                "home_team": f"观察主队{index}",
                "away_team": f"观察客队{index}",
                "home_score": 0,
                "away_score": 1,
            }
        )
    for index in range(20):
        records.append(
            {
                "run_id": f"actionable-observation-{index}",
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match_id": f"actionable-observation-{index}",
                "league": "观察联赛",
                "home_team": f"候选主队{index}",
                "away_team": f"候选客队{index}",
                "market": "asian_handicap",
                "selection": f"候选主队{index} -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "decimal_odds": 1.8,
                "model_probability": 0.62,
                "calibrated_probability": 0.62,
                "edge": 0.06,
                "recommendation": "immediate_bet",
                "stake_level": "small",
                "raw": {"kind": "learning_observation", "reason": "paper_track"},
            }
        )
        results.append(
            {
                "match_id": f"actionable-observation-{index}",
                "home_team": f"候选主队{index}",
                "away_team": f"候选客队{index}",
                "home_score": 2,
                "away_score": 0,
            }
        )

    learning_store.save_recommendation_records(records, db_path=db_path)
    learning_store.settle_recommendations(results, db_path=db_path)

    calibration = learning_store.recompute_calibration(db_path=db_path)
    broad_market_bucket = next(
        bucket
        for bucket in calibration["buckets"]
        if bucket["market"] == "asian_handicap"
        and bucket["league_bucket"] == "ALL"
        and bucket["line_bucket"] == "line:ALL"
        and bucket["probability_bucket"] == "prob:ALL"
    )
    state = learning_store.update_strategy_state(db_path=db_path, market="asian_handicap", mode="balanced")

    assert broad_market_bucket["sample_count"] == 40
    assert state["status"] == "live_calibration_active"
    assert state["active"] is True
    assert state["sample_count"] == 20
    assert state["hit_rate"] == 1.0
    assert state["roi"] == 0.8
    assert state["min_calibrated_probability"] < 0.60  # base default was raised from 0.58 to 0.60
    assert state["raw"]["source_bucket"]["raw"]["ignored_observation_count"] == 20
    assert state["raw"]["source_bucket"]["raw"]["bucket_scope"] == "strategy_actionable_global"

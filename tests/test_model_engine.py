from football_data_mcp import model_engine
from football_data_mcp import sources as sources_module


def _quality_contract() -> dict:
    return {
        "supported_markets": {
            "moneyline_1x2": True,
            "asian_handicap": True,
            "over_under": True,
        },
        "preferred_moneyline_1x2": {
            "provider": "Average",
            "current_metrics": {
                "available": True,
                "normalized_probability": {
                    "home": 0.48,
                    "draw": 0.27,
                    "away": 0.25,
                },
            },
        },
        "preferred_asian_handicap": {
            "provider": "Average",
            "current_metrics": {
                "available": True,
                "line": -0.5,
                "normalized_probability": {
                    "home_cover": 0.52,
                    "away_cover": 0.48,
                },
                "decimal_odds": {
                    "home_cover": 1.92,
                    "away_cover": 2.05,
                },
            },
        },
        "preferred_over_under": {
            "provider": "Average",
            "current_metrics": {
                "available": True,
                "line": 2.5,
                "normalized_probability": {
                    "over": 0.54,
                    "under": 0.46,
                },
                "decimal_odds": {
                    "over": 1.86,
                    "under": 2.12,
                },
            },
        },
    }


def test_model_engine_builds_scoreline_distribution_and_market_edges():
    projection = model_engine.build_model_projection(
        match={"home_team": "Home", "away_team": "Away"},
        odds={"quality_contract": _quality_contract()},
        form={
            "available": True,
            "recent_record_summary": {
                "home": {
                    "goals_for_per_match": 1.8,
                    "goals_against_per_match": 0.9,
                    "sample_size": 5,
                },
                "away": {
                    "goals_for_per_match": 1.0,
                    "goals_against_per_match": 1.7,
                    "sample_size": 5,
                },
            },
        },
    )

    assert projection["available"] is True
    assert projection["version"].startswith("football-data-mcp-model-engine")
    assert projection["method"] == "dixon_coles_adjusted_market_anchored_poisson_v1"
    assert projection["model_quality"]["fallback_used"] is False
    assert projection["dixon_coles"]["low_score_adjustment"] is True
    assert projection["independent_poisson_baseline"]["method"] == "market_anchored_independent_poisson_baseline_v1"
    assert projection["expected_goals"]["home"] > projection["expected_goals"]["away"]
    assert abs(projection["model_quality"]["scoreline_probability_sum"] - 1.0) < 0.0001
    assert projection["derived_probabilities"]["1x2"]["home"] > projection["derived_probabilities"]["1x2"]["away"]
    assert projection["derived_probabilities"]["over_under"]["line"] == 2.5
    assert projection["derived_probabilities"]["asian_handicap"]["line"] == -0.5
    assert projection["market_edges"]["over_under"]["over"] == (
        projection["derived_probabilities"]["over_under"]["over"] - 0.54
    )
    assert projection["top_scorelines"][0]["probability"] >= projection["top_scorelines"][1]["probability"]


def test_dixon_coles_adjustment_changes_low_score_distribution_without_losing_probability_mass():
    independent = {
        (row["home_goals"], row["away_goals"]): row["probability"]
        for row in model_engine._scoreline_distribution(1.2, 1.1, 10, 0.0)
    }
    adjusted = {
        (row["home_goals"], row["away_goals"]): row["probability"]
        for row in model_engine._scoreline_distribution(1.2, 1.1, 10, -0.10)
    }

    assert abs(sum(adjusted.values()) - 1.0) < 0.0001
    assert adjusted[(0, 0)] > independent[(0, 0)]
    assert adjusted[(1, 1)] > independent[(1, 1)]
    assert adjusted[(1, 0)] < independent[(1, 0)]
    assert adjusted[(0, 1)] < independent[(0, 1)]


def test_model_engine_exposes_rolling_elo_strength_without_unvalidated_probability_push():
    odds = {"quality_contract": _quality_contract()}
    neutral_form = {
        "available": True,
        "recent_record_summary": {
            "home": {
                "goals_for_per_match": 1.3,
                "goals_against_per_match": 1.2,
                "sample_size": 5,
            },
            "away": {
                "goals_for_per_match": 1.2,
                "goals_against_per_match": 1.3,
                "sample_size": 5,
            },
        },
    }
    elo_projection = model_engine.build_model_projection(
        match={"home_team": "Home", "away_team": "Away"},
        odds=odds,
        form={
            **neutral_form,
            "team_strength": {
                "rolling_elo": {
                    "available": True,
                    "expected_goal_diff_hint": 0.8,
                }
            },
        },
    )

    assert elo_projection["expected_goals"]["strength_goal_diff_hint"] == 0.8
    assert elo_projection["expected_goals"]["strength_goal_diff_loss_weight"] == 0.0
    assert elo_projection["model_quality"]["feature_coverage"]["rolling_elo"] is True


def test_total_only_projection_keeps_goal_split_neutral_without_side_signal():
    projection = model_engine.build_model_projection(
        match={"home_team": "Home", "away_team": "Away"},
        odds={
            "quality_contract": {
                "supported_markets": {
                    "moneyline_1x2": False,
                    "asian_handicap": False,
                    "over_under": True,
                },
                "preferred_over_under": {
                    "provider": "Average",
                    "current_metrics": {
                        "available": True,
                        "line": 2.5,
                        "normalized_probability": {
                            "over": 0.52,
                            "under": 0.48,
                        },
                    },
                },
            }
        },
        form={"available": False},
    )

    assert projection["available"] is True
    assert projection["model_quality"]["feature_coverage"]["over_under"] is True
    assert abs(projection["expected_goals"]["home"] - projection["expected_goals"]["away"]) <= 0.2


def test_asian_only_projection_uses_handicap_market_as_model_constraint():
    projection = model_engine.build_model_projection(
        match={"home_team": "Home", "away_team": "Away"},
        odds={
            "quality_contract": {
                "supported_markets": {
                    "moneyline_1x2": False,
                    "asian_handicap": True,
                    "over_under": False,
                },
                "preferred_asian_handicap": {
                    "provider": "Average",
                    "current_metrics": {
                        "available": True,
                        "line": -0.5,
                        "normalized_probability": {
                            "home_cover": 0.58,
                            "away_cover": 0.42,
                        },
                    },
                },
            }
        },
        form={"available": False},
    )

    assert projection["available"] is True
    assert projection["derived_probabilities"]["asian_handicap"]["line"] == -0.5
    assert abs(projection["derived_probabilities"]["asian_handicap"]["home_cover"] - 0.58) < 0.08
    assert projection["model_quality"]["feature_coverage"]["asian_handicap"] is True


def test_decision_support_uses_model_engine_projection_for_candidate_edges():
    odds = {"quality_contract": _quality_contract()}

    support = sources_module.build_betting_decision_support(
        match={
            "home_team": "Home",
            "away_team": "Away",
            "time_window": {
                "as_of": "2026-05-23T18:00:00+08:00",
                "kickoff": "2026-05-23T20:00:00+08:00",
            },
        },
        odds=odds,
        form={
            "available": True,
            "recent_record_summary": {
                "home": {
                    "goals_for_per_match": 1.8,
                    "goals_against_per_match": 0.9,
                    "sample_size": 5,
                },
                "away": {
                    "goals_for_per_match": 1.0,
                    "goals_against_per_match": 1.7,
                    "sample_size": 5,
                },
            },
        },
        match_context=None,
        quality_flags=[],
        quality_warnings=[],
    )

    assert support["model_engine"]["available"] is True
    assert support["model_engine"]["method"] == "dixon_coles_adjusted_market_anchored_poisson_v1"
    assert support["market_candidates"]
    assert all(
        candidate["probability_source"] == "MCP Dixon-Coles adjusted scoreline distribution"
        for candidate in support["market_candidates"]
    )
    assert support["best_candidate"]["edge_source"] == "model_engine"

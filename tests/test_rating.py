from __future__ import annotations

from datetime import datetime, timezone

from football_data_mcp import rating


def _sample(date: str, home: str, away: str, home_goals: int, away_goals: int) -> dict:
    return {
        "kickoff": datetime.fromisoformat(date).replace(tzinfo=timezone.utc),
        "match": {
            "home_team": home,
            "away_team": away,
        },
        "actual": {
            "home_goals": home_goals,
            "away_goals": away_goals,
        },
    }


def test_rolling_elo_context_uses_only_prior_results_for_pre_match_strength():
    prior_samples = [
        _sample("2025-08-01T15:00:00", "Alpha", "Beta", 3, 0),
        _sample("2025-08-08T15:00:00", "Gamma", "Alpha", 1, 2),
        _sample("2025-08-15T15:00:00", "Beta", "Gamma", 0, 0),
    ]

    context = rating.build_pre_match_elo_context(
        prior_samples,
        home_team="Alpha",
        away_team="Beta",
    )

    assert context["available"] is True
    assert context["method"] == "rolling_elo_time_weighted_v2"
    assert context["home"]["team"] == "Alpha"
    assert context["away"]["team"] == "Beta"
    assert context["home"]["matches"] == 2
    assert context["away"]["matches"] == 2
    assert context["home"]["rating"] > context["away"]["rating"]
    assert context["raw_rating_diff_home_minus_away"] > 0
    assert context["adjusted_rating_diff_home_minus_away"] > context["raw_rating_diff_home_minus_away"]
    assert 0.5 < context["expected_home_result"] < 1.0
    assert context["leakage_policy"] == "ratings are built only from prior completed samples"


def test_rolling_elo_context_requires_both_teams_to_have_prior_matches():
    context = rating.build_pre_match_elo_context(
        [
            _sample("2025-08-01T15:00:00", "Gamma", "Delta", 2, 1),
        ],
        home_team="Alpha",
        away_team="Beta",
    )

    assert context["available"] is False
    assert context["home"]["matches"] == 0
    assert context["away"]["matches"] == 0

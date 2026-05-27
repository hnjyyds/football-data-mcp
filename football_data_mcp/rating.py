from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


DEFAULT_RATING = 1500.0
DEFAULT_HOME_ADVANTAGE = 65.0
DEFAULT_K_FACTOR = 20.0
K_FACTOR_NEW_TEAM = 30.0      # < 10 matches played
K_FACTOR_ESTABLISHED = 20.0  # >= 10 matches played
TIME_DECAY_HALFLIFE_DAYS = 180.0  # Elo updates older than this are down-weighted
RATING_METHOD = "rolling_elo_time_weighted_v2"
LEAKAGE_POLICY = "ratings are built only from prior completed samples"


def _round(value: float, ndigits: int = 6) -> float:
    return round(float(value), ndigits)


def _team_rating(ratings: dict[str, float], team: str) -> float:
    return ratings.get(team, DEFAULT_RATING)


def _expected_result(home_rating: float, away_rating: float, *, home_advantage: float) -> float:
    adjusted_diff = (home_rating + home_advantage) - away_rating
    return 1.0 / (1.0 + 10 ** (-adjusted_diff / 400.0))


def _actual_result(home_goals: int, away_goals: int) -> float:
    if home_goals > away_goals:
        return 1.0
    if home_goals == away_goals:
        return 0.5
    return 0.0


def _margin_multiplier(home_goals: int, away_goals: int) -> float:
    margin = abs(home_goals - away_goals)
    if margin <= 1:
        return 1.0
    return 1.0 + math.log(margin) * 0.35


def _adaptive_k_factor(match_count: int) -> float:
    """Return higher K for teams with few matches (more uncertainty)."""
    if match_count < 10:
        return K_FACTOR_NEW_TEAM
    return K_FACTOR_ESTABLISHED


def _time_decay_weight(kickoff_str: str | None, reference_time: datetime | None) -> float:
    """Exponential decay weight based on days between match and reference time."""
    if not kickoff_str or not reference_time:
        return 1.0
    try:
        if isinstance(kickoff_str, datetime):
            kickoff = kickoff_str
        else:
            kickoff = datetime.fromisoformat(str(kickoff_str).replace("Z", "+00:00"))
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        days_ago = (reference_time - kickoff).total_seconds() / 86400.0
        if days_ago < 0:
            return 1.0
        return math.exp(-days_ago * math.log(2) / TIME_DECAY_HALFLIFE_DAYS)
    except (ValueError, TypeError, AttributeError):
        return 1.0


def _completed_score(sample: dict[str, Any]) -> tuple[int, int] | None:
    actual = sample.get("actual") or {}
    try:
        return int(actual["home_goals"]), int(actual["away_goals"])
    except (KeyError, TypeError, ValueError):
        return None


def build_ratings_from_samples(
    samples: list[dict[str, Any]],
    *,
    home_advantage: float = DEFAULT_HOME_ADVANTAGE,
    k_factor: float = DEFAULT_K_FACTOR,
    use_time_decay: bool = True,
    use_adaptive_k: bool = True,
) -> dict[str, dict[str, Any]]:
    sorted_samples = sorted(samples, key=lambda item: item.get("kickoff") or "")
    reference_time: datetime | None = None
    if sorted_samples and use_time_decay:
        last_kickoff = sorted_samples[-1].get("kickoff")
        if last_kickoff:
            try:
                reference_time = datetime.fromisoformat(str(last_kickoff).replace("Z", "+00:00"))
                if reference_time.tzinfo is None:
                    reference_time = reference_time.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                reference_time = None

    ratings: dict[str, float] = {}
    match_counts: dict[str, int] = {}

    for sample in sorted_samples:
        match = sample.get("match") or {}
        home_team = str(match.get("home_team") or "").strip()
        away_team = str(match.get("away_team") or "").strip()
        score = _completed_score(sample)
        if not home_team or not away_team or score is None:
            continue

        home_goals, away_goals = score
        home_count = match_counts.get(home_team, 0)
        away_count = match_counts.get(away_team, 0)

        effective_k = k_factor
        if use_adaptive_k:
            effective_k = (_adaptive_k_factor(home_count) + _adaptive_k_factor(away_count)) / 2.0

        time_weight = 1.0
        if use_time_decay and reference_time:
            time_weight = _time_decay_weight(sample.get("kickoff"), reference_time)

        home_rating = _team_rating(ratings, home_team)
        away_rating = _team_rating(ratings, away_team)
        expected_home = _expected_result(home_rating, away_rating, home_advantage=home_advantage)
        actual_home = _actual_result(home_goals, away_goals)
        delta = effective_k * _margin_multiplier(home_goals, away_goals) * (actual_home - expected_home) * time_weight
        ratings[home_team] = home_rating + delta
        ratings[away_team] = away_rating - delta
        match_counts[home_team] = home_count + 1
        match_counts[away_team] = away_count + 1

    return {
        team: {
            "team": team,
            "rating": _round(rating, 3),
            "matches": int(match_counts.get(team, 0)),
        }
        for team, rating in ratings.items()
    }


def build_pre_match_elo_context(
    prior_samples: list[dict[str, Any]],
    *,
    home_team: str,
    away_team: str,
    home_advantage: float = DEFAULT_HOME_ADVANTAGE,
    k_factor: float = DEFAULT_K_FACTOR,
    use_time_decay: bool = True,
    use_adaptive_k: bool = True,
) -> dict[str, Any]:
    team_ratings = build_ratings_from_samples(
        prior_samples,
        home_advantage=home_advantage,
        k_factor=k_factor,
        use_time_decay=use_time_decay,
        use_adaptive_k=use_adaptive_k,
    )
    home = team_ratings.get(
        home_team,
        {"team": home_team, "rating": DEFAULT_RATING, "matches": 0},
    )
    away = team_ratings.get(
        away_team,
        {"team": away_team, "rating": DEFAULT_RATING, "matches": 0},
    )
    home_rating = float(home["rating"])
    away_rating = float(away["rating"])
    raw_diff = home_rating - away_rating
    adjusted_diff = raw_diff + home_advantage
    expected_home = _expected_result(home_rating, away_rating, home_advantage=home_advantage)
    available = int(home.get("matches") or 0) > 0 and int(away.get("matches") or 0) > 0

    return {
        "available": available,
        "method": RATING_METHOD,
        "home": home,
        "away": away,
        "home_advantage_points": _round(home_advantage, 3),
        "raw_rating_diff_home_minus_away": _round(raw_diff, 3),
        "adjusted_rating_diff_home_minus_away": _round(adjusted_diff, 3),
        "expected_home_result": _round(expected_home),
        "expected_goal_diff_hint": _round(max(min(adjusted_diff / 260.0, 1.4), -1.4), 4) if available else None,
        "time_decay_enabled": use_time_decay,
        "adaptive_k_enabled": use_adaptive_k,
        "leakage_policy": LEAKAGE_POLICY,
    }

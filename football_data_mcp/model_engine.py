from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

import numpy as np


MODEL_ENGINE_VERSION = "football-data-mcp-model-engine-2026-05-27"
MODEL_ENGINE_METHOD = "dixon_coles_adjusted_market_anchored_poisson_v1"
INDEPENDENT_BASELINE_METHOD = "market_anchored_independent_poisson_baseline_v1"
ROLLING_ELO_GOAL_DIFF_LOSS_WEIGHT = 0.15
DIXON_COLES_RHO_GRID = tuple(round(-0.20 + index * 0.02, 4) for index in range(21))
HISTORICAL_DIXON_COLES_RHO_GRID = DIXON_COLES_RHO_GRID
MONEYLINE_LOSS_WEIGHT = 2.0
TOTALS_LOSS_WEIGHT = 1.5
ASIAN_HANDICAP_LOSS_WEIGHT = 1.2
SIDE_NEUTRALITY_LOSS_WEIGHT = 0.5


def parse_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def round_metric(value: float | None, ndigits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), ndigits)


def _poisson_pmf(mean: float, goals: int) -> float:
    return math.exp(-mean) * (mean**goals) / math.factorial(goals)


def _poisson_log_pmf(mean: float, goals: int) -> float:
    return -mean + goals * math.log(mean) - math.lgamma(goals + 1)


def _dixon_coles_tau(home_goals: int, away_goals: int, home_xg: float, away_xg: float, rho: float) -> float:
    if abs(rho) < 1e-12:
        return 1.0
    if home_goals == 0 and away_goals == 0:
        return 1.0 - home_xg * away_xg * rho
    if home_goals == 0 and away_goals == 1:
        return 1.0 + home_xg * rho
    if home_goals == 1 and away_goals == 0:
        return 1.0 + away_xg * rho
    if home_goals == 1 and away_goals == 1:
        return 1.0 - rho
    return 1.0


def estimate_dixon_coles_rho_from_scorelines(
    scorelines: list[dict[str, Any]],
    *,
    min_sample_count: int = 20,
    rho_grid: tuple[float, ...] = HISTORICAL_DIXON_COLES_RHO_GRID,
) -> dict[str, Any]:
    usable = []
    for row in scorelines:
        home_goals = parse_float(row.get("home_goals"))
        away_goals = parse_float(row.get("away_goals"))
        if home_goals is None or away_goals is None:
            continue
        if home_goals < 0 or away_goals < 0:
            continue
        usable.append((int(home_goals), int(away_goals)))

    if len(usable) < max(1, int(min_sample_count or 0)):
        return {
            "available": False,
            "method": "league_scoreline_dixon_coles_rho_mle_v1",
            "reason": "insufficient_completed_scorelines",
            "sample_count": len(usable),
            "min_sample_count": max(1, int(min_sample_count or 0)),
        }

    home_goal_mean = max(sum(home for home, _away in usable) / len(usable), 0.05)
    away_goal_mean = max(sum(away for _home, away in usable) / len(usable), 0.05)

    best_rho = 0.0
    best_log_likelihood = float("-inf")
    zero_log_likelihood: float | None = None
    grid_results = []
    for rho in rho_grid:
        log_likelihood = 0.0
        valid = True
        for home_goals, away_goals in usable:
            tau = _dixon_coles_tau(home_goals, away_goals, home_goal_mean, away_goal_mean, rho)
            if tau <= 0:
                valid = False
                break
            log_likelihood += (
                _poisson_log_pmf(home_goal_mean, home_goals)
                + _poisson_log_pmf(away_goal_mean, away_goals)
                + math.log(tau)
            )
        if not valid:
            continue
        grid_results.append({"rho": round_metric(rho, 4), "log_likelihood": round_metric(log_likelihood, 6)})
        if abs(rho) < 1e-12:
            zero_log_likelihood = log_likelihood
        if log_likelihood > best_log_likelihood:
            best_rho = float(rho)
            best_log_likelihood = log_likelihood

    if not grid_results:
        return {
            "available": False,
            "method": "league_scoreline_dixon_coles_rho_mle_v1",
            "reason": "no_valid_rho_candidate",
            "sample_count": len(usable),
            "min_sample_count": max(1, int(min_sample_count or 0)),
        }

    low_score_count = sum(1 for home_goals, away_goals in usable if home_goals <= 1 and away_goals <= 1)
    return {
        "available": True,
        "method": "league_scoreline_dixon_coles_rho_mle_v1",
        "rho": round_metric(best_rho, 4),
        "sample_count": len(usable),
        "min_sample_count": max(1, int(min_sample_count or 0)),
        "home_goal_mean": round_metric(home_goal_mean, 4),
        "away_goal_mean": round_metric(away_goal_mean, 4),
        "low_score_count": low_score_count,
        "low_score_share": round_metric(low_score_count / len(usable)),
        "log_likelihood": round_metric(best_log_likelihood, 6),
        "baseline_log_likelihood_at_zero": round_metric(zero_log_likelihood, 6),
        "log_likelihood_gain_vs_zero": (
            round_metric(best_log_likelihood - zero_log_likelihood, 6)
            if zero_log_likelihood is not None
            else None
        ),
        "rho_grid": [round_metric(value, 4) for value in rho_grid],
        "grid_results": grid_results,
        "estimation_rule": "Conditional maximum likelihood over rho using completed prior league scorelines and empirical home/away goal means.",
    }


@lru_cache(maxsize=32768)
def _scoreline_distribution(
    home_xg: float,
    away_xg: float,
    max_goals: int = 10,
    dixon_coles_rho: float = 0.0,
) -> tuple[dict[str, Any], ...]:
    rows = []
    for home_goals in range(max_goals + 1):
        home_prob = _poisson_pmf(home_xg, home_goals)
        for away_goals in range(max_goals + 1):
            tau = _dixon_coles_tau(home_goals, away_goals, home_xg, away_xg, dixon_coles_rho)
            probability = home_prob * _poisson_pmf(away_xg, away_goals) * max(tau, 0.001)
            rows.append(
                {
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "total_goals": home_goals + away_goals,
                    "margin": home_goals - away_goals,
                    "probability": probability,
                }
            )

    probability_sum = sum(row["probability"] for row in rows)
    if probability_sum:
        for row in rows:
            row["probability"] = row["probability"] / probability_sum
    return tuple(rows)


def _one_x_two_probabilities(distribution: list[dict[str, Any]]) -> dict[str, float]:
    home = sum(row["probability"] for row in distribution if row["margin"] > 0)
    draw = sum(row["probability"] for row in distribution if row["margin"] == 0)
    away = sum(row["probability"] for row in distribution if row["margin"] < 0)
    return {
        "home": round_metric(home) or 0.0,
        "draw": round_metric(draw) or 0.0,
        "away": round_metric(away) or 0.0,
    }


@lru_cache(maxsize=4096)
def _one_x_two_for_xg(
    home_xg: float,
    away_xg: float,
    max_goals: int = 10,
    dixon_coles_rho: float = 0.0,
) -> dict[str, float]:
    return _one_x_two_probabilities(_scoreline_distribution(home_xg, away_xg, max_goals, dixon_coles_rho))


def _split_quarter_line(line: float) -> tuple[float, ...]:
    doubled = line * 2
    if abs(doubled - round(doubled)) < 1e-9:
        return (line,)
    lower = math.floor(doubled) / 2
    upper = lower + 0.5
    return (lower, upper)


def _settlement_weight(score_after_line: float) -> float:
    if score_after_line > 1e-9:
        return 1.0
    if score_after_line < -1e-9:
        return 0.0
    return 0.5


def _asian_selection_probability(distribution: list[dict[str, Any]], line: float, *, home: bool) -> float:
    split_lines = _split_quarter_line(line if home else -line)
    total = 0.0
    for row in distribution:
        margin = row["margin"] if home else -row["margin"]
        split_value = sum(_settlement_weight(margin + split_line) for split_line in split_lines) / len(split_lines)
        total += row["probability"] * split_value
    return round_metric(total) or 0.0


def _total_selection_probability(distribution: list[dict[str, Any]], line: float, *, over: bool) -> float:
    split_lines = _split_quarter_line(line)
    total = 0.0
    for row in distribution:
        goals = row["total_goals"]
        if over:
            split_value = sum(_settlement_weight(goals - split_line) for split_line in split_lines) / len(split_lines)
        else:
            split_value = sum(_settlement_weight(split_line - goals) for split_line in split_lines) / len(split_lines)
        total += row["probability"] * split_value
    return round_metric(total) or 0.0


@lru_cache(maxsize=16384)
def _total_selection_probability_for_xg(
    home_xg: float,
    away_xg: float,
    line: float,
    over: bool,
    max_goals: int = 10,
    dixon_coles_rho: float = 0.0,
) -> float:
    return _total_selection_probability(
        _scoreline_distribution(home_xg, away_xg, max_goals, dixon_coles_rho),
        line,
        over=over,
    )


@lru_cache(maxsize=16384)
def _asian_selection_probability_for_xg(
    home_xg: float,
    away_xg: float,
    line: float,
    home: bool,
    max_goals: int = 10,
    dixon_coles_rho: float = 0.0,
) -> float:
    return _asian_selection_probability(
        _scoreline_distribution(home_xg, away_xg, max_goals, dixon_coles_rho),
        line,
        home=home,
    )


def _market_probabilities(metrics: dict[str, Any], keys: tuple[str, ...]) -> dict[str, float]:
    probabilities = metrics.get("normalized_probability") or {}
    return {
        key: float(value)
        for key in keys
        if (value := parse_float(probabilities.get(key))) is not None
    }


_FORM_DECAY_WEIGHTS = np.array([0.40, 0.25, 0.16, 0.11, 0.08], dtype=np.float64)
_FORM_DECAY_WEIGHTS = _FORM_DECAY_WEIGHTS / _FORM_DECAY_WEIGHTS.sum()


def _form_total_goals(form: dict[str, Any]) -> float | None:
    summary = (form or {}).get("recent_record_summary") or {}
    home = summary.get("home") or {}
    away = summary.get("away") or {}
    estimates = []
    home_for = parse_float(home.get("goals_for_per_match"))
    home_against = parse_float(home.get("goals_against_per_match"))
    away_for = parse_float(away.get("goals_for_per_match"))
    away_against = parse_float(away.get("goals_against_per_match"))
    if home_for is not None and away_against is not None:
        estimates.append((home_for + away_against) / 2)
    if away_for is not None and home_against is not None:
        estimates.append((away_for + home_against) / 2)
    if estimates:
        return round_metric(sum(estimates), 4)
    return None


def apply_form_decay_weights(goals_sequence: list[float]) -> float:
    """Apply exponential decay weighting to a sequence of per-match goal values (most recent first)."""
    if not goals_sequence:
        return 0.0
    n = min(len(goals_sequence), len(_FORM_DECAY_WEIGHTS))
    weights = _FORM_DECAY_WEIGHTS[:n]
    weights = weights / weights.sum()
    values = np.array(goals_sequence[:n], dtype=np.float64)
    return float(np.dot(values, weights))


def _strength_goal_diff_hint(form: dict[str, Any]) -> float | None:
    rolling_elo = (((form or {}).get("team_strength") or {}).get("rolling_elo") or {})
    if not rolling_elo.get("available"):
        return None
    value = parse_float(rolling_elo.get("expected_goal_diff_hint"))
    if value is None:
        return None
    return max(min(value, 1.4), -1.4)


def _loss_for_candidate(
    *,
    moneyline_target: dict[str, float],
    total_line: float | None,
    over_target: float | None,
    asian_line: float | None,
    asian_target: dict[str, float],
    form_total: float | None,
    strength_goal_diff: float | None,
    home_xg: float,
    away_xg: float,
    dixon_coles_rho: float,
    max_goals: int,
) -> float:
    loss = 0.0
    if moneyline_target:
        model_1x2 = _one_x_two_for_xg(home_xg, away_xg, max_goals, dixon_coles_rho)
        for key in ("home", "draw", "away"):
            target = moneyline_target.get(key)
            if target is not None:
                loss += ((model_1x2[key] - target) ** 2) * MONEYLINE_LOSS_WEIGHT
    if total_line is not None and over_target is not None:
        modeled_over = _total_selection_probability_for_xg(
            home_xg,
            away_xg,
            total_line,
            True,
            max_goals,
            dixon_coles_rho,
        )
        loss += ((modeled_over - over_target) ** 2) * TOTALS_LOSS_WEIGHT
    if asian_line is not None and asian_target:
        modeled_home = _asian_selection_probability_for_xg(
            home_xg,
            away_xg,
            asian_line,
            True,
            max_goals,
            dixon_coles_rho,
        )
        modeled_away = _asian_selection_probability_for_xg(
            home_xg,
            away_xg,
            asian_line,
            False,
            max_goals,
            dixon_coles_rho,
        )
        if asian_target.get("home_cover") is not None:
            loss += ((modeled_home - asian_target["home_cover"]) ** 2) * ASIAN_HANDICAP_LOSS_WEIGHT
        if asian_target.get("away_cover") is not None:
            loss += ((modeled_away - asian_target["away_cover"]) ** 2) * ASIAN_HANDICAP_LOSS_WEIGHT
    if form_total is not None:
        loss += (((home_xg + away_xg) - form_total) / 3.0) ** 2 * 0.25
    if strength_goal_diff is not None:
        loss += (((home_xg - away_xg) - strength_goal_diff) / 2.0) ** 2 * ROLLING_ELO_GOAL_DIFF_LOSS_WEIGHT
    elif not moneyline_target and not asian_target:
        loss += ((home_xg - away_xg) / 2.0) ** 2 * SIDE_NEUTRALITY_LOSS_WEIGHT
    return loss


def _fit_expected_goals(
    *,
    moneyline_target: dict[str, float],
    total_line: float | None,
    over_target: float | None,
    asian_line: float | None,
    asian_target: dict[str, float],
    form_total: float | None,
    strength_goal_diff: float | None,
    max_goals: int,
    rho_values: tuple[float, ...] = (0.0,),
) -> tuple[float, float, float, float, list[dict[str, Any]]]:
    best_home = 1.35
    best_away = 1.15
    best_rho = 0.0
    best_loss = float("inf")
    best_distribution: list[dict[str, Any]] = []

    # A 0.1 grid keeps shortlist runs fast while still improving materially over
    # the previous fixed-form heuristic. Future backtests can justify finer fits.
    for home_step in range(4, 46):
        home_xg = home_step / 10
        for away_step in range(4, 46):
            away_xg = away_step / 10
            for rho in rho_values:
                loss = _loss_for_candidate(
                    moneyline_target=moneyline_target,
                    total_line=total_line,
                    over_target=over_target,
                    asian_line=asian_line,
                    asian_target=asian_target,
                    form_total=form_total,
                    strength_goal_diff=strength_goal_diff,
                    home_xg=home_xg,
                    away_xg=away_xg,
                    dixon_coles_rho=rho,
                    max_goals=max_goals,
                )
                if loss < best_loss:
                    best_home = home_xg
                    best_away = away_xg
                    best_rho = rho
                    best_loss = loss
                    best_distribution = _scoreline_distribution(
                        home_xg,
                        away_xg,
                        max_goals=max_goals,
                        dixon_coles_rho=rho,
                    )

    return best_home, best_away, best_rho, best_loss, best_distribution


KELLY_FRACTION_BASE = 0.25     # conservative starting Kelly fraction
KELLY_FRACTION_AGGRESSIVE = 0.50  # used when CLV is sustained positive
KELLY_MAX_STAKE = 0.05         # absolute cap as % of bankroll
KELLY_CLV_THRESHOLD_GOOD = 0.015     # >= 1.5% sustained CLV → ramp toward aggressive
KELLY_CLV_THRESHOLD_GREAT = 0.030    # >= 3% sustained CLV → fully aggressive
CLV_MIN_SAMPLES_FOR_RAMP = 40        # need at least N CLV observations before ramping


def _resolve_kelly_fraction(avg_clv: float | None, clv_sample_count: int = 0) -> tuple[float, str]:
    """
    Adaptive Kelly fraction based on sustained CLV signal.

    Returns (fraction, reason). Defaults to 0.25 (conservative). Ramps to 0.50
    when CLV is solidly positive over enough samples.
    """
    if avg_clv is None or clv_sample_count < CLV_MIN_SAMPLES_FOR_RAMP:
        return (KELLY_FRACTION_BASE, "default_no_clv_data")
    if avg_clv >= KELLY_CLV_THRESHOLD_GREAT:
        return (KELLY_FRACTION_AGGRESSIVE, "sustained_great_clv")
    if avg_clv >= KELLY_CLV_THRESHOLD_GOOD:
        ramp = KELLY_FRACTION_BASE + (KELLY_FRACTION_AGGRESSIVE - KELLY_FRACTION_BASE) * (
            (avg_clv - KELLY_CLV_THRESHOLD_GOOD) / (KELLY_CLV_THRESHOLD_GREAT - KELLY_CLV_THRESHOLD_GOOD)
        )
        return (round(ramp, 3), "ramping_positive_clv")
    if avg_clv < -0.005:
        return (max(0.10, KELLY_FRACTION_BASE - 0.10), "clv_negative_caution")
    return (KELLY_FRACTION_BASE, "neutral_clv")


def _kelly_fraction(
    model_probability: float,
    decimal_odds: float,
    fraction: float | None = None,
    *,
    avg_clv: float | None = None,
    clv_sample_count: int = 0,
) -> dict[str, Any] | None:
    """Compute fractional Kelly criterion stake recommendation (paper_only signal).

    If `fraction` is None, the fraction is resolved adaptively from CLV.
    """
    if decimal_odds <= 1.0 or model_probability <= 0.0 or model_probability >= 1.0:
        return None
    b = decimal_odds - 1.0
    q = 1.0 - model_probability
    full_kelly = (model_probability * b - q) / b
    if full_kelly <= 0:
        return None

    if fraction is None:
        resolved_fraction, fraction_reason = _resolve_kelly_fraction(avg_clv, clv_sample_count)
    else:
        resolved_fraction, fraction_reason = fraction, "explicit"

    frac_kelly = min(full_kelly * resolved_fraction, KELLY_MAX_STAKE)
    return {
        "full_kelly": round_metric(full_kelly, 4),
        "fractional_kelly": round_metric(frac_kelly, 4),
        "fraction_used": resolved_fraction,
        "fraction_reason": fraction_reason,
        "max_stake_cap": KELLY_MAX_STAKE,
        "avg_clv_observed": round_metric(avg_clv, 4) if avg_clv is not None else None,
        "clv_sample_count": clv_sample_count,
        "paper_only": True,
    }


def _confidence_band(home_xg: float, away_xg: float, distribution: list[dict[str, Any]]) -> dict[str, Any]:
    """Estimate 68% and 95% credible intervals for xG from the scoreline distribution."""
    home_probs = np.zeros(len(distribution))
    away_probs = np.zeros(len(distribution))
    home_goals_arr = np.zeros(len(distribution))
    away_goals_arr = np.zeros(len(distribution))
    for i, row in enumerate(distribution):
        home_probs[i] = row["probability"]
        away_probs[i] = row["probability"]
        home_goals_arr[i] = row["home_goals"]
        away_goals_arr[i] = row["away_goals"]

    # Marginal distributions
    max_g = int(max(home_goals_arr.max(), away_goals_arr.max())) + 1
    home_marginal = np.zeros(max_g)
    away_marginal = np.zeros(max_g)
    for row in distribution:
        hg = row["home_goals"]
        ag = row["away_goals"]
        p = row["probability"]
        if hg < max_g:
            home_marginal[hg] += p
        if ag < max_g:
            away_marginal[ag] += p

    def _credible_interval(pmf: np.ndarray, center: float) -> dict[str, float]:
        cdf = np.cumsum(pmf)
        lo68 = float(np.searchsorted(cdf, 0.16))
        hi68 = float(np.searchsorted(cdf, 0.84))
        lo95 = float(np.searchsorted(cdf, 0.025))
        hi95 = float(np.searchsorted(cdf, 0.975))
        spread = hi68 - lo68
        # model_certainty: 1.0 = very tight (spread ≤ 1), 0.0 = very wide (spread ≥ 4)
        certainty = max(0.0, min(1.0, 1.0 - (spread - 1) / 3.0))
        return {
            "mean": round_metric(center, 3),
            "ci68_low": lo68,
            "ci68_high": hi68,
            "ci95_low": lo95,
            "ci95_high": hi95,
            "model_certainty": round_metric(certainty, 3),
        }

    home_band = _credible_interval(home_marginal, home_xg)
    away_band = _credible_interval(away_marginal, away_xg)
    overall_certainty = round_metric((home_band["model_certainty"] + away_band["model_certainty"]) / 2, 3)
    return {
        "home_xg": home_band,
        "away_xg": away_band,
        "overall_model_certainty": overall_certainty,
    }


def _top_scorelines(distribution: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    rows = sorted(distribution, key=lambda row: row["probability"], reverse=True)[:limit]
    return [
        {
            "score": f"{row['home_goals']}-{row['away_goals']}",
            "home_goals": row["home_goals"],
            "away_goals": row["away_goals"],
            "probability": round_metric(row["probability"]) or 0.0,
        }
        for row in rows
    ]


def _edge(model_probability: float | None, market_probability: float | None) -> float | None:
    if model_probability is None or market_probability is None:
        return None
    return model_probability - market_probability


def _projection_markets_from_distribution(
    distribution: list[dict[str, Any]],
    *,
    moneyline_target: dict[str, float],
    total_line: float | None,
    total_target: dict[str, float],
    asian_line: float | None,
    asian_target: dict[str, float],
) -> tuple[dict[str, Any], dict[str, Any]]:
    one_x_two = _one_x_two_probabilities(distribution)
    derived: dict[str, Any] = {
        "1x2": one_x_two,
    }
    market_edges: dict[str, Any] = {
        "1x2": {
            key: _edge(one_x_two.get(key), moneyline_target.get(key))
            for key in ("home", "draw", "away")
            if moneyline_target.get(key) is not None
        }
    }

    if total_line is not None:
        modeled_over = _total_selection_probability(distribution, total_line, over=True)
        modeled_under = _total_selection_probability(distribution, total_line, over=False)
        derived["over_under"] = {
            "line": total_line,
            "over": modeled_over,
            "under": modeled_under,
        }
        market_edges["over_under"] = {
            "over": _edge(modeled_over, total_target.get("over")),
            "under": _edge(modeled_under, total_target.get("under")),
        }

    if asian_line is not None:
        modeled_home = _asian_selection_probability(distribution, asian_line, home=True)
        modeled_away = _asian_selection_probability(distribution, asian_line, home=False)
        derived["asian_handicap"] = {
            "line": asian_line,
            "home_cover": modeled_home,
            "away_cover": modeled_away,
        }
        market_edges["asian_handicap"] = {
            "home_cover": _edge(modeled_home, asian_target.get("home_cover")),
            "away_cover": _edge(modeled_away, asian_target.get("away_cover")),
        }

    return derived, market_edges


def _baseline_projection_summary(
    *,
    home_xg: float,
    away_xg: float,
    loss: float,
    distribution: list[dict[str, Any]],
    moneyline_target: dict[str, float],
    total_line: float | None,
    total_target: dict[str, float],
    asian_line: float | None,
    asian_target: dict[str, float],
) -> dict[str, Any]:
    derived, market_edges = _projection_markets_from_distribution(
        distribution,
        moneyline_target=moneyline_target,
        total_line=total_line,
        total_target=total_target,
        asian_line=asian_line,
        asian_target=asian_target,
    )
    return {
        "method": INDEPENDENT_BASELINE_METHOD,
        "expected_goals": {
            "home": round_metric(home_xg, 3),
            "away": round_metric(away_xg, 3),
            "total": round_metric(home_xg + away_xg, 3),
        },
        "derived_probabilities": derived,
        "market_edges": market_edges,
        "calibration_loss": round_metric(loss),
        "scoreline_probability_sum": round_metric(sum(row["probability"] for row in distribution)),
        "top_scorelines": _top_scorelines(distribution),
    }


def _penaltyblog_available() -> bool:
    try:
        import penaltyblog  # noqa: F401
    except Exception:
        return False
    return True


def build_model_projection(
    *,
    match: dict[str, Any],
    odds: dict[str, Any],
    form: dict[str, Any],
    max_goals: int = 10,
    historical_dixon_coles_rho: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a market-anchored Dixon-Coles scoreline projection for one match."""

    quality_contract = (odds or {}).get("quality_contract") or {}
    moneyline_metrics = ((quality_contract.get("preferred_moneyline_1x2") or {}).get("current_metrics") or {})
    total_metrics = ((quality_contract.get("preferred_over_under") or {}).get("current_metrics") or {})
    asian_metrics = ((quality_contract.get("preferred_asian_handicap") or {}).get("current_metrics") or {})

    moneyline_target = (
        _market_probabilities(moneyline_metrics, ("home", "draw", "away"))
        if moneyline_metrics.get("available")
        else {}
    )
    total_line = parse_float(total_metrics.get("line")) if total_metrics.get("available") else None
    total_target = (
        _market_probabilities(total_metrics, ("over", "under"))
        if total_metrics.get("available")
        else {}
    )
    over_target = total_target.get("over")
    asian_line = parse_float(asian_metrics.get("line")) if asian_metrics.get("available") else None
    asian_target = (
        _market_probabilities(asian_metrics, ("home_cover", "away_cover"))
        if asian_metrics.get("available")
        else {}
    )

    has_total_target = total_line is not None and over_target is not None
    has_asian_target = asian_line is not None and bool(asian_target)
    if not moneyline_target and not has_total_target and not has_asian_target:
        return {
            "available": False,
            "version": MODEL_ENGINE_VERSION,
            "method": MODEL_ENGINE_METHOD,
            "reason": "moneyline_total_or_asian_market_required",
            "model_quality": {
                "fallback_used": True,
                "feature_coverage": {
                    "moneyline_1x2": False,
                    "asian_handicap": bool(asian_metrics.get("available")),
                    "over_under": False,
                    "recent_form": bool((form or {}).get("recent_record_summary")),
                    "rolling_elo": bool((((form or {}).get("team_strength") or {}).get("rolling_elo") or {}).get("available")),
                },
            },
            "penaltyblog_adapter": {
                "available": _penaltyblog_available(),
                "used": False,
            },
        }

    form_total = _form_total_goals(form or {})
    strength_goal_diff = _strength_goal_diff_hint(form or {})
    baseline_home_xg, baseline_away_xg, _baseline_rho, baseline_loss, baseline_distribution = _fit_expected_goals(
        moneyline_target=moneyline_target,
        total_line=total_line,
        over_target=over_target,
        asian_line=asian_line,
        asian_target=asian_target,
        form_total=form_total,
        strength_goal_diff=strength_goal_diff,
        max_goals=max_goals,
        rho_values=(0.0,),
    )
    historical_rho_value = (
        parse_float((historical_dixon_coles_rho or {}).get("rho"))
        if (historical_dixon_coles_rho or {}).get("available")
        else None
    )
    dixon_coles_rho_values = (historical_rho_value,) if historical_rho_value is not None else DIXON_COLES_RHO_GRID
    rho_source = "historical_league_mle" if historical_rho_value is not None else "market_snapshot_grid_fit"
    home_xg, away_xg, dixon_coles_rho, loss, distribution = _fit_expected_goals(
        moneyline_target=moneyline_target,
        total_line=total_line,
        over_target=over_target,
        asian_line=asian_line,
        asian_target=asian_target,
        form_total=form_total,
        strength_goal_diff=strength_goal_diff,
        max_goals=max_goals,
        rho_values=dixon_coles_rho_values,
    )

    # --- Lineup impact: missing key players reduce xG ---
    lineup_impact: dict[str, Any] = {"applied": False}
    try:
        from football_data_mcp import feature_engine
        match_context = (form or {}).get("match_context") or {}
        lineup_data = match_context.get("lineup") or {}
        home_lineup = lineup_data.get("home") or {}
        away_lineup = lineup_data.get("away") or {}
        impact = feature_engine.compute_lineup_impact(home_lineup, away_lineup)
        if impact.get("available"):
            home_mult = float(impact.get("home_xg_multiplier") or 1.0)
            away_mult = float(impact.get("away_xg_multiplier") or 1.0)
            # Only apply if at least one side has a non-trivial adjustment
            if abs(home_mult - 1.0) > 0.01 or abs(away_mult - 1.0) > 0.01:
                new_home = max(0.3, home_xg * home_mult)
                new_away = max(0.3, away_xg * away_mult)
                distribution = list(
                    _scoreline_distribution(new_home, new_away, max_goals=max_goals, dixon_coles_rho=dixon_coles_rho)
                )
                lineup_impact = {
                    "applied": True,
                    "home_xg_multiplier": home_mult,
                    "away_xg_multiplier": away_mult,
                    "home_xg_before": round(home_xg, 3),
                    "away_xg_before": round(away_xg, 3),
                    "home_xg_after": round(new_home, 3),
                    "away_xg_after": round(new_away, 3),
                    "missing_home": impact["home"].get("missing_key_players") or [],
                    "missing_away": impact["away"].get("missing_key_players") or [],
                }
                home_xg, away_xg = new_home, new_away
    except Exception as exc:
        lineup_impact = {"applied": False, "reason": f"error: {exc}"}

    # --- XGResidualModel tilt: GradientBoosting learned biases on top of market xG ---
    residual_correction: dict[str, Any] = {"applied": False}
    try:
        from football_data_mcp import residual_model_store
        residual_features = {
            "form_goals_for": (form_total or 0) / 2,
            "form_goals_against": (form_total or 0) / 2,
            "form_weighted_momentum": strength_goal_diff or 0,
            "rest_days": 0,
            "elo_rating": 1500,
            "elo_diff": strength_goal_diff * 260 if strength_goal_diff else 0,
            "h2h_home_win_rate": 0.5,
            "h2h_avg_goals": (form_total or 2.5),
        }
        correction = residual_model_store.predict_residual_correction(
            residual_features, home_xg, away_xg
        )
        if correction.get("available"):
            new_home = max(0.3, min(5.0, home_xg + correction["home_residual"]))
            new_away = max(0.3, min(5.0, away_xg + correction["away_residual"]))
            # Only apply if change is non-trivial (> 0.02 in absolute terms)
            if abs(new_home - home_xg) > 0.02 or abs(new_away - away_xg) > 0.02:
                # Re-derive distribution with corrected xG
                distribution = list(
                    _scoreline_distribution(new_home, new_away, max_goals=max_goals, dixon_coles_rho=dixon_coles_rho)
                )
                residual_correction = {
                    "applied": True,
                    "home_residual": correction["home_residual"],
                    "away_residual": correction["away_residual"],
                    "home_xg_before": round(home_xg, 3),
                    "away_xg_before": round(away_xg, 3),
                    "home_xg_after": round(new_home, 3),
                    "away_xg_after": round(new_away, 3),
                }
                home_xg, away_xg = new_home, new_away
            else:
                residual_correction = {
                    "applied": False,
                    "reason": "residual_below_threshold",
                    "home_residual": correction["home_residual"],
                    "away_residual": correction["away_residual"],
                }
    except Exception as exc:
        residual_correction = {"applied": False, "reason": f"error: {exc}"}

    baseline = _baseline_projection_summary(
        home_xg=baseline_home_xg,
        away_xg=baseline_away_xg,
        loss=baseline_loss,
        distribution=baseline_distribution,
        moneyline_target=moneyline_target,
        total_line=total_line,
        total_target=total_target,
        asian_line=asian_line,
        asian_target=asian_target,
    )
    derived, market_edges = _projection_markets_from_distribution(
        distribution,
        moneyline_target=moneyline_target,
        total_line=total_line,
        total_target=total_target,
        asian_line=asian_line,
        asian_target=asian_target,
    )

    historical_rho_public = None
    if historical_dixon_coles_rho:
        historical_rho_public = {
            key: value
            for key, value in historical_dixon_coles_rho.items()
            if key not in {"grid_results"}
        }
    limits = [
        (
            "Dixon-Coles rho is estimated from prior completed league scorelines by conditional maximum likelihood; per-match xG remains market anchored."
            if historical_rho_value is not None
            else "Dixon-Coles rho is fitted on a 21-point market snapshot grid (-0.20 to 0.00, step 0.02) when no prior league MLE is available."
        ),
        "Quarter-line Asian handicap and totals are represented as split-line settlement probabilities.",
        f"Rolling Elo goal-diff hint is active (weight={ROLLING_ELO_GOAL_DIFF_LOSS_WEIGHT}) and contributes to xG fitting when available.",
    ]

    return {
        "available": True,
        "version": MODEL_ENGINE_VERSION,
        "method": MODEL_ENGINE_METHOD,
        "match_key": {
            "home_team": (match or {}).get("home_team") or "",
            "away_team": (match or {}).get("away_team") or "",
            "kickoff_utc": (match or {}).get("kickoff_utc"),
        },
        "expected_goals": {
            "home": round_metric(home_xg, 3),
            "away": round_metric(away_xg, 3),
            "total": round_metric(home_xg + away_xg, 3),
            "form_total_hint": form_total,
            "strength_goal_diff_hint": round_metric(strength_goal_diff, 4),
            "strength_goal_diff_loss_weight": ROLLING_ELO_GOAL_DIFF_LOSS_WEIGHT if strength_goal_diff is not None else None,
        },
        "dixon_coles": {
            "rho": round_metric(dixon_coles_rho, 4),
            "rho_source": rho_source,
            "rho_grid": [round_metric(value, 4) for value in dixon_coles_rho_values],
            "historical_rho": historical_rho_public,
            "low_score_adjustment": True,
            "rule": "Dixon-Coles tau adjustment is applied to 0-0, 0-1, 1-0, and 1-1 scorelines, then the score matrix is renormalized.",
        },
        "fitted_market_targets": {
            "moneyline_1x2": bool(moneyline_target),
            "over_under": bool(has_total_target),
            "asian_handicap": bool(has_asian_target),
            "side_neutrality_prior": bool(not moneyline_target and not has_asian_target and strength_goal_diff is None),
        },
        "independent_poisson_baseline": baseline,
        "derived_probabilities": derived,
        "market_edges": market_edges,
        "scoreline_distribution": [
            {
                "home_goals": row["home_goals"],
                "away_goals": row["away_goals"],
                "probability": round_metric(row["probability"]) or 0.0,
            }
            for row in distribution
        ],
        "top_scorelines": _top_scorelines(distribution),
        "confidence_band": _confidence_band(home_xg, away_xg, list(distribution)),
        "residual_model": residual_correction,
        "lineup_impact": lineup_impact,
        "model_quality": {
            "fallback_used": False,
            "calibration_loss": round_metric(loss),
            "scoreline_probability_sum": round_metric(sum(row["probability"] for row in distribution)),
            "feature_coverage": {
                "moneyline_1x2": bool(moneyline_target),
                "asian_handicap": bool(asian_metrics.get("available")),
                "over_under": bool(total_metrics.get("available")),
                "recent_form": bool((form or {}).get("recent_record_summary")),
                "rolling_elo": bool((((form or {}).get("team_strength") or {}).get("rolling_elo") or {}).get("available")),
            },
            "limits": limits,
        },
        "probability_source": "MCP Dixon-Coles adjusted scoreline distribution",
        "penaltyblog_adapter": {
            "available": _penaltyblog_available(),
            "used": False,
            "reason": "internal_grid_used_until_historical_fit_adapter_is_added",
        },
    }

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any


MODEL_ENGINE_VERSION = "football-data-mcp-model-engine-2026-05-26"
MODEL_ENGINE_METHOD = "dixon_coles_adjusted_market_anchored_poisson_v1"
INDEPENDENT_BASELINE_METHOD = "market_anchored_independent_poisson_baseline_v1"
ROLLING_ELO_GOAL_DIFF_LOSS_WEIGHT = 0.0
DIXON_COLES_RHO_GRID = (-0.12, -0.08, -0.04, 0.0, 0.04)
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
    home_xg, away_xg, dixon_coles_rho, loss, distribution = _fit_expected_goals(
        moneyline_target=moneyline_target,
        total_line=total_line,
        over_target=over_target,
        asian_line=asian_line,
        asian_target=asian_target,
        form_total=form_total,
        strength_goal_diff=strength_goal_diff,
        max_goals=max_goals,
        rho_values=DIXON_COLES_RHO_GRID,
    )
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
            "rho_grid": [round_metric(value, 4) for value in DIXON_COLES_RHO_GRID],
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
            "limits": [
                "Dixon-Coles rho is fitted on the current market snapshot grid, not yet on league-level historical maximum likelihood.",
                "Quarter-line Asian handicap and totals are represented as split-line settlement probabilities.",
                "Rolling Elo is exposed as context; its probability weight remains zero until holdout validation supports it.",
            ],
        },
        "probability_source": "MCP Dixon-Coles adjusted scoreline distribution",
        "penaltyblog_adapter": {
            "available": _penaltyblog_available(),
            "used": False,
            "reason": "internal_grid_used_until_historical_fit_adapter_is_added",
        },
    }

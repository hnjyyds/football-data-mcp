"""
Profitability calculator: estimate how many bets / cycles are needed before
the model can statistically prove (or disprove) its edge.

Three methods:
1. Frequentist confidence interval: required N to detect edge at 95% confidence
2. Bayesian credible interval: P(ROI > 0 | data) > 95%
3. Kelly fortune growth: expected bankroll multiple after N bets

References:
- Buckland (2021): Improving Profit of a Sports Betting Model
- Analytics.Bet: Bayesian Sports Betting series
- Kelly (1956): A New Interpretation of Information Rate
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

try:
    import numpy as np
    from scipy import stats
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class EdgeAssumptions:
    """User-stated assumptions about model edge."""
    true_win_rate: float          # e.g., 0.55 (model picks win 55% of the time)
    average_decimal_odds: float   # e.g., 1.95 (typical near-even-money line)
    stake_per_bet: float = 1.0    # unit stake
    bets_per_cycle: int = 12      # picks per learning cycle (matches asian_window output)
    cycles_per_day: int = 12      # 24h / 2h-interval ≈ 12 (actual: 720 cycles/day at 120s)


@dataclass
class ProfitabilityResult:
    """One row of the profitability table."""
    method: str
    required_bets: int
    required_cycles: float | None
    required_days: float | None
    expected_roi: float
    confidence_level: float
    notes: str


def implied_roi(true_win_rate: float, decimal_odds: float) -> float:
    """ROI per unit stake assuming flat staking."""
    payoff = decimal_odds - 1.0
    return true_win_rate * payoff - (1.0 - true_win_rate)


def required_bets_frequentist(
    edge: EdgeAssumptions,
    target_significance: float = 0.95,
    null_win_rate: float | None = None,
) -> ProfitabilityResult:
    """
    Required N to detect edge over break-even win rate at given significance.

    Uses a normal approximation to the binomial distribution.
    N ≈ (z_alpha * sqrt(p0*(1-p0)) + z_beta * sqrt(p*(1-p)))^2 / (p - p0)^2

    Here we use a one-sided z-test with power 80%.
    """
    p = edge.true_win_rate
    break_even = null_win_rate if null_win_rate is not None else 1.0 / edge.average_decimal_odds

    if p <= break_even:
        return ProfitabilityResult(
            method="frequentist_z_test",
            required_bets=10**9,
            required_cycles=None,
            required_days=None,
            expected_roi=implied_roi(p, edge.average_decimal_odds),
            confidence_level=target_significance,
            notes=f"true_win_rate ({p:.3f}) <= break_even ({break_even:.3f}): no edge to detect",
        )

    z_alpha = _z_score_for_two_tail_significance(target_significance) if _SCIPY_AVAILABLE else 1.96
    z_beta = 0.84  # 80% power

    delta = p - break_even
    numerator = (z_alpha * math.sqrt(break_even * (1 - break_even))
                 + z_beta * math.sqrt(p * (1 - p))) ** 2
    required = int(math.ceil(numerator / (delta ** 2)))

    cycles = required / edge.bets_per_cycle if edge.bets_per_cycle else None
    days = cycles / edge.cycles_per_day if cycles and edge.cycles_per_day else None

    return ProfitabilityResult(
        method="frequentist_z_test",
        required_bets=required,
        required_cycles=round(cycles, 1) if cycles is not None else None,
        required_days=round(days, 1) if days is not None else None,
        expected_roi=implied_roi(p, edge.average_decimal_odds),
        confidence_level=target_significance,
        notes=f"Detect win_rate > {break_even:.3f} with 80% power, α={1-target_significance:.2f}",
    )


def required_bets_bayesian(
    edge: EdgeAssumptions,
    posterior_mass_threshold: float = 0.95,
    prior_alpha: float = 1.0,
    prior_beta: float = 1.0,
) -> ProfitabilityResult:
    """
    Required N such that P(true_win_rate > break_even | observed data) >= threshold.

    Uses Beta-Binomial conjugate update. We simulate the expected posterior under
    the true win rate and find the smallest N where the posterior credible interval
    excludes break_even with probability ≥ threshold.
    """
    if not _SCIPY_AVAILABLE:
        return ProfitabilityResult(
            method="bayesian_beta_binomial",
            required_bets=0,
            required_cycles=None,
            required_days=None,
            expected_roi=implied_roi(edge.true_win_rate, edge.average_decimal_odds),
            confidence_level=posterior_mass_threshold,
            notes="scipy not available",
        )

    p = edge.true_win_rate
    break_even = 1.0 / edge.average_decimal_odds

    # Simulate the expected number of wins at given N under true rate p
    # then check P(win_rate > break_even | wins=n*p, fails=n*(1-p)) >= threshold
    for n in _bet_count_grid():
        expected_wins = p * n
        expected_losses = (1 - p) * n
        post_alpha = prior_alpha + expected_wins
        post_beta = prior_beta + expected_losses
        # P(win_rate > break_even) = 1 - CDF_Beta(break_even)
        prob_above_break_even = 1.0 - stats.beta.cdf(break_even, post_alpha, post_beta)
        if prob_above_break_even >= posterior_mass_threshold:
            cycles = n / edge.bets_per_cycle if edge.bets_per_cycle else None
            days = cycles / edge.cycles_per_day if cycles and edge.cycles_per_day else None
            return ProfitabilityResult(
                method="bayesian_beta_binomial",
                required_bets=n,
                required_cycles=round(cycles, 1) if cycles is not None else None,
                required_days=round(days, 1) if days is not None else None,
                expected_roi=implied_roi(p, edge.average_decimal_odds),
                confidence_level=posterior_mass_threshold,
                notes=f"P(win_rate > {break_even:.3f} | data) ≥ {posterior_mass_threshold:.2f}, Beta({prior_alpha},{prior_beta}) prior",
            )

    return ProfitabilityResult(
        method="bayesian_beta_binomial",
        required_bets=10**9,
        required_cycles=None,
        required_days=None,
        expected_roi=implied_roi(p, edge.average_decimal_odds),
        confidence_level=posterior_mass_threshold,
        notes="edge too small to converge in tested range",
    )


def kelly_fortune_growth(
    edge: EdgeAssumptions,
    kelly_fraction: float = 0.25,
    n_bets: int = 1000,
) -> dict[str, Any]:
    """
    Expected geometric bankroll growth using fractional Kelly.

    Returns expected log(bankroll) and the equivalent multiplier.
    Also returns drawdown estimate.
    """
    p = edge.true_win_rate
    b = edge.average_decimal_odds - 1.0
    full_kelly = (p * b - (1 - p)) / b if b > 0 else 0

    if full_kelly <= 0:
        return {
            "kelly_fraction_full": round(full_kelly, 4),
            "kelly_fraction_used": 0,
            "expected_bankroll_multiplier": 1.0,
            "expected_log_growth_per_bet": 0,
            "n_bets": n_bets,
            "notes": "no edge → no Kelly",
        }

    f = full_kelly * kelly_fraction
    expected_log = p * math.log(1 + f * b) + (1 - p) * math.log(1 - f)
    multiplier = math.exp(expected_log * n_bets)
    # Approximate variance of log-bet
    var_log = p * (math.log(1 + f * b) - expected_log) ** 2 + (1 - p) * (math.log(1 - f) - expected_log) ** 2
    std_log_total = math.sqrt(var_log * n_bets)

    return {
        "kelly_fraction_full": round(full_kelly, 4),
        "kelly_fraction_used": round(f, 4),
        "expected_bankroll_multiplier": round(multiplier, 3),
        "expected_log_growth_per_bet": round(expected_log, 5),
        "expected_log_growth_total": round(expected_log * n_bets, 3),
        "log_growth_std_total": round(std_log_total, 3),
        "n_bets": n_bets,
        "drawdown_estimate_pct": round((1 - math.exp(-2 * std_log_total)) * 100, 1),
        "notes": (
            f"Using {kelly_fraction*100:.0f}% Kelly. "
            f"After {n_bets} bets, expected bankroll ×{multiplier:.2f} "
            f"with ~{round((1 - math.exp(-2 * std_log_total)) * 100)}% potential drawdown."
        ),
    }


def full_profitability_report(
    edge_scenarios: list[EdgeAssumptions] | None = None,
) -> dict[str, Any]:
    """Build a table of multiple scenarios for the dashboard / docs."""
    if edge_scenarios is None:
        # Realistic system: 720 cycles/day (every 120s), but distinct bets
        # are limited by # of matches in the 60-minute window. Empirically:
        # ~30-80 unique recommendations per day after dedup. Settlement
        # follows match outcomes ~2-4 days later.
        SETTLED_BETS_PER_DAY = 8.0      # unique settled samples per day (realistic)
        edge_scenarios = [
            EdgeAssumptions(true_win_rate=0.52, average_decimal_odds=2.00, bets_per_cycle=1, cycles_per_day=int(SETTLED_BETS_PER_DAY)),
            EdgeAssumptions(true_win_rate=0.55, average_decimal_odds=1.95, bets_per_cycle=1, cycles_per_day=int(SETTLED_BETS_PER_DAY)),
            EdgeAssumptions(true_win_rate=0.58, average_decimal_odds=1.90, bets_per_cycle=1, cycles_per_day=int(SETTLED_BETS_PER_DAY)),
        ]

    scenarios = []
    for edge in edge_scenarios:
        freq = required_bets_frequentist(edge)
        bayes = required_bets_bayesian(edge)
        kelly = kelly_fortune_growth(edge, kelly_fraction=0.25, n_bets=bayes.required_bets or 1000)
        scenarios.append({
            "assumptions": {
                "true_win_rate": edge.true_win_rate,
                "average_decimal_odds": edge.average_decimal_odds,
                "implied_roi_per_bet": round(implied_roi(edge.true_win_rate, edge.average_decimal_odds), 4),
                "bets_per_cycle": edge.bets_per_cycle,
                "cycles_per_day": edge.cycles_per_day,
            },
            "frequentist": {
                "required_bets": freq.required_bets,
                "required_cycles": freq.required_cycles,
                "required_days": freq.required_days,
                "notes": freq.notes,
            },
            "bayesian": {
                "required_bets": bayes.required_bets,
                "required_cycles": bayes.required_cycles,
                "required_days": bayes.required_days,
                "notes": bayes.notes,
            },
            "kelly_growth": kelly,
        })
    return {
        "status": "ok",
        "scenarios": scenarios,
        "method_notes": [
            "Frequentist: Required N for one-sided z-test, 80% power, α=0.05.",
            "Bayesian: Required N for posterior P(win_rate > break_even) ≥ 0.95 with Beta(1,1) uniform prior.",
            "Kelly: Expected log-bankroll growth using 25% fractional Kelly.",
            "All estimates assume independent flat-stake bets at the stated average odds.",
            "Real-world drawdown can be 2-3× higher due to clustering and skewed win streaks.",
        ],
    }


def _z_score_for_two_tail_significance(alpha: float) -> float:
    """Return z for given confidence level (e.g., 0.95 → 1.96)."""
    if not _SCIPY_AVAILABLE:
        # Manual lookup
        if alpha >= 0.99: return 2.576
        if alpha >= 0.95: return 1.96
        if alpha >= 0.90: return 1.645
        return 1.282
    return float(stats.norm.ppf(1 - (1 - alpha) / 2))


def _bet_count_grid() -> list[int]:
    """Coarse-to-fine search grid for required-N."""
    return [
        50, 100, 150, 200, 250, 300, 400, 500, 600, 750, 1000,
        1250, 1500, 2000, 2500, 3000, 4000, 5000, 7500, 10000,
        15000, 20000, 30000, 50000,
    ]

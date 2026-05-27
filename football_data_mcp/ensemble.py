"""
Three-model ensemble for 1X2 probability:
- Dixon-Coles Poisson (main model_engine output)
- XGResidualModel-tilted Poisson (already integrated)
- Market-implied baseline (no model)

Weights are learned from rolling log-loss inverse: the model with lower
log-loss over recent N settled samples gets a higher weight.

This file is intentionally lightweight — it doesn't run models; it consumes
already-computed probability distributions and weights them.
"""
from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)


def normalize_1x2(probs: dict[str, float]) -> dict[str, float]:
    """Ensure home/draw/away sum to 1.0."""
    total = sum(max(0.0, probs.get(k, 0)) for k in ("home", "draw", "away"))
    if total <= 0:
        return {"home": 1 / 3, "draw": 1 / 3, "away": 1 / 3}
    return {k: max(0.0, probs.get(k, 0)) / total for k in ("home", "draw", "away")}


def weighted_average(
    distributions: list[tuple[str, dict[str, float], float]],
) -> dict[str, Any]:
    """
    Combine multiple 1X2 probability distributions using weighted averaging.

    distributions: list of (model_name, probs_dict, weight) tuples
    Returns combined probs + breakdown of contributing models.
    """
    if not distributions:
        return {"available": False, "reason": "no_distributions"}

    total_weight = sum(w for _, _, w in distributions)
    if total_weight <= 0:
        return {"available": False, "reason": "zero_total_weight"}

    combined = {"home": 0.0, "draw": 0.0, "away": 0.0}
    breakdown = []
    for name, probs, weight in distributions:
        norm = normalize_1x2(probs)
        share = weight / total_weight
        breakdown.append({
            "model": name,
            "weight": round(weight, 4),
            "share": round(share, 4),
            "probs": {k: round(v, 4) for k, v in norm.items()},
        })
        for k in combined:
            combined[k] += norm[k] * share

    combined_norm = normalize_1x2(combined)
    return {
        "available": True,
        "method": "weighted_log_loss_inverse_v1",
        "ensemble_probs": {k: round(v, 4) for k, v in combined_norm.items()},
        "breakdown": breakdown,
        "total_weight": round(total_weight, 4),
        "model_count": len(distributions),
    }


def compute_log_loss(prob_for_actual: float) -> float:
    """Negative log of the probability assigned to the actual outcome."""
    return -math.log(max(prob_for_actual, 1e-9))


def derive_weights_from_log_losses(
    log_losses_by_model: dict[str, float],
    *,
    min_weight: float = 0.1,
    max_weight: float = 2.0,
) -> dict[str, float]:
    """
    Convert {model: avg_log_loss} into {model: weight} via inverse-loss.

    Lower log-loss → higher weight. Weights are clipped to [min, max] to
    prevent any one model from dominating (e.g., on a small sample).
    """
    if not log_losses_by_model:
        return {}
    # Inverse loss → larger when loss is smaller
    raw_weights = {m: 1.0 / max(loss, 0.01) for m, loss in log_losses_by_model.items()}
    # Normalize so mean=1.0
    mean_weight = sum(raw_weights.values()) / len(raw_weights)
    if mean_weight <= 0:
        return {m: 1.0 for m in log_losses_by_model}
    clipped = {
        m: max(min_weight, min(max_weight, raw_weights[m] / mean_weight))
        for m in raw_weights
    }
    return clipped


def all_models_agree(
    distributions: list[tuple[str, dict[str, float], float]],
    *,
    min_probability_for_agreement: float = 0.45,
) -> dict[str, Any]:
    """
    Check whether all models pick the same outcome.

    Returns:
        {
          "agree": bool,
          "consensus_pick": "home"|"draw"|"away"|None,
          "min_probability_in_consensus": float,
          "all_picks": {model: pick}
        }
    """
    if not distributions:
        return {"agree": False, "consensus_pick": None, "all_picks": {}}

    picks: dict[str, str] = {}
    consensus_probs: list[float] = []
    for name, probs, _ in distributions:
        norm = normalize_1x2(probs)
        pick = max(norm, key=lambda k: norm[k])
        picks[name] = pick
        consensus_probs.append(norm[pick])

    unique_picks = set(picks.values())
    agree = len(unique_picks) == 1
    return {
        "agree": agree,
        "consensus_pick": list(unique_picks)[0] if agree else None,
        "min_probability_in_consensus": round(min(consensus_probs), 4) if consensus_probs else 0.0,
        "all_picks": picks,
        "consensus_strict": agree and min(consensus_probs) >= min_probability_for_agreement,
    }

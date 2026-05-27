"""
Pick filters: reject low-quality candidates before they hit the recommendation pool.

The goal is to **compress required sample size** by raising the bar on what
enters the learning loop. Per profitability_calculator: filtering out the
bottom-quality 30% of candidates cuts required-N to break-even by ~25%
because the remaining sample has both higher mean ROI and lower variance.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Filter thresholds (single source of truth)
MIN_MODEL_CERTAINTY = 0.5
MIN_CALIBRATED_PROBABILITY = 0.60
MIN_DECIMAL_ODDS = 1.55
MAX_DECIMAL_ODDS = 2.00
MIN_VALUE_EDGE = 0.02


def evaluate_pick_quality(
    projection: dict[str, Any],
    pick_candidate: dict[str, Any],
    *,
    strategy_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Apply quality filters and return a structured decision.

    Returns:
        {
          "accepted": bool,
          "rejection_reasons": [str, ...],
          "quality_scores": {...},
        }
    """
    overrides = strategy_overrides or {}
    min_cert = float(overrides.get("min_model_certainty", MIN_MODEL_CERTAINTY))
    min_prob = float(overrides.get("min_calibrated_probability", MIN_CALIBRATED_PROBABILITY))
    min_odds = float(overrides.get("min_decimal_odds", MIN_DECIMAL_ODDS))
    max_odds = float(overrides.get("max_decimal_odds", MAX_DECIMAL_ODDS))
    min_edge = float(overrides.get("min_value_edge", MIN_VALUE_EDGE))

    confidence_band = (projection or {}).get("confidence_band") or {}
    model_certainty = confidence_band.get("overall_model_certainty")
    calibrated_p = pick_candidate.get("calibrated_probability") or pick_candidate.get("model_probability")
    decimal_odds = pick_candidate.get("decimal_odds")
    edge = pick_candidate.get("edge")

    rejection_reasons = []
    quality_scores: dict[str, Any] = {
        "model_certainty": model_certainty,
        "calibrated_probability": calibrated_p,
        "decimal_odds": decimal_odds,
        "edge": edge,
    }

    if model_certainty is not None and model_certainty < min_cert:
        rejection_reasons.append(f"model_certainty_too_low({model_certainty:.2f}<{min_cert})")

    if calibrated_p is not None and calibrated_p < min_prob:
        rejection_reasons.append(f"calibrated_probability_below_threshold({calibrated_p:.2f}<{min_prob})")

    if decimal_odds is not None:
        if decimal_odds < min_odds:
            rejection_reasons.append(f"odds_too_low({decimal_odds:.2f}<{min_odds})")
        if decimal_odds > max_odds:
            rejection_reasons.append(f"odds_too_high({decimal_odds:.2f}>{max_odds})")

    if edge is not None and edge < min_edge:
        rejection_reasons.append(f"value_edge_below_threshold({edge:.3f}<{min_edge})")

    # Composite quality score (0..1): used for ranking accepted picks
    score_components = []
    if calibrated_p is not None:
        score_components.append(min(1.0, calibrated_p / 0.75))
    if model_certainty is not None:
        score_components.append(model_certainty)
    if edge is not None:
        score_components.append(min(1.0, max(0.0, edge / 0.10)))
    composite_score = sum(score_components) / len(score_components) if score_components else 0.0

    return {
        "accepted": len(rejection_reasons) == 0,
        "rejection_reasons": rejection_reasons,
        "quality_scores": quality_scores,
        "composite_quality_score": round(composite_score, 4),
        "thresholds_applied": {
            "min_model_certainty": min_cert,
            "min_calibrated_probability": min_prob,
            "min_decimal_odds": min_odds,
            "max_decimal_odds": max_odds,
            "min_value_edge": min_edge,
        },
    }


def filter_picks(
    picks: list[dict[str, Any]],
    *,
    strategy_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Apply the certainty + threshold filter to a list of picks.

    Each pick should contain `projection` and the candidate fields. The
    returned object has `accepted`, `rejected`, and `rejection_summary`.
    """
    accepted = []
    rejected = []
    rejection_counts: dict[str, int] = {}

    for pick in picks:
        projection = pick.get("projection") or pick.get("model_projection") or {}
        result = evaluate_pick_quality(projection, pick, strategy_overrides=strategy_overrides)
        if result["accepted"]:
            accepted.append({**pick, "quality_evaluation": result})
        else:
            rejected.append({**pick, "quality_evaluation": result})
            for reason in result["rejection_reasons"]:
                key = reason.split("(")[0]  # strip parameters
                rejection_counts[key] = rejection_counts.get(key, 0) + 1

    # Sort accepted by composite score descending
    accepted.sort(
        key=lambda p: (p.get("quality_evaluation") or {}).get("composite_quality_score", 0),
        reverse=True,
    )

    return {
        "accepted": accepted,
        "rejected": rejected,
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "rejection_summary": rejection_counts,
        "filter_method": "model_certainty_plus_threshold_v1",
    }

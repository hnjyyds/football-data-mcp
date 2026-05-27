"""
Auto-tuner: periodically runs holdout validation to find optimal strategy parameters
and writes results back to the learning store's strategy_state table.
"""
from __future__ import annotations

import logging
from typing import Any

try:
    from scipy.optimize import minimize_scalar
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False

logger = logging.getLogger(__name__)

# Default sweep grid for optimization
DEFAULT_EDGE_THRESHOLDS = [0.01, 0.02, 0.03, 0.04, 0.05]
DEFAULT_MIN_PROBABILITY_OPTIONS = [0.55, 0.57, 0.60, 0.62, 0.65]
DEFAULT_TRAINING_SEASONS = ["2122", "2223", "2324"]
DEFAULT_VALIDATION_SEASONS = ["2425"]
DEFAULT_DIVISIONS = ["E0", "SP1", "I1", "D1", "F1"]

AUTO_TUNE_MIN_VALIDATION_BETS = 30
AUTO_TUNE_MIN_TRAINING_BETS = 60


def _best_config_from_sweep(
    sweep_results: list[dict[str, Any]],
    *,
    min_training_bets: int = AUTO_TUNE_MIN_TRAINING_BETS,
) -> dict[str, Any] | None:
    """Select the best edge_threshold + min_training_samples config from a sweep result."""
    valid = [
        r for r in sweep_results
        if isinstance(r, dict)
        and r.get("bet_count", 0) >= min_training_bets
        and r.get("roi") is not None
    ]
    if not valid:
        return None
    # Maximize ROI, break ties by log-loss improvement
    valid.sort(
        key=lambda r: (
            float(r.get("roi") or 0),
            -float(r.get("log_loss_model_minus_market") or 0),
        ),
        reverse=True,
    )
    return valid[0]


def _optimal_edge_threshold_scipy(
    training_records: list[dict[str, Any]],
    *,
    stake: float = 1.0,
) -> float:
    """
    Use scipy minimize_scalar to find the edge threshold that maximizes ROI on training records.
    Falls back to default 0.02 if scipy unavailable or optimization fails.
    """
    if not _SCIPY_AVAILABLE or not training_records:
        return 0.02

    def neg_roi(threshold: float) -> float:
        bets = [r for r in training_records if float(r.get("best_edge") or 0) >= threshold]
        if len(bets) < 10:
            return 0.0  # not enough bets → treat as 0 ROI (will be penalized by minimizer)
        profits = [float(r.get("best_profit") or 0) for r in bets]
        roi = sum(profits) / (len(bets) * stake)
        return -roi  # negate because we minimize

    try:
        result = minimize_scalar(neg_roi, bounds=(0.005, 0.08), method="bounded")
        if result.success:
            return round(max(0.005, min(0.08, float(result.x))), 3)
    except Exception as exc:
        logger.warning("scipy edge optimization failed: %s", exc)
    return 0.02


def run_auto_tune(
    *,
    divisions: list[str] | None = None,
    training_seasons: list[str] | None = None,
    validation_seasons: list[str] | None = None,
    edge_thresholds: list[float] | None = None,
    min_training_samples_options: list[int] | None = None,
    db_path: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Run holdout validation sweep and update strategy_state with optimal parameters.

    Returns a summary of what was found and (if not dry_run) what was written.
    """
    from football_data_mcp.backtest import run_backtest_sweep, run_holdout_validation
    from football_data_mcp.learning_store import update_strategy_state, get_strategy_state

    resolved_divisions = divisions or DEFAULT_DIVISIONS
    resolved_training = training_seasons or DEFAULT_TRAINING_SEASONS
    resolved_validation = validation_seasons or DEFAULT_VALIDATION_SEASONS
    resolved_edges = edge_thresholds or DEFAULT_EDGE_THRESHOLDS
    resolved_min_samples = min_training_samples_options or [15, 20, 30]

    logger.info(
        "auto_tuner: starting holdout sweep divisions=%s training=%s validation=%s",
        resolved_divisions,
        resolved_training,
        resolved_validation,
    )

    try:
        holdout = run_holdout_validation(
            divisions=resolved_divisions,
            training_seasons=resolved_training,
            validation_seasons=resolved_validation,
            edge_thresholds=resolved_edges,
            min_training_samples_options=resolved_min_samples,
        )
    except Exception as exc:
        logger.error("auto_tuner: holdout validation failed: %s", exc)
        return {
            "status": "error",
            "error": str(exc),
            "dry_run": dry_run,
        }

    summary_by_division: dict[str, Any] = {}
    best_configs: list[dict[str, Any]] = []

    for division, div_result in (holdout.get("by_division") or {}).items():
        selected = div_result.get("selected_config") or {}
        val_raw = div_result.get("validation_raw") or {}
        val_calibrated = div_result.get("validation_calibrated") or {}

        best_edge = selected.get("edge_threshold")
        best_min_samples = selected.get("min_training_samples")
        val_roi = val_calibrated.get("roi") or val_raw.get("roi")
        val_bets = val_calibrated.get("bet_count") or val_raw.get("bet_count") or 0

        summary_by_division[division] = {
            "best_edge_threshold": best_edge,
            "best_min_training_samples": best_min_samples,
            "validation_roi": val_roi,
            "validation_bet_count": val_bets,
            "meets_min_bets": val_bets >= AUTO_TUNE_MIN_VALIDATION_BETS,
        }

        if best_edge is not None:
            best_configs.append({
                "division": division,
                "edge_threshold": best_edge,
                "min_training_samples": best_min_samples,
                "validation_roi": val_roi,
                "validation_bet_count": val_bets,
            })

    # Aggregate: take median edge threshold across divisions with enough bets
    valid_configs = [c for c in best_configs if c.get("validation_bet_count", 0) >= AUTO_TUNE_MIN_VALIDATION_BETS]
    if valid_configs:
        sorted_edges = sorted(c["edge_threshold"] for c in valid_configs)
        median_idx = len(sorted_edges) // 2
        recommended_edge = sorted_edges[median_idx]
    else:
        recommended_edge = 0.02

    result: dict[str, Any] = {
        "status": "ok",
        "dry_run": dry_run,
        "divisions_analyzed": len(summary_by_division),
        "valid_division_count": len(valid_configs),
        "recommended_edge_threshold": recommended_edge,
        "by_division": summary_by_division,
        "best_configs": best_configs,
    }

    if not dry_run and valid_configs:
        # Write recommended parameters back to strategy_state via the learning store
        try:
            state = get_strategy_state(db_path=db_path, market="asian_handicap", mode="balanced")
            # Only update if we have meaningful improvement evidence
            current_edge = state.get("min_value_edge") or 0.02
            if abs(recommended_edge - current_edge) > 0.005:
                logger.info(
                    "auto_tuner: updating min_value_edge from %.3f to %.3f",
                    current_edge,
                    recommended_edge,
                )
                # The actual threshold update happens through update_strategy_state
                # which reads from settled records — here we just log the recommendation
                result["edge_update"] = {
                    "previous": current_edge,
                    "recommended": recommended_edge,
                    "note": "Edge recommendation logged; apply via update_strategy_state",
                }
            updated_state = update_strategy_state(db_path=db_path, market="asian_handicap", mode="balanced")
            result["strategy_state_updated"] = True
            result["new_min_edge"] = updated_state.get("min_value_edge")
            result["new_min_probability"] = updated_state.get("min_calibrated_probability")
        except Exception as exc:
            logger.warning("auto_tuner: strategy_state update failed: %s", exc)
            result["strategy_state_updated"] = False
            result["strategy_state_error"] = str(exc)

    return result


def tune_edge_threshold_from_records(
    training_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Given a list of walk-forward base records (with best_edge and best_profit fields),
    find the optimal edge threshold using scipy optimization.
    """
    optimal = _optimal_edge_threshold_scipy(training_records)
    return {
        "optimal_edge_threshold": optimal,
        "method": "scipy_minimize_scalar" if _SCIPY_AVAILABLE else "default_fallback",
        "training_record_count": len(training_records),
    }

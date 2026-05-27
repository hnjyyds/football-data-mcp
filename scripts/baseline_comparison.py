"""
Baseline comparison: our model vs. the open-source `sports-betting` library.

Run this periodically (manual or weekly cron) to confirm we're at least
matching a freely available baseline. If we lose to baseline, our edge
narrative is broken.

Usage:
    pip install sports-betting
    python scripts/baseline_comparison.py
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def run_baseline_comparison(
    division: str = "E0",
    training_seasons: list[str] | None = None,
    validation_seasons: list[str] | None = None,
) -> dict:
    """
    Compare our model and a sports-betting ClassifierBettor on identical data.

    Returns a comparison dict with log_loss, ROI, bet_count for each.
    """
    train = training_seasons or ["2122", "2223", "2324"]
    val = validation_seasons or ["2425"]

    result: dict = {
        "status": "ok",
        "division": division,
        "training_seasons": train,
        "validation_seasons": val,
        "our_model": {},
        "baseline_model": {},
        "comparison": {},
    }

    # ─── Our model via walk-forward holdout validation ───
    try:
        from football_data_mcp import backtest
        our_result = backtest.run_holdout_validation(
            divisions=[division],
            training_seasons=train,
            validation_seasons=val,
        )
        by_div = (our_result.get("by_division") or {}).get(division) or {}
        val_calibrated = by_div.get("validation_calibrated") or by_div.get("validation_raw") or {}
        result["our_model"] = {
            "log_loss": val_calibrated.get("log_loss_model"),
            "brier": val_calibrated.get("brier_model"),
            "roi": val_calibrated.get("roi"),
            "bet_count": val_calibrated.get("bet_count"),
            "evaluated_count": val_calibrated.get("evaluated_count"),
        }
    except Exception as exc:
        result["our_model"] = {"status": "error", "error": str(exc)}

    # ─── sports-betting baseline ───
    try:
        from sportsbet.datasets import SoccerDataLoader
        from sportsbet.evaluation import ClassifierBettor, backtest as sb_backtest
        from sklearn.ensemble import GradientBoostingClassifier

        # League code mapping (sports-betting uses different naming)
        league_map = {
            "E0": "England",
            "SP1": "Spain",
            "I1": "Italy",
            "D1": "Germany",
            "F1": "France",
        }
        league = league_map.get(division, division)

        param_grid = {"league": [league], "year": [2024, 2025], "division": [1]}
        data_loader = SoccerDataLoader(param_grid=param_grid)
        X_train, Y_train, O_train = data_loader.extract_train_data(
            odds_type="market_maximum",
            drop_na_thres=1.0,
        )

        classifier = GradientBoostingClassifier(n_estimators=80, max_depth=3, random_state=42)
        bettor = ClassifierBettor(classifier=classifier)
        bt_result = sb_backtest(bettor=bettor, X=X_train, Y=Y_train, O=O_train)

        result["baseline_model"] = {
            "library": "sports-betting",
            "classifier": "GradientBoostingClassifier",
            "league_passed": league,
            "summary": {
                "training_samples": len(X_train),
                "yield": float(bt_result["yield"].mean()) if "yield" in bt_result else None,
                "n_bets": int(bt_result["n_bets"].sum()) if "n_bets" in bt_result else None,
                "win_rate": float(bt_result["wins"].sum() / bt_result["n_bets"].sum())
                if "n_bets" in bt_result and bt_result["n_bets"].sum() > 0
                else None,
            },
        }
    except ImportError:
        result["baseline_model"] = {
            "status": "skipped",
            "reason": "pip install sports-betting required",
        }
    except Exception as exc:
        result["baseline_model"] = {"status": "error", "error": str(exc)}

    # ─── Comparison verdict ───
    our_ll = result["our_model"].get("log_loss")
    base_yield = (result["baseline_model"].get("summary") or {}).get("yield")
    our_roi = result["our_model"].get("roi")

    result["comparison"] = {
        "our_log_loss": our_ll,
        "our_roi": our_roi,
        "baseline_yield": base_yield,
        "verdict": (
            "OURS_WINS" if our_roi is not None and base_yield is not None and our_roi > base_yield
            else "BASELINE_WINS" if our_roi is not None and base_yield is not None and our_roi < base_yield
            else "INCONCLUSIVE"
        ),
    }
    return result


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = run_baseline_comparison()
    print(json.dumps(result, indent=2, default=str))
    verdict = result["comparison"]["verdict"]
    if verdict == "BASELINE_WINS":
        logger.warning("⚠️  Baseline wins — our model is not adding value over sports-betting default")
        return 2
    elif verdict == "OURS_WINS":
        logger.info("✅  Our model beats sports-betting baseline")
        return 0
    else:
        logger.info("⚠️  Inconclusive — likely missing dependencies or data")
        return 1


if __name__ == "__main__":
    sys.exit(main())

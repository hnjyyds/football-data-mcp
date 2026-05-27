"""
Per-league strategy: identify which leagues our model beats the market on,
and restrict recommendations to those leagues only.

Inefficient markets (small leagues, women's, lower divisions) often have
larger edges but more variance. Highly efficient markets (Premier League,
Bundesliga top 5) have tiny edges but stable odds.

This module:
1. Computes per-league log_loss_model_minus_market from settled records
2. Classifies leagues into "winning" / "losing" / "uncertain"
3. Exposes a filter that recommendation pipelines can call to skip
   non-winning leagues
"""
from __future__ import annotations

import json
import logging
import math
import sqlite3
from typing import Any

from football_data_mcp import learning_store

logger = logging.getLogger(__name__)

# Minimum settled samples per league required for classification
MIN_LEAGUE_SAMPLES = 25


def compute_league_breakdown(*, db_path: str | None = None) -> dict[str, Any]:
    """
    Aggregate per-league hit rate, ROI, log-loss model-vs-market.

    Returns:
        {
          "by_league": {league: {samples, hit_rate, roi, log_loss_diff, classification}},
          "winning_leagues": [...],
          "losing_leagues": [...],
          "uncertain_leagues": [...],
          "all_leagues_classification_method": "...",
        }
    """
    by_league: dict[str, dict[str, Any]] = {}

    with sqlite3.connect(db_path or learning_store.learning_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT league, model_probability, market_probability, hit,
                   profit_units, raw_json
            FROM recommendation_records
            WHERE settlement_status = 'settled'
              AND league IS NOT NULL
              AND league != ''
            """
        ).fetchall()

    for row in rows:
        league = str(row["league"])
        bucket = by_league.setdefault(league, {
            "samples": 0,
            "hits": 0,
            "profit_sum": 0.0,
            "log_loss_model_sum": 0.0,
            "log_loss_market_sum": 0.0,
            "valid_log_loss_samples": 0,
        })
        bucket["samples"] += 1
        if int(row["hit"] or 0) == 1:
            bucket["hits"] += 1
        bucket["profit_sum"] += float(row["profit_units"] or 0)

        # Log-loss: -log(p_actual)
        actual = 1 if int(row["hit"] or 0) == 1 else 0
        for prob_field, sum_key in (
            ("model_probability", "log_loss_model_sum"),
            ("market_probability", "log_loss_market_sum"),
        ):
            p = row[prob_field]
            if p is None:
                continue
            p_actual = float(p) if actual == 1 else (1 - float(p))
            p_actual = max(min(p_actual, 0.999), 0.001)
            bucket[sum_key] += -math.log(p_actual)
        if row["model_probability"] is not None and row["market_probability"] is not None:
            bucket["valid_log_loss_samples"] += 1

    classifications: dict[str, str] = {}
    league_summaries: dict[str, Any] = {}
    for league, data in by_league.items():
        samples = data["samples"]
        if samples < MIN_LEAGUE_SAMPLES:
            classification = "insufficient_data"
        else:
            ll_model = data["log_loss_model_sum"] / max(data["valid_log_loss_samples"], 1)
            ll_market = data["log_loss_market_sum"] / max(data["valid_log_loss_samples"], 1)
            ll_diff = ll_model - ll_market
            roi = data["profit_sum"] / samples
            # Classification rule:
            # - winning: log_loss_diff < -0.005 AND roi > 0
            # - losing: log_loss_diff > 0.01 OR roi < -0.05
            # - uncertain: otherwise
            if ll_diff < -0.005 and roi > 0:
                classification = "winning"
            elif ll_diff > 0.01 or roi < -0.05:
                classification = "losing"
            else:
                classification = "uncertain"

        classifications[league] = classification

        ll_diff_value = None
        if data["valid_log_loss_samples"] >= MIN_LEAGUE_SAMPLES:
            ll_diff_value = round(
                data["log_loss_model_sum"] / data["valid_log_loss_samples"]
                - data["log_loss_market_sum"] / data["valid_log_loss_samples"],
                5,
            )
        league_summaries[league] = {
            "samples": samples,
            "hit_rate": round(data["hits"] / samples, 4) if samples else None,
            "roi": round(data["profit_sum"] / samples, 4) if samples else None,
            "log_loss_diff": ll_diff_value,
            "classification": classification,
        }

    return {
        "by_league": league_summaries,
        "winning_leagues": sorted(l for l, c in classifications.items() if c == "winning"),
        "losing_leagues": sorted(l for l, c in classifications.items() if c == "losing"),
        "uncertain_leagues": sorted(l for l, c in classifications.items() if c == "uncertain"),
        "min_samples_required": MIN_LEAGUE_SAMPLES,
        "classification_method": "log_loss_diff_lt_-0.005_and_roi_positive",
    }


def is_league_allowed(league: str, *, db_path: str | None = None) -> dict[str, Any]:
    """
    Quick lookup: can we recommend in this league right now?

    Conservative default: if league hasn't been classified yet (no data),
    allow it (shadow mode) but flag for paper-only.
    """
    if not league:
        return {"allowed": True, "mode": "default", "reason": "no_league"}

    breakdown = compute_league_breakdown(db_path=db_path)
    info = breakdown["by_league"].get(league)
    if not info or info["classification"] == "insufficient_data":
        return {
            "allowed": True,
            "mode": "paper_only",
            "reason": "insufficient_data",
            "classification": info["classification"] if info else "unknown",
        }
    if info["classification"] == "winning":
        return {
            "allowed": True,
            "mode": "production_ready",
            "reason": "league_proven_winning",
            "classification": "winning",
            "log_loss_diff": info["log_loss_diff"],
        }
    if info["classification"] == "losing":
        return {
            "allowed": False,
            "mode": "blocked",
            "reason": "league_consistently_losing",
            "classification": "losing",
            "log_loss_diff": info["log_loss_diff"],
        }
    # uncertain
    return {
        "allowed": True,
        "mode": "paper_only",
        "reason": "league_uncertain",
        "classification": "uncertain",
        "log_loss_diff": info["log_loss_diff"],
    }

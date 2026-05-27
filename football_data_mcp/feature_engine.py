"""
Feature engine: lightweight feature extraction for football match prediction.

Currently provides:
- Recent form aggregations with exponential decay
- Head-to-head historical features
- Rest days / fixture congestion features
- Goal-difference momentum features

These features can be fed into model_engine.build_model_projection via the
`form` argument's `team_strength.engineered_features` slot.

Future extensions:
- Player-availability features (lineup-based)
- xG event sequence features (requires shot-level data)
- Gradient boosting layer for xG fine-tuning
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

try:
    import numpy as np
    from sklearn.ensemble import GradientBoostingRegressor
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


# ─── Form & momentum features ────────────────────────────────────────────────


def exponential_decay_avg(
    values: list[float],
    halflife_matches: float = 5.0,
) -> float | None:
    """Weighted average where recent matches matter more. Most recent first."""
    if not values:
        return None
    if not _SKLEARN_AVAILABLE:
        # pure-python fallback
        total = 0.0
        weight_sum = 0.0
        for i, v in enumerate(values):
            w = math.exp(-i * math.log(2) / halflife_matches)
            total += v * w
            weight_sum += w
        return total / weight_sum if weight_sum else None
    arr = np.array(values, dtype=np.float64)
    weights = np.exp(-np.arange(len(arr)) * math.log(2) / halflife_matches)
    return float(np.average(arr, weights=weights))


def compute_goal_momentum(recent_matches: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Goal-difference momentum: rolling weighted goal differential.
    `recent_matches` should be sorted most recent first, each with:
    - goals_for, goals_against, is_home (bool)
    """
    if not recent_matches:
        return {"available": False}

    diffs = [
        float(m.get("goals_for", 0)) - float(m.get("goals_against", 0))
        for m in recent_matches[:10]
    ]
    weighted = exponential_decay_avg(diffs, halflife_matches=4.0)
    raw_avg = sum(diffs) / len(diffs) if diffs else 0.0

    return {
        "available": True,
        "raw_diff_avg_last10": round(raw_avg, 3),
        "weighted_momentum": round(weighted, 3) if weighted is not None else None,
        "trend": (
            "improving" if weighted is not None and weighted > raw_avg + 0.15
            else "declining" if weighted is not None and weighted < raw_avg - 0.15
            else "stable"
        ),
        "sample_count": len(diffs),
        "method": "exponential_decay_halflife_4",
    }


def compute_rest_days(
    last_match_kickoff_utc: str | None,
    current_kickoff_utc: str | None,
) -> dict[str, Any]:
    """Days since last match. Critical for fatigue modeling."""
    if not last_match_kickoff_utc or not current_kickoff_utc:
        return {"available": False}
    try:
        last_t = datetime.fromisoformat(last_match_kickoff_utc.replace("Z", "+00:00"))
        curr_t = datetime.fromisoformat(current_kickoff_utc.replace("Z", "+00:00"))
        if last_t.tzinfo is None:
            last_t = last_t.replace(tzinfo=timezone.utc)
        if curr_t.tzinfo is None:
            curr_t = curr_t.replace(tzinfo=timezone.utc)
        days = (curr_t - last_t).total_seconds() / 86400.0
        if days < 0:
            return {"available": False, "reason": "negative_diff"}
        # Fatigue factor: <3 days = high; 3-5 = medium; >5 = none
        fatigue = (
            "high" if days < 3
            else "medium" if days < 5
            else "none"
        )
        return {
            "available": True,
            "rest_days": round(days, 1),
            "fatigue_risk": fatigue,
        }
    except (ValueError, TypeError) as exc:
        return {"available": False, "reason": str(exc)}


# ─── Head-to-head features ───────────────────────────────────────────────────


def compute_h2h_record(
    h2h_matches: list[dict[str, Any]],
    home_team: str,
    away_team: str,
    max_lookback: int = 10,
) -> dict[str, Any]:
    """
    Aggregate head-to-head history.
    `h2h_matches` should contain matches between home_team and away_team
    with keys: home_team, away_team, home_goals, away_goals, kickoff_utc.
    """
    if not h2h_matches:
        return {"available": False}

    recent = sorted(h2h_matches, key=lambda m: m.get("kickoff_utc", ""), reverse=True)[:max_lookback]
    wins_for_current_home = 0
    draws = 0
    wins_for_current_away = 0
    goals_for_current_home = 0
    goals_for_current_away = 0

    for m in recent:
        hg = m.get("home_goals")
        ag = m.get("away_goals")
        if hg is None or ag is None:
            continue
        hg, ag = int(hg), int(ag)
        # Normalize perspective: who was at home in *this* h2h match
        h2h_home = str(m.get("home_team") or "")
        if h2h_home.lower().strip() == home_team.lower().strip():
            # current home was also home in this h2h
            goals_for_current_home += hg
            goals_for_current_away += ag
            if hg > ag: wins_for_current_home += 1
            elif hg < ag: wins_for_current_away += 1
            else: draws += 1
        else:
            # current home was away in this h2h
            goals_for_current_home += ag
            goals_for_current_away += hg
            if ag > hg: wins_for_current_home += 1
            elif ag < hg: wins_for_current_away += 1
            else: draws += 1

    total = wins_for_current_home + draws + wins_for_current_away
    if total == 0:
        return {"available": False, "reason": "no_completed_h2h"}

    return {
        "available": True,
        "sample_count": total,
        "home_win_rate": round(wins_for_current_home / total, 4),
        "draw_rate": round(draws / total, 4),
        "away_win_rate": round(wins_for_current_away / total, 4),
        "home_goals_avg": round(goals_for_current_home / total, 3),
        "away_goals_avg": round(goals_for_current_away / total, 3),
        "h2h_total_goals_avg": round((goals_for_current_home + goals_for_current_away) / total, 3),
        "max_lookback": max_lookback,
    }


# ─── Gradient boosting xG residual model ─────────────────────────────────────


class XGResidualModel:
    """
    Lightweight gradient boosting model that predicts the *residual* between
    market-implied xG and observed goals, conditional on engineered features.

    Use it as a "tilt" on top of the Dixon-Coles market-anchored projection:
    - Train: collect (features, observed_goals - market_xg) pairs after settlement
    - Predict: predict residual for new match, add it to market_xg

    This is NOT a replacement for the Poisson model — it's a calibration tilt
    that gradually learns systematic biases in the market.
    """

    FEATURE_KEYS = (
        "form_goals_for",
        "form_goals_against",
        "form_weighted_momentum",
        "rest_days",
        "elo_rating",
        "elo_diff",
        "h2h_home_win_rate",
        "h2h_avg_goals",
        "market_xg",
    )

    def __init__(self):
        if not _SKLEARN_AVAILABLE:
            raise RuntimeError("sklearn not available; cannot build XGResidualModel")
        self.home_model = GradientBoostingRegressor(
            n_estimators=80, max_depth=3, learning_rate=0.05, subsample=0.8,
            random_state=42,
        )
        self.away_model = GradientBoostingRegressor(
            n_estimators=80, max_depth=3, learning_rate=0.05, subsample=0.8,
            random_state=42,
        )
        self.is_trained = False
        self.min_training_samples = 100
        self.training_metadata: dict[str, Any] = {}

    def _to_feature_vector(self, features: dict[str, Any]) -> list[float]:
        return [float(features.get(k) or 0.0) for k in self.FEATURE_KEYS]

    def fit(
        self,
        training_records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Train on settled records.
        Each record needs: features dict, market_home_xg, market_away_xg,
        observed_home_goals, observed_away_goals.
        """
        if not _SKLEARN_AVAILABLE:
            return {"status": "skipped", "reason": "sklearn_not_available"}
        if len(training_records) < self.min_training_samples:
            return {
                "status": "insufficient_samples",
                "sample_count": len(training_records),
                "min_required": self.min_training_samples,
            }

        X = []
        y_home = []
        y_away = []
        for rec in training_records:
            feats = rec.get("features") or {}
            market_home_xg = float(rec.get("market_home_xg") or 0)
            market_away_xg = float(rec.get("market_away_xg") or 0)
            obs_home = float(rec.get("observed_home_goals") or 0)
            obs_away = float(rec.get("observed_away_goals") or 0)
            X.append(self._to_feature_vector({**feats, "market_xg": market_home_xg}))
            y_home.append(obs_home - market_home_xg)
            y_away.append(obs_away - market_away_xg)

        Xa = np.array(X)
        self.home_model.fit(Xa, np.array(y_home))
        self.away_model.fit(Xa, np.array(y_away))
        self.is_trained = True
        self.training_metadata = {
            "sample_count": len(training_records),
            "home_feature_importances": dict(zip(self.FEATURE_KEYS, [float(v) for v in self.home_model.feature_importances_])),
            "away_feature_importances": dict(zip(self.FEATURE_KEYS, [float(v) for v in self.away_model.feature_importances_])),
            "home_residual_mean": float(np.mean(y_home)),
            "away_residual_mean": float(np.mean(y_away)),
            "home_residual_std": float(np.std(y_home)),
            "away_residual_std": float(np.std(y_away)),
        }
        return {
            "status": "ok",
            "trained": True,
            **self.training_metadata,
        }

    def predict_residuals(
        self,
        features: dict[str, Any],
        market_home_xg: float,
        market_away_xg: float,
    ) -> dict[str, float]:
        """Return (home_residual, away_residual) to add to market xG."""
        if not self.is_trained:
            return {"home_residual": 0.0, "away_residual": 0.0, "available": False}
        x_home = np.array([self._to_feature_vector({**features, "market_xg": market_home_xg})])
        x_away = np.array([self._to_feature_vector({**features, "market_xg": market_away_xg})])
        # Cap residuals to avoid overfit jumps
        h_pred = float(self.home_model.predict(x_home)[0])
        a_pred = float(self.away_model.predict(x_away)[0])
        h_pred = max(-0.5, min(0.5, h_pred))
        a_pred = max(-0.5, min(0.5, a_pred))
        return {
            "home_residual": round(h_pred, 4),
            "away_residual": round(a_pred, 4),
            "available": True,
        }


# Module-level singleton (lazy init)
_residual_model: XGResidualModel | None = None


def get_residual_model() -> XGResidualModel | None:
    """Return the singleton residual model if sklearn is available."""
    global _residual_model
    if not _SKLEARN_AVAILABLE:
        return None
    if _residual_model is None:
        try:
            _residual_model = XGResidualModel()
        except RuntimeError:
            return None
    return _residual_model

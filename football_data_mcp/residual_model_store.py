"""
Persist + serve the trained XGResidualModel between predictions.

Lifecycle:
1. extract_training_records_from_learning_store(): pull settled records
   from learning DB, build (features, market_xg, observed_goals) triples
2. train_and_save(): fit the GradientBoosting models, pickle to /data/
3. load_active_model(): module-level cached load; predictions hit RAM

Used by model_engine.build_model_projection to tilt market-anchored xG.
"""
from __future__ import annotations

import json
import logging
import os
import pickle
import sqlite3
import time
from typing import Any

from football_data_mcp import feature_engine, learning_store

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = "/data/residual_model.pkl"
MODEL_RELOAD_TTL_SECONDS = 300.0  # check disk every 5min

_CACHED_MODEL: feature_engine.XGResidualModel | None = None
_CACHED_AT: float = 0.0


def model_path() -> str:
    return os.getenv("FOOTBALL_DATA_RESIDUAL_MODEL_PATH", DEFAULT_MODEL_PATH)


def extract_training_records_from_learning_store(
    *,
    db_path: str | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    """Build training records from settled recommendation_records."""
    with sqlite3.connect(db_path or learning_store.learning_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM recommendation_records
            WHERE settlement_status = 'settled'
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
              AND market = 'asian_handicap'
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()

    training = []
    for row in rows:
        record = dict(row)
        try:
            raw = json.loads(record.get("raw_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            raw = {}
        if not isinstance(raw, dict):
            continue

        # Extract market xG from the projection that was used at decision time
        projection = (raw.get("projection") or raw.get("model_projection") or {})
        expected_goals = (projection.get("expected_goals") or {})
        market_home_xg = expected_goals.get("home")
        market_away_xg = expected_goals.get("away")
        if market_home_xg is None or market_away_xg is None:
            continue

        # Extract features from the raw context
        form = (raw.get("form") or {})
        elo = ((form.get("team_strength") or {}).get("rolling_elo") or {})
        recent = (form.get("recent_record_summary") or {})

        features = {
            "form_goals_for": (recent.get("home") or {}).get("goals_for_per_match") or 0,
            "form_goals_against": (recent.get("home") or {}).get("goals_against_per_match") or 0,
            "form_weighted_momentum": elo.get("expected_goal_diff_hint") or 0,
            "rest_days": 0,  # not tracked currently — will be 0 baseline
            "elo_rating": (elo.get("home") or {}).get("rating") or 1500,
            "elo_diff": elo.get("adjusted_rating_diff_home_minus_away") or 0,
            "h2h_home_win_rate": 0.5,  # not tracked currently
            "h2h_avg_goals": 2.5,  # league baseline
        }

        training.append({
            "features": features,
            "market_home_xg": float(market_home_xg),
            "market_away_xg": float(market_away_xg),
            "observed_home_goals": float(record["home_score"]),
            "observed_away_goals": float(record["away_score"]),
        })
    return training


def train_and_save(
    *,
    db_path: str | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Train residual model on settled records and persist to disk."""
    try:
        model = feature_engine.XGResidualModel()
    except RuntimeError as exc:
        return {"status": "skipped", "reason": str(exc)}

    training = extract_training_records_from_learning_store(db_path=db_path)
    fit_result = model.fit(training)
    if fit_result.get("status") != "ok":
        return {**fit_result, "training_count": len(training)}

    path = output_path or model_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        pickle.dump({"model": model, "trained_at": time.time(), "sample_count": len(training)}, fh)

    global _CACHED_MODEL, _CACHED_AT
    _CACHED_MODEL = model
    _CACHED_AT = time.time()

    logger.info("residual_model trained on %d samples → %s", len(training), path)
    return {
        "status": "ok",
        "training_count": len(training),
        "model_path": path,
        **fit_result,
    }


def load_active_model() -> feature_engine.XGResidualModel | None:
    """Lazy-load + cache the latest trained model."""
    global _CACHED_MODEL, _CACHED_AT
    now = time.time()
    if _CACHED_MODEL is not None and (now - _CACHED_AT) < MODEL_RELOAD_TTL_SECONDS:
        return _CACHED_MODEL

    path = model_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as fh:
            payload = pickle.load(fh)
        _CACHED_MODEL = payload.get("model")
        _CACHED_AT = now
        return _CACHED_MODEL
    except Exception as exc:
        logger.warning("failed to load residual model: %s", exc)
        return None


def predict_residual_correction(
    features: dict[str, Any],
    market_home_xg: float,
    market_away_xg: float,
) -> dict[str, Any]:
    """Return residual corrections to add to market xG (paper_only signal)."""
    model = load_active_model()
    if model is None or not model.is_trained:
        return {"available": False, "reason": "no_trained_model"}
    return model.predict_residuals(features, market_home_xg, market_away_xg)

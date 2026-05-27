"""
Event-sequence-based xG framework.

Status: SCAFFOLD ONLY. Requires shot-level + preceding-event data which
the current free-tier data sources don't provide. This module defines the
interface and feature contract so we can wire it in when:
- StatsBomb Open Data is integrated, or
- Sportmonks/API-Football paid tier provides shot-level events

Per PLOS One (2024) "Predicting goal probabilities with improved xG models
using event sequences", incorporating the 5 events preceding each shot
gives ~3-7% calibration improvement over single-shot features.

Feature contract:
- shot location (x, y on standard 105x68 pitch)
- shot type (foot/head/penalty/freekick)
- pre-shot events (5 most recent): pass, dribble, carry, tackle, save
- pressure (defender count within 3m)
- shooter quality (recent xG-per-shot performance)
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# Standard pitch dimensions for normalization
PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0


def shot_to_xg_features(shot: dict[str, Any], preceding_events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """
    Extract features from a single shot + preceding events.

    `shot` expects keys:
        x, y (location in meters from attacker's goal at x=0)
        body_part: 'foot' | 'head' | 'penalty' | 'free_kick'
        defenders_in_range: int (within 3m)
        shooter_id: str
    `preceding_events`: list of up to 5 events leading to the shot.

    Returns feature dict consumable by an event-xG ML model.
    """
    x = float(shot.get("x", 0))
    y = float(shot.get("y", 0))
    body_part = str(shot.get("body_part", "foot"))

    # Geometry features
    # Distance to goal (goal at x=0, y=PITCH_WIDTH_M/2)
    goal_x = 0.0
    goal_y = PITCH_WIDTH_M / 2
    distance = ((x - goal_x) ** 2 + (y - goal_y) ** 2) ** 0.5

    # Angle to goal (atan2 — wider = better angle)
    import math
    goal_post_left = PITCH_WIDTH_M / 2 - 3.66
    goal_post_right = PITCH_WIDTH_M / 2 + 3.66
    angle_left = math.atan2(goal_post_left - y, x)
    angle_right = math.atan2(goal_post_right - y, x)
    angle_to_goal = abs(angle_right - angle_left)

    # Body part one-hots
    is_head = 1 if body_part == "head" else 0
    is_penalty = 1 if body_part == "penalty" else 0
    is_freekick = 1 if body_part == "free_kick" else 0

    # Defensive pressure
    defenders = int(shot.get("defenders_in_range", 0))

    # Pre-shot event features
    pre_events = preceding_events or []
    pre_event_count = len(pre_events)
    pre_event_types = [str(e.get("type", "")) for e in pre_events]
    has_pre_through_ball = 1 if "through_ball" in pre_event_types else 0
    has_pre_cross = 1 if "cross" in pre_event_types else 0
    has_pre_dribble = 1 if "dribble" in pre_event_types else 0
    chain_speed_mps = _compute_chain_speed(pre_events)

    return {
        "distance_m": round(distance, 2),
        "angle_to_goal_rad": round(angle_to_goal, 4),
        "is_head": is_head,
        "is_penalty": is_penalty,
        "is_freekick": is_freekick,
        "defenders_in_range": defenders,
        "pre_event_count": pre_event_count,
        "has_pre_through_ball": has_pre_through_ball,
        "has_pre_cross": has_pre_cross,
        "has_pre_dribble": has_pre_dribble,
        "chain_speed_mps": round(chain_speed_mps, 2),
    }


def _compute_chain_speed(events: list[dict[str, Any]]) -> float:
    """Average pitch progression rate (m/s) of the pre-shot event chain."""
    if len(events) < 2:
        return 0.0
    progressions = []
    for i in range(1, len(events)):
        prev = events[i - 1]
        curr = events[i]
        dx = float(curr.get("x", 0)) - float(prev.get("x", 0))
        dt = max(0.5, float(curr.get("timestamp_s", 0)) - float(prev.get("timestamp_s", 0)))
        progressions.append(dx / dt)
    return sum(progressions) / len(progressions) if progressions else 0.0


def aggregate_match_xg(
    home_shots: list[dict[str, Any]],
    away_shots: list[dict[str, Any]],
    model_predict_fn=None,
) -> dict[str, Any]:
    """
    Sum per-shot xG into match-level home/away xG.

    `model_predict_fn`: callable that takes feature dict, returns probability.
    If None, returns a simple distance-based heuristic (for testing).
    """
    def shot_xg(s: dict[str, Any]) -> float:
        if model_predict_fn is None:
            # Heuristic: 1 / (1 + 0.5*distance^1.4)
            distance = ((s.get("x", 0)) ** 2 + (s.get("y", 0) - 34) ** 2) ** 0.5
            return min(0.95, 1.0 / (1.0 + 0.5 * distance ** 1.4))
        features = shot_to_xg_features(s, s.get("preceding_events"))
        return float(model_predict_fn(features))

    home_xg = sum(shot_xg(s) for s in home_shots)
    away_xg = sum(shot_xg(s) for s in away_shots)
    return {
        "home_xg": round(home_xg, 3),
        "away_xg": round(away_xg, 3),
        "home_shot_count": len(home_shots),
        "away_shot_count": len(away_shots),
        "method": "event_sequence_xg_v0_scaffold",
        "data_source": "requires_shot_level_data",
    }


def integration_status() -> dict[str, Any]:
    """Diagnostic — what data sources are needed for this to work."""
    import os
    return {
        "scaffold_only": True,
        "data_source_status": {
            "statsbomb_open_data": "not_integrated",
            "sportmonks_shot_events": (
                "configured" if os.getenv("SPORTMONKS_API_TOKEN") else "not_configured"
            ),
            "api_football_events": (
                "configured" if os.getenv("API_FOOTBALL_KEY") else "not_configured"
            ),
        },
        "next_steps": [
            "Integrate StatsBomb Open Data CSV loader for offline training",
            "Train RandomForest on (features, observed_goal) pairs",
            "Add per-shot endpoint to expose match aggregate event-xG",
            "Compare event-xG vs market-anchored xG on holdout",
        ],
    }

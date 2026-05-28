from __future__ import annotations

from typing import Any

from football_data_mcp import sources


def build_dashboard_summary() -> dict[str, Any]:
    snapshot = sources.dashboard_snapshot()
    kpis = snapshot.get("kpis") or {}
    prediction_kpis = snapshot.get("prediction_kpis") or {}
    strategy_state = snapshot.get("strategy_state") or {}
    return {
        "status": "ok",
        "generated_at_utc": snapshot.get("generated_at_utc"),
        "kpis": {
            "open_records": kpis.get("open_records"),
            "settled_records": kpis.get("settled_records"),
            "asian_pick_count": kpis.get("asian_pick_count"),
            "live_calibration_active": kpis.get("live_calibration_active"),
        },
        "prediction_kpis": {
            "hit_rate": prediction_kpis.get("hit_rate"),
            "roi": prediction_kpis.get("roi"),
            "settled_count": prediction_kpis.get("settled_count"),
            "recommended_count": prediction_kpis.get("recommended_count"),
        },
        "strategy_status": strategy_state.get("status"),
        "strategy_sample_count": strategy_state.get("sample_count"),
    }

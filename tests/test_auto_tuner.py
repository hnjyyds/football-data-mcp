from __future__ import annotations

import asyncio
from typing import Any

from football_data_mcp import auto_tuner


def _division_result(division: str = "E0", *, bet_count: int = 31) -> dict[str, object]:
    return {
        "division": division,
        "league": "England Premier League",
        "status": "ok",
        "selected_config": {
            "edge_threshold": 0.03,
            "min_training_samples": 20,
        },
        "validation_result": {
            "roi": -0.02,
            "bet_count": bet_count,
        },
        "calibrated_validation_result": {
            "roi": 0.08,
            "bet_count": bet_count,
        },
    }


def test_auto_tune_awaits_holdout_and_reads_current_result_contract(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def fake_holdout(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {
            "status": "ok",
            "division_results": [_division_result()],
        }

    monkeypatch.setattr("football_data_mcp.backtest.run_holdout_validation", fake_holdout)

    result = auto_tuner.run_auto_tune(
        divisions=["E0"],
        training_seasons=["2122"],
        validation_seasons=["2223"],
        edge_thresholds=[0.03],
        min_training_samples_options=[20],
        dry_run=True,
    )

    assert calls and calls[0]["divisions"] == ["E0"]
    assert result["status"] == "ok"
    assert result["divisions_analyzed"] == 1
    assert result["valid_division_count"] == 1
    assert result["recommended_edge_threshold"] == 0.03
    assert result["by_division"]["E0"] == {
        "best_edge_threshold": 0.03,
        "best_min_training_samples": 20,
        "validation_roi": 0.08,
        "validation_bet_count": 31,
        "meets_min_bets": True,
    }


def test_auto_tune_async_can_run_inside_existing_event_loop(monkeypatch) -> None:
    async def fake_holdout(**_kwargs: object) -> dict[str, object]:
        return {
            "status": "ok",
            "division_results": [_division_result("SP1", bet_count=35)],
        }

    monkeypatch.setattr("football_data_mcp.backtest.run_holdout_validation", fake_holdout)

    async def run() -> dict[str, Any]:
        return await auto_tuner.run_auto_tune_async(divisions=["SP1"], dry_run=True)

    result = asyncio.run(run())

    assert result["status"] == "ok"
    assert result["by_division"]["SP1"]["validation_bet_count"] == 35


def test_auto_tune_skips_divisions_without_selected_config(monkeypatch) -> None:
    async def fake_holdout(**_kwargs: object) -> dict[str, object]:
        return {
            "status": "ok",
            "division_results": [
                {
                    "division": "I1",
                    "league": "Italy Serie A",
                    "status": "no_training_config",
                    "selected_config": None,
                    "validation_result": None,
                    "calibrated_validation_result": None,
                }
            ],
        }

    monkeypatch.setattr("football_data_mcp.backtest.run_holdout_validation", fake_holdout)

    result = auto_tuner.run_auto_tune(divisions=["I1"], dry_run=True)

    assert result["status"] == "ok"
    assert result["divisions_analyzed"] == 1
    assert result["valid_division_count"] == 0
    assert result["recommended_edge_threshold"] == 0.02
    assert result["by_division"]["I1"]["meets_min_bets"] is False

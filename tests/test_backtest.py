import asyncio

from football_data_mcp import server
from football_data_mcp import backtest


def _row(
    date: str,
    home: str,
    away: str,
    fthg: int,
    ftag: int,
    *,
    avg_h: float = 2.0,
    avg_d: float = 3.4,
    avg_a: float = 3.8,
    over: float = 1.9,
    under: float = 1.95,
) -> dict[str, str]:
    if fthg > ftag:
        result = "H"
    elif fthg == ftag:
        result = "D"
    else:
        result = "A"
    return {
        "Div": "E0",
        "Date": date,
        "Time": "15:00",
        "HomeTeam": home,
        "AwayTeam": away,
        "FTHG": str(fthg),
        "FTAG": str(ftag),
        "FTR": result,
        "AvgH": str(avg_h),
        "AvgD": str(avg_d),
        "AvgA": str(avg_a),
        "Avg>2.5": str(over),
        "Avg<2.5": str(under),
        "AHh": "-0.5",
        "AvgAHH": "1.92",
        "AvgAHA": "2.02",
    }


def _rows_for_division(division: str, start_day: int = 1) -> list[dict[str, str]]:
    rows = []
    teams = ["A", "B", "C", "D"]
    for index in range(8):
        home = f"{division}{teams[index % 4]}"
        away = f"{division}{teams[(index + 1) % 4]}"
        home_goals = 2 if index % 3 != 0 else 0
        away_goals = 1 if index % 2 == 0 else 2
        row = _row(
            f"{start_day + index:02d}/08/2025",
            home,
            away,
            home_goals,
            away_goals,
            avg_h=1.8 + (index % 3) * 0.2,
            avg_d=3.2 + (index % 2) * 0.1,
            avg_a=4.0 - (index % 3) * 0.2,
        )
        row["Div"] = division
        rows.append(row)
    return rows


def test_build_historical_samples_extracts_results_and_preferred_markets():
    rows = [
        _row("01/08/2025", "Arsenal", "Chelsea", 2, 1),
        {
            "Div": "E0",
            "Date": "02/08/2025",
            "HomeTeam": "Incomplete",
            "AwayTeam": "No Result",
            "AvgH": "2.0",
            "AvgD": "3.2",
            "AvgA": "3.5",
        },
    ]

    samples = backtest.build_historical_samples(rows, division="E0", season="2526")

    assert len(samples) == 1
    sample = samples[0]
    assert sample["match"]["home_team"] == "Arsenal"
    assert sample["actual"]["result_1x2"] == "home"
    assert sample["actual"]["total_goals"] == 3
    assert sample["actual"]["over_under_2_5"] == "over"
    assert sample["odds"]["preferred_moneyline_1x2"]["provider"] == "Average"
    assert sample["odds"]["quality_contract"]["supported_markets"]["moneyline_1x2"] is True
    assert sample["odds"]["quality_contract"]["supported_markets"]["over_under"] is True


def test_walk_forward_backtest_uses_only_prior_matches_and_reports_metrics():
    samples = backtest.build_historical_samples(
        [
            _row("01/08/2025", "Arsenal", "Chelsea", 2, 0, avg_h=1.9, avg_d=3.5, avg_a=4.2),
            _row("02/08/2025", "Liverpool", "Spurs", 1, 1, avg_h=2.1, avg_d=3.4, avg_a=3.4),
            _row("08/08/2025", "Arsenal", "Spurs", 3, 1, avg_h=1.8, avg_d=3.6, avg_a=4.6),
            _row("09/08/2025", "Chelsea", "Liverpool", 0, 1, avg_h=2.5, avg_d=3.2, avg_a=2.8),
        ],
        division="E0",
        season="2526",
    )

    result = backtest.run_walk_forward_backtest(
        samples,
        min_training_samples=2,
        edge_threshold=0.0,
        stake=1.0,
    )

    assert result["status"] == "ok"
    assert result["summary"]["sample_count"] == 4
    assert result["summary"]["evaluated_count"] == 2
    assert result["summary"]["skipped_for_training_count"] == 2
    assert result["records"][0]["training_sample_count"] == 2
    assert result["records"][0]["leakage_policy"] == "only matches with kickoff before this sample are used for form features"
    assert result["records"][0]["form_summary"]["home"]["sample_size"] == 1
    rolling_elo = result["records"][0]["team_strength"]["rolling_elo"]
    assert rolling_elo["method"] == "rolling_elo_from_prior_results_v1"
    assert rolling_elo["home"]["team"] == "Arsenal"
    assert rolling_elo["away"]["team"] == "Spurs"
    assert rolling_elo["leakage_policy"] == "ratings are built only from prior completed samples"
    assert result["metrics"]["model"]["log_loss_1x2"] > 0
    assert result["metrics"]["market"]["brier_score_1x2"] > 0
    assert result["betting"]["bet_count"] >= 1
    assert "roi" in result["betting"]
    assert result["calibration"]["model_1x2"]


def test_run_historical_backtest_tool_delegates_to_backtest_module(monkeypatch):
    async def fake_run_football_data_backtest(**kwargs):
        return {
            "status": "ok",
            "division": kwargs["division"],
            "season": kwargs["season"],
            "summary": {"evaluated_count": 3},
        }

    monkeypatch.setattr(server.backtest, "run_football_data_backtest", fake_run_football_data_backtest)

    result = asyncio.run(
        server.run_historical_backtest(
            division="E0",
            season="2526",
            edge_threshold=0.03,
            min_training_samples=20,
            max_samples=100,
        )
    )

    assert result["status"] == "ok"
    assert result["division"] == "E0"
    assert result["season"] == "2526"


def test_backtest_sweep_ranks_configs_and_summarizes_segments(monkeypatch):
    fetch_calls = []

    async def fake_fetch_rows(division, season):
        fetch_calls.append((division, season))
        return _rows_for_division(division), {"url": f"https://example.test/{season}/{division}.csv"}

    monkeypatch.setattr(backtest, "fetch_football_data_season_rows", fake_fetch_rows)

    result = asyncio.run(
        backtest.run_backtest_sweep(
            divisions=["E0", "SP1"],
            seasons=["2526"],
            edge_thresholds=[0.0, 0.03],
            min_training_samples_options=[2, 4],
            max_samples=8,
        )
    )

    assert result["status"] == "ok"
    assert result["summary"]["source_count"] == 2
    assert result["summary"]["config_count"] == 8
    assert sorted(fetch_calls) == [("E0", "2526"), ("SP1", "2526")]
    assert result["best_configs"]
    assert result["worst_configs"]
    assert result["best_configs"][0]["rank_score"] >= result["worst_configs"][-1]["rank_score"]
    assert set(result["league_summary"]) == {"E0", "SP1"}
    assert set(result["season_summary"]) == {"2526"}
    assert result["sample_size_warnings"]
    assert result["sample_size_warnings"][0]["reasons"]
    assert result["automation_readiness"]["status"] in {"not_ready", "watchlist", "paper_trade_only"}
    assert result["automation_readiness"]["real_money_allowed"] is False
    assert result["agent_contract"]["no_automation_without_positive_sweep"].startswith("Do not enable")


def test_backtest_sweep_tool_delegates_to_backtest_module(monkeypatch):
    async def fake_run_backtest_sweep(**kwargs):
        return {
            "status": "ok",
            "divisions": kwargs["divisions"],
            "seasons": kwargs["seasons"],
            "summary": {"config_count": 1},
        }

    monkeypatch.setattr(server.backtest, "run_backtest_sweep", fake_run_backtest_sweep)

    result = asyncio.run(
        server.run_backtest_sweep(
            divisions=["E0"],
            seasons=["2526"],
            edge_thresholds=[0.02],
            min_training_samples_options=[20],
            max_samples=50,
        )
    )

    assert result["status"] == "ok"
    assert result["divisions"] == ["E0"]
    assert result["seasons"] == ["2526"]


def test_backtest_sweep_reuses_model_projections_across_edge_thresholds(monkeypatch):
    async def fake_fetch_rows(division, season):
        return _rows_for_division(division), {"url": f"https://example.test/{season}/{division}.csv"}

    original_projection = backtest.model_engine.build_model_projection
    call_count = 0

    def counted_projection(**kwargs):
        nonlocal call_count
        call_count += 1
        return original_projection(**kwargs)

    monkeypatch.setattr(backtest, "fetch_football_data_season_rows", fake_fetch_rows)
    monkeypatch.setattr(backtest.model_engine, "build_model_projection", counted_projection)

    result = asyncio.run(
        backtest.run_backtest_sweep(
            divisions=["E0"],
            seasons=["2526"],
            edge_thresholds=[0.0, 0.02, 0.04],
            min_training_samples_options=[2],
            max_samples=8,
        )
    )

    assert result["summary"]["config_count"] == 3
    assert call_count == 6


def test_automation_readiness_uses_best_eligible_config_not_extreme_tiny_sample():
    high_roi_tiny_sample = {
        "division": "E0",
        "season": "2324",
        "evaluated_count": 260,
        "bet_count": 1,
        "roi": 2.22,
        "log_loss_model_minus_market": 0.0007,
        "rank_score": 222.0,
    }
    eligible_large_sample = {
        "division": "F1",
        "season": "2122",
        "evaluated_count": 320,
        "bet_count": 120,
        "roi": 0.06,
        "log_loss_model_minus_market": -0.001,
        "rank_score": 8.0,
    }

    readiness = backtest._automation_readiness(
        [high_roi_tiny_sample, eligible_large_sample],
        warnings=[],
    )

    assert readiness["status"] == "paper_trade_only"
    assert readiness["best_config"] == eligible_large_sample
    assert readiness["real_money_allowed"] is False


def test_automation_readiness_prefers_stable_candidate_over_tiny_eligible_rank():
    tiny_eligible = {
        "division": "E0",
        "season": "2324",
        "evaluated_count": 300,
        "bet_count": 2,
        "roi": 2.01,
        "log_loss_model_minus_market": -0.0004,
        "rank_score": 201.0,
    }
    stable_eligible = {
        "division": "F1",
        "season": "2223",
        "evaluated_count": 360,
        "bet_count": 107,
        "roi": 0.13,
        "log_loss_model_minus_market": -0.0006,
        "rank_score": 17.0,
    }

    readiness = backtest._automation_readiness(
        [tiny_eligible, stable_eligible],
        warnings=[],
    )

    assert readiness["status"] == "paper_trade_only"
    assert readiness["best_config"] == stable_eligible


def test_holdout_validation_selects_on_training_and_scores_validation(monkeypatch):
    fetch_calls = []

    async def fake_fetch_rows(division, season):
        fetch_calls.append((division, season))
        start_day = 1 if season == "2122" else 11
        return _rows_for_division(division, start_day=start_day), {"url": f"https://example.test/{season}/{division}.csv"}

    monkeypatch.setattr(backtest, "fetch_football_data_season_rows", fake_fetch_rows)

    result = asyncio.run(
        backtest.run_holdout_validation(
            divisions=["E0"],
            training_seasons=["2122"],
            validation_seasons=["2223"],
            edge_thresholds=[0.0, 0.03],
            min_training_samples_options=[2],
            max_samples=8,
            min_selection_bets=1,
            min_validation_bets=1,
        )
    )

    assert result["status"] == "ok"
    assert result["summary"]["division_count"] == 1
    assert result["summary"]["training_config_count"] == 2
    assert sorted(fetch_calls) == [("E0", "2122"), ("E0", "2223")]
    division_result = result["division_results"][0]
    assert division_result["division"] == "E0"
    assert division_result["selected_config"]["selection_source"] == "training_only"
    assert division_result["selected_config"]["seasons"] == ["2122"]
    assert division_result["validation_result"]["seasons"] == ["2223"]
    assert division_result["validation_result"]["evaluated_count"] > 0
    assert result["holdout_readiness"]["real_money_allowed"] is False
    assert result["agent_contract"]["holdout_rule"].startswith("Training seasons select")


def test_holdout_validation_tool_delegates_to_backtest_module(monkeypatch):
    async def fake_run_holdout_validation(**kwargs):
        return {
            "status": "ok",
            "divisions": kwargs["divisions"],
            "training_seasons": kwargs["training_seasons"],
            "validation_seasons": kwargs["validation_seasons"],
        }

    monkeypatch.setattr(server.backtest, "run_holdout_validation", fake_run_holdout_validation)

    result = asyncio.run(
        server.run_holdout_validation(
            divisions=["E0"],
            training_seasons=["2122", "2223"],
            validation_seasons=["2425"],
            edge_thresholds=[0.02],
            min_training_samples_options=[40],
            max_samples=100,
        )
    )

    assert result["status"] == "ok"
    assert result["divisions"] == ["E0"]
    assert result["training_seasons"] == ["2122", "2223"]
    assert result["validation_seasons"] == ["2425"]


def test_top_k_confidence_backtest_calibrates_on_training_and_scores_validation(monkeypatch):
    fetch_calls = []

    async def fake_fetch_rows(division, season):
        fetch_calls.append((division, season))
        start_day = 1 if season == "2122" else 11
        return _rows_for_division(division, start_day=start_day), {"url": f"https://example.test/{season}/{division}.csv"}

    monkeypatch.setattr(backtest, "fetch_football_data_season_rows", fake_fetch_rows)

    result = asyncio.run(
        backtest.run_top_k_confidence_backtest(
            divisions=["E0"],
            training_seasons=["2122"],
            validation_seasons=["2223"],
            min_training_samples=2,
            top_k_options=[1, 2],
            probability_floors=[0.0, 0.55],
            max_samples=8,
        )
    )

    assert result["status"] == "ok"
    assert sorted(fetch_calls) == [("E0", "2122"), ("E0", "2223")]
    assert result["calibration"]["method"] == "empirical_top_selection_probability_bins_v1"
    assert result["calibration"]["training_record_count"] > 0
    assert result["summary"]["validation_record_count"] > 0
    assert result["top_k_results"]
    assert {row["top_k"] for row in result["top_k_results"]} == {1, 2}
    assert {row["min_calibrated_probability"] for row in result["top_k_results"]} == {0.0, 0.55}
    first = result["top_k_results"][0]
    assert "hit_rate" in first
    assert "avg_calibrated_probability" in first
    assert "roi" in first
    assert result["agent_contract"]["real_money_allowed"] is False


def test_top_k_confidence_backtest_tool_delegates_to_backtest_module(monkeypatch):
    async def fake_run_top_k_confidence_backtest(**kwargs):
        return {
            "status": "ok",
            "divisions": kwargs["divisions"],
            "training_seasons": kwargs["training_seasons"],
            "validation_seasons": kwargs["validation_seasons"],
            "top_k_options": kwargs["top_k_options"],
        }

    monkeypatch.setattr(server.backtest, "run_top_k_confidence_backtest", fake_run_top_k_confidence_backtest)

    result = asyncio.run(
        server.run_top_k_confidence_backtest(
            divisions=["E0"],
            training_seasons=["2122"],
            validation_seasons=["2223"],
            top_k_options=[1],
            probability_floors=[0.55],
        )
    )

    assert result["status"] == "ok"
    assert result["divisions"] == ["E0"]
    assert result["training_seasons"] == ["2122"]
    assert result["validation_seasons"] == ["2223"]
    assert result["top_k_options"] == [1]

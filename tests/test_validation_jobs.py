import asyncio
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from football_data_mcp import validation_store
from football_data_mcp.services import validation_service
from football_data_mcp.services.validation_service import HoldoutValidationJobConfig, ValidationJobService


def test_validation_job_store_tracks_league_progress_and_resume(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    config = HoldoutValidationJobConfig(
        divisions=["E0", "SP1"],
        training_seasons=["2122"],
        validation_seasons=["2223"],
        edge_thresholds=[0.03],
        min_training_samples_options=[20],
        max_samples=60,
    )

    job = validation_store.create_validation_job(
        method="holdout_validation_job_v1",
        divisions=config.divisions,
        training_seasons=config.training_seasons,
        validation_seasons=config.validation_seasons,
        config=config.to_store_config(),
        db_path=db_path,
    )

    validation_store.mark_validation_job_running(job["job_id"], db_path=db_path)
    validation_store.upsert_validation_league_result(
        job["job_id"],
        division="E0",
        league="England Premier League",
        status="succeeded",
        cache_key=config.cache_key_for_division("E0"),
        result={"division": "E0", "evaluated_count": 40},
        db_path=db_path,
    )

    loaded = validation_store.get_validation_job(job["job_id"], db_path=db_path)

    assert loaded is not None
    assert loaded["status"] == "running"
    assert loaded["progress"]["total_leagues"] == 2
    assert loaded["progress"]["completed_leagues"] == 1
    assert loaded["progress"]["pending_leagues"] == 1
    assert loaded["progress"]["progress_ratio"] == 0.5
    assert loaded["league_results"][0]["division"] == "E0"

    resumed = validation_store.create_validation_job(
        method="holdout_validation_job_v1",
        divisions=config.divisions,
        training_seasons=config.training_seasons,
        validation_seasons=config.validation_seasons,
        config=config.to_store_config(),
        resume=True,
        db_path=db_path,
    )

    assert resumed["job_id"] == job["job_id"]


def test_validation_job_progress_counts_failed_leagues_as_processed(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    config = HoldoutValidationJobConfig(
        divisions=["E0", "SP1"],
        training_seasons=["2122"],
        validation_seasons=["2223"],
        edge_thresholds=[0.03],
        min_training_samples_options=[20],
        max_samples=60,
    )
    job = validation_store.create_validation_job(
        method="holdout_validation_job_v1",
        divisions=config.divisions,
        training_seasons=config.training_seasons,
        validation_seasons=config.validation_seasons,
        config=config.to_store_config(),
        db_path=db_path,
    )

    validation_store.upsert_validation_league_result(
        job["job_id"],
        division="E0",
        league="England Premier League",
        status="succeeded",
        cache_key=config.cache_key_for_division("E0"),
        result={"division": "E0"},
        db_path=db_path,
    )
    validation_store.upsert_validation_league_result(
        job["job_id"],
        division="SP1",
        league="Spain La Liga",
        status="failed",
        cache_key=config.cache_key_for_division("SP1"),
        error="temporary data source failure",
        db_path=db_path,
    )

    loaded = validation_store.get_validation_job(job["job_id"], db_path=db_path)

    assert loaded is not None
    assert loaded["progress"]["completed_leagues"] == 1
    assert loaded["progress"]["failed_leagues"] == 1
    assert loaded["progress"]["processed_leagues"] == 2
    assert loaded["progress"]["progress_ratio"] == 1.0
    assert loaded["progress"]["success_ratio"] == 0.5


def test_validation_failure_summary_classifies_data_source_errors(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    config = HoldoutValidationJobConfig(
        divisions=["E0"],
        training_seasons=["2122"],
        validation_seasons=["2223"],
        edge_thresholds=[0.03],
        min_training_samples_options=[20],
        max_samples=60,
    )
    job = validation_store.create_validation_job(
        method="holdout_validation_job_v1",
        divisions=config.divisions,
        training_seasons=config.training_seasons,
        validation_seasons=config.validation_seasons,
        config=config.to_store_config(),
        db_path=db_path,
    )

    validation_store.upsert_validation_league_result(
        str(job["job_id"]),
        division="E0",
        league="England Premier League",
        status="failed",
        cache_key=config.cache_key_for_division("E0"),
        error="RuntimeError: source unavailable",
        db_path=db_path,
    )
    loaded = validation_store.get_validation_job(str(job["job_id"]), db_path=db_path)

    assert loaded is not None
    assert loaded["failure_summary"]["category"] == "data_source"
    assert loaded["failure_summary"]["stage"] == "league_validation"
    assert loaded["failure_summary"]["severity"] == "error"
    assert "检查数据源" in loaded["failure_summary"]["next_action"]


def test_validation_failure_summary_classifies_timeout_and_stale_recovery(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    config = HoldoutValidationJobConfig(
        divisions=["E0", "SP1"],
        training_seasons=["2122"],
        validation_seasons=["2223"],
        edge_thresholds=[0.03],
        min_training_samples_options=[20],
        max_samples=60,
    )
    job = validation_store.create_validation_job(
        method="holdout_validation_job_v1",
        divisions=config.divisions,
        training_seasons=config.training_seasons,
        validation_seasons=config.validation_seasons,
        config=config.to_store_config(),
        db_path=db_path,
    )

    validation_store.upsert_validation_league_result(
        str(job["job_id"]),
        division="E0",
        league="England Premier League",
        status="failed",
        cache_key=config.cache_key_for_division("E0"),
        error="TimeoutError: holdout validation exceeded 60s",
        db_path=db_path,
    )
    timeout_job = validation_store.get_validation_job(str(job["job_id"]), db_path=db_path)
    assert timeout_job is not None
    assert timeout_job["failure_summary"]["category"] == "timeout"
    assert "超时" in timeout_job["failure_summary"]["title"]

    validation_store.upsert_validation_league_result(
        str(job["job_id"]),
        division="SP1",
        league="Spain La Liga",
        status="pending",
        cache_key=config.cache_key_for_division("SP1"),
        error="Previous validation runner exceeded heartbeat window (60s); released for retry.",
        db_path=db_path,
    )
    recovered_job = validation_store.get_validation_job(str(job["job_id"]), db_path=db_path)
    assert recovered_job is not None
    assert recovered_job["failure_summary"]["category"] == "worker_recovered"
    assert recovered_job["failure_summary"]["severity"] == "warning"
    assert "无需人工处理" in recovered_job["failure_summary"]["next_action"]


def test_validation_job_execution_health_marks_stale_runner(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    config = HoldoutValidationJobConfig(
        divisions=["E0"],
        training_seasons=["2122"],
        validation_seasons=["2223"],
        edge_thresholds=[0.03],
        min_training_samples_options=[20],
        max_samples=60,
    )
    job = validation_store.create_validation_job(
        method="holdout_validation_job_v1",
        divisions=config.divisions,
        training_seasons=config.training_seasons,
        validation_seasons=config.validation_seasons,
        config=config.to_store_config(),
        db_path=db_path,
    )
    stale_at = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE model_validation_jobs
            SET status = 'running',
                runner_id = 'runner-stale',
                started_at_utc = ?,
                updated_at_utc = ?,
                runner_heartbeat_at_utc = ?
            WHERE job_id = ?
            """,
            (stale_at, stale_at, stale_at, job["job_id"]),
        )
        conn.commit()

    loaded = validation_store.get_validation_job(str(job["job_id"]), db_path=db_path)

    assert loaded is not None
    health = loaded["execution_health"]
    assert health["state"] == "stale"
    assert health["is_stale"] is True
    assert health["heartbeat_age_seconds"] >= 7000
    assert health["severity"] == "error"
    assert "worker" in health["next_action"].lower()


def test_validation_job_store_records_lifecycle_events(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    config = HoldoutValidationJobConfig(
        divisions=["E0"],
        training_seasons=["2122"],
        validation_seasons=["2223"],
        edge_thresholds=[0.03],
        min_training_samples_options=[20],
        max_samples=60,
    )
    job = validation_store.create_validation_job(
        method="holdout_validation_job_v1",
        divisions=config.divisions,
        training_seasons=config.training_seasons,
        validation_seasons=config.validation_seasons,
        config=config.to_store_config(),
        db_path=db_path,
    )

    validation_store.mark_validation_job_queued(
        str(job["job_id"]),
        backend="arq",
        message="queued for worker",
        db_path=db_path,
    )
    validation_store.claim_validation_job_run(
        str(job["job_id"]),
        stale_after_seconds=60,
        runner_id="runner-a",
        db_path=db_path,
    )
    validation_store.mark_validation_league_running(
        str(job["job_id"]),
        division="E0",
        runner_id="runner-a",
        db_path=db_path,
    )
    validation_store.upsert_validation_league_result(
        str(job["job_id"]),
        division="E0",
        league="England Premier League",
        status="failed",
        cache_key=config.cache_key_for_division("E0"),
        error="RuntimeError: source unavailable",
        runner_id="runner-a",
        db_path=db_path,
    )
    validation_store.mark_validation_job_finished(
        str(job["job_id"]),
        status="failed",
        result_summary={"failed_leagues": 1},
        error="One or more league validations failed.",
        runner_id="runner-a",
        db_path=db_path,
    )
    loaded = validation_store.get_validation_job(str(job["job_id"]), db_path=db_path)

    assert loaded is not None
    events = loaded["events"]
    assert [event["event_type"] for event in events] == [
        "job_created",
        "job_queued",
        "job_claimed",
        "league_started",
        "league_failed",
        "job_failed",
    ]
    assert events[1]["metadata"]["backend"] == "arq"
    assert events[2]["runner_id"] == "runner-a"
    assert events[3]["division"] == "E0"
    assert events[4]["severity"] == "error"
    assert events[4]["message"] == "England Premier League failed: RuntimeError: source unavailable"
    assert events[-1]["created_at_utc"] is not None


def test_validation_job_store_backfills_verdict_for_legacy_summary(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    config = HoldoutValidationJobConfig(
        divisions=["E0"],
        training_seasons=["2122"],
        validation_seasons=["2223"],
        edge_thresholds=[0.03],
        min_training_samples_options=[20],
        max_samples=60,
    )
    job = validation_store.create_validation_job(
        method="holdout_validation_job_v1",
        divisions=config.divisions,
        training_seasons=config.training_seasons,
        validation_seasons=config.validation_seasons,
        config=config.to_store_config(),
        db_path=db_path,
    )

    validation_store.mark_validation_job_finished(
        job["job_id"],
        status="completed",
        result_summary={
            "evaluated_count": 150,
            "bet_count": 70,
            "roi": -0.1,
            "log_loss_diff": 0.03,
            "failed_leagues": 0,
        },
        db_path=db_path,
    )

    loaded = validation_store.get_validation_job(job["job_id"], db_path=db_path)

    assert loaded is not None
    assert loaded["result_summary"]["verdict"]["status"] == "model_underperforms_market"
    assert "暂停推荐发布" in loaded["result_summary"]["verdict"]["next_action"]
    assert loaded["result_summary"]["metric_scope"]["probability_market"] == "moneyline_1x2"
    assert loaded["result_summary"]["metric_scope"]["asian_handicap_specific"] is False
    assert "不是亚盘专属验证" in loaded["result_summary"]["metric_scope"]["warning"]
    assert loaded["result_summary"]["asian_handicap_validation"]["status"] == "missing"
    assert loaded["result_summary"]["asian_handicap_validation"]["sample_gate"]["passed"] is False


def test_holdout_summary_diagnoses_model_underperforming_market():
    summary = validation_service._aggregate_job_summary(
        {
            "progress": {"total_leagues": 1, "completed_leagues": 1, "failed_leagues": 0},
            "league_results": [
                {
                    "status": "succeeded",
                    "result": {
                        "calibrated_validation_result": {
                            "evaluated_count": 160,
                            "bet_count": 70,
                            "profit": -8.0,
                            "model_log_loss_1x2": 0.62,
                            "market_log_loss_1x2": 0.58,
                            "model_brier_score_1x2": 0.24,
                            "market_brier_score_1x2": 0.22,
                            "asian_handicap_validation": {
                                "market": "asian_handicap",
                                "available_count": 120,
                                "evaluated_count": 110,
                                "bet_count": 30,
                                "profit": 3.0,
                                "roi": 0.1,
                                "hit_count": 16,
                                "push_count": 2,
                                "loss_count": 12,
                                "result_counts": {"win": 16, "push": 2, "loss": 12},
                            },
                        }
                    },
                }
            ],
        }
    )

    assert summary["log_loss_diff"] == 0.04
    assert summary["metric_scope"]["probability_market"] == "moneyline_1x2"
    assert summary["metric_scope"]["asian_handicap_specific"] is False
    assert summary["metric_scope"]["asian_handicap_evaluated_count"] == 110
    assert "不是亚盘专属验证" in summary["metric_scope"]["warning"]
    assert summary["asian_handicap_validation"]["market"] == "asian_handicap"
    assert summary["asian_handicap_validation"]["bet_count"] == 30
    assert summary["asian_handicap_validation"]["roi"] == 0.1
    assert summary["asian_handicap_validation"]["status"] == "insufficient_sample"
    assert summary["verdict"]["status"] == "model_underperforms_market"
    assert summary["verdict"]["tone"] == "bad"
    assert "跑输市场" in summary["verdict"]["title"]
    assert "暂停推荐发布" in summary["verdict"]["next_action"]


def test_validation_job_league_results_include_runtime_diagnostics(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    config = validation_service.HoldoutValidationJobConfig(divisions=["E0"], max_samples=1)
    job = validation_store.create_validation_job(
        method="holdout_validation_job_v1",
        divisions=config.divisions,
        training_seasons=config.training_seasons,
        validation_seasons=config.validation_seasons,
        config=config.to_store_config(),
        db_path=db_path,
    )

    validation_store.mark_validation_job_running(job["job_id"], db_path=db_path)
    validation_store.mark_validation_league_running(
        job["job_id"],
        division="E0",
        db_path=db_path,
    )
    validation_store.touch_validation_job_run(
        job["job_id"],
        division="E0",
        db_path=db_path,
    )

    loaded = validation_store.get_validation_job(job["job_id"], db_path=db_path)

    assert loaded is not None
    league = loaded["league_results"][0]
    assert league["runtime"]["state"] == "running"
    assert league["runtime"]["is_running"] is True
    assert league["runtime"]["run_seconds"] is not None
    assert league["runtime"]["updated_age_seconds"] is not None
    assert league["runtime"]["heartbeat_age_seconds"] is not None
    assert loaded["execution_health"]["heartbeat_age_seconds"] is not None


def test_holdout_summary_marks_watchlist_only_after_market_and_roi_pass():
    summary = validation_service._aggregate_job_summary(
        {
            "progress": {"total_leagues": 1, "completed_leagues": 1, "failed_leagues": 0},
            "league_results": [
                {
                    "status": "succeeded",
                    "result": {
                        "calibrated_validation_result": {
                            "evaluated_count": 180,
                            "bet_count": 80,
                            "profit": 6.4,
                            "model_log_loss_1x2": 0.54,
                            "market_log_loss_1x2": 0.58,
                            "model_brier_score_1x2": 0.21,
                            "market_brier_score_1x2": 0.23,
                        }
                    },
                }
            ],
        }
    )

    assert summary["log_loss_diff"] == -0.04
    assert summary["roi"] == 0.08
    assert summary["verdict"]["status"] == "watchlist_candidate"
    assert summary["verdict"]["tone"] == "good"
    assert "观察候选" in summary["verdict"]["next_action"]


def test_validation_job_store_cancels_pending_and_running_leagues(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    config = HoldoutValidationJobConfig(
        divisions=["E0", "SP1"],
        training_seasons=["2122"],
        validation_seasons=["2223"],
        edge_thresholds=[0.03],
        min_training_samples_options=[20],
        max_samples=60,
    )
    job = validation_store.create_validation_job(
        method="holdout_validation_job_v1",
        divisions=config.divisions,
        training_seasons=config.training_seasons,
        validation_seasons=config.validation_seasons,
        config=config.to_store_config(),
        db_path=db_path,
    )
    validation_store.mark_validation_job_running(job["job_id"], db_path=db_path)
    validation_store.mark_validation_league_running(job["job_id"], division="E0", db_path=db_path)

    cancelled = validation_store.cancel_validation_job(job["job_id"], db_path=db_path)

    assert cancelled is not None
    assert cancelled["status"] == "cancelled"
    assert cancelled["progress"]["cancelled_leagues"] == 2
    assert cancelled["progress"]["pending_leagues"] == 0
    assert {row["status"] for row in cancelled["league_results"]} == {"cancelled"}
    assert cancelled["finished_at_utc"] is not None


def test_validation_job_service_uses_cache_and_resumes_failed_league(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    calls: list[str] = []

    async def fake_holdout(**kwargs):
        division = kwargs["divisions"][0]
        calls.append(division)
        item = {
            "division": division,
            "league": division,
            "validation_result": {
                "division": division,
                "evaluated_count": 10,
                "bet_count": 5,
                "profit": 1.0,
                "roi": 0.2,
                "model_log_loss_1x2": 0.5,
                "market_log_loss_1x2": 0.55,
                "model_brier_score_1x2": 0.2,
                "market_brier_score_1x2": 0.24,
            },
            "calibrated_validation_result": {
                "division": division,
                "evaluated_count": 10,
                "bet_count": 5,
                "profit": 1.0,
                "roi": 0.2,
                "model_log_loss_1x2": 0.5,
                "market_log_loss_1x2": 0.55,
                "model_brier_score_1x2": 0.2,
                "market_brier_score_1x2": 0.24,
            },
        }
        return {"status": "ok", "division_results": [item], "holdout_readiness": {"status": "watchlist"}}

    monkeypatch.setattr("football_data_mcp.services.validation_service.backtest.run_holdout_validation", fake_holdout)
    service = ValidationJobService(db_path=db_path)
    config = HoldoutValidationJobConfig(
        divisions=["E0", "SP1"],
        training_seasons=["2122"],
        validation_seasons=["2223"],
        edge_thresholds=[0.03],
        min_training_samples_options=[20],
        max_samples=60,
    )

    job = service.create_or_resume_holdout_job(config)
    completed = asyncio.run(service.run_holdout_job_inline(job["job_id"]))
    rerun = service.create_or_resume_holdout_job(config)
    completed_again = asyncio.run(service.run_holdout_job_inline(rerun["job_id"]))

    assert calls == ["E0", "SP1"]
    assert completed["status"] == "completed"
    assert completed["progress"]["completed_leagues"] == 2
    assert completed["result_summary"]["log_loss_diff"] == -0.05
    assert completed_again["progress"]["completed_leagues"] == 2
    assert {row["cache_hit"] for row in completed_again["league_results"]} == {True}


def test_validation_job_heartbeat_updates_while_division_blocks_event_loop(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")

    async def fake_holdout(**kwargs):
        division = kwargs["divisions"][0]
        time.sleep(0.05)
        item = {
            "division": division,
            "league": division,
            "validation_result": {
                "division": division,
                "evaluated_count": 10,
                "bet_count": 5,
                "profit": 1.0,
                "roi": 0.2,
                "model_log_loss_1x2": 0.5,
                "market_log_loss_1x2": 0.55,
                "model_brier_score_1x2": 0.2,
                "market_brier_score_1x2": 0.24,
            },
            "calibrated_validation_result": {
                "division": division,
                "evaluated_count": 10,
                "bet_count": 5,
                "profit": 1.0,
                "roi": 0.2,
                "model_log_loss_1x2": 0.5,
                "market_log_loss_1x2": 0.55,
                "model_brier_score_1x2": 0.2,
                "market_brier_score_1x2": 0.24,
            },
        }
        return {"status": "ok", "division_results": [item], "holdout_readiness": {"status": "watchlist"}}

    monkeypatch.setattr("football_data_mcp.services.validation_service.backtest.run_holdout_validation", fake_holdout)
    service = ValidationJobService(
        db_path=db_path,
        running_job_stale_after_seconds=60,
        running_job_heartbeat_interval_seconds=0.01,
    )
    config = HoldoutValidationJobConfig(
        divisions=["E0"],
        training_seasons=["2122"],
        validation_seasons=["2223"],
        edge_thresholds=[0.03],
        min_training_samples_options=[20],
        max_samples=60,
    )
    job = service.create_or_resume_holdout_job(config)

    completed = asyncio.run(service.run_holdout_job_inline(job["job_id"]))

    assert completed["status"] == "completed"
    assert completed["runner_heartbeat_at_utc"] is not None
    assert completed["started_at_utc"] != completed["runner_heartbeat_at_utc"]


def test_validation_job_service_does_not_run_cancelled_job(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    calls: list[str] = []

    async def fake_holdout(**kwargs):
        calls.append(kwargs["divisions"][0])
        return {"status": "ok", "division_results": []}

    monkeypatch.setattr("football_data_mcp.services.validation_service.backtest.run_holdout_validation", fake_holdout)
    service = ValidationJobService(db_path=db_path)
    config = HoldoutValidationJobConfig(
        divisions=["E0"],
        training_seasons=["2122"],
        validation_seasons=["2223"],
        edge_thresholds=[0.03],
        min_training_samples_options=[20],
        max_samples=60,
    )
    job = service.create_or_resume_holdout_job(config)

    cancelled = service.cancel_job(job["job_id"])
    completed = asyncio.run(service.run_holdout_job_inline(job["job_id"]))

    assert cancelled["status"] == "cancelled"
    assert completed["status"] == "cancelled"
    assert calls == []


def test_validation_job_service_does_not_duplicate_active_running_job(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    calls: list[str] = []

    async def fake_holdout(**kwargs):
        calls.append(kwargs["divisions"][0])
        return {"status": "ok", "division_results": []}

    monkeypatch.setattr("football_data_mcp.services.validation_service.backtest.run_holdout_validation", fake_holdout)
    service = ValidationJobService(db_path=db_path, running_job_stale_after_seconds=3600)
    config = HoldoutValidationJobConfig(
        divisions=["E0"],
        training_seasons=["2122"],
        validation_seasons=["2223"],
        edge_thresholds=[0.03],
        min_training_samples_options=[20],
        max_samples=60,
    )
    job = service.create_or_resume_holdout_job(config)
    validation_store.mark_validation_job_running(job["job_id"], db_path=db_path)
    validation_store.mark_validation_league_running(job["job_id"], division="E0", db_path=db_path)

    current = asyncio.run(service.run_holdout_job_inline(job["job_id"]))

    assert current["status"] == "running"
    assert current["progress"]["running_leagues"] == 1
    assert calls == []


def test_validation_job_service_recovers_stale_running_job(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    calls: list[str] = []

    async def fake_holdout(**kwargs):
        division = kwargs["divisions"][0]
        calls.append(division)
        item = {
            "division": division,
            "league": division,
            "validation_result": {
                "division": division,
                "evaluated_count": 10,
                "bet_count": 5,
                "profit": 1.0,
                "roi": 0.2,
                "model_log_loss_1x2": 0.5,
                "market_log_loss_1x2": 0.55,
                "model_brier_score_1x2": 0.2,
                "market_brier_score_1x2": 0.24,
            },
            "calibrated_validation_result": {
                "division": division,
                "evaluated_count": 10,
                "bet_count": 5,
                "profit": 1.0,
                "roi": 0.2,
                "model_log_loss_1x2": 0.5,
                "market_log_loss_1x2": 0.55,
                "model_brier_score_1x2": 0.2,
                "market_brier_score_1x2": 0.24,
            },
        }
        return {"status": "ok", "division_results": [item], "holdout_readiness": {"status": "watchlist"}}

    monkeypatch.setattr("football_data_mcp.services.validation_service.backtest.run_holdout_validation", fake_holdout)
    service = ValidationJobService(db_path=db_path, running_job_stale_after_seconds=60)
    config = HoldoutValidationJobConfig(
        divisions=["E0", "SP1"],
        training_seasons=["2122"],
        validation_seasons=["2223"],
        edge_thresholds=[0.03],
        min_training_samples_options=[20],
        max_samples=60,
    )
    job = service.create_or_resume_holdout_job(config)
    validation_store.mark_validation_job_running(job["job_id"], db_path=db_path)
    validation_store.mark_validation_league_running(job["job_id"], division="E0", db_path=db_path)
    stale_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE model_validation_jobs SET updated_at_utc = ? WHERE job_id = ?",
            (stale_at, job["job_id"]),
        )
        conn.execute(
            "UPDATE model_validation_league_results SET updated_at_utc = ? WHERE job_id = ? AND division = 'E0'",
            (stale_at, job["job_id"]),
        )
        conn.commit()

    completed = asyncio.run(service.run_holdout_job_inline(job["job_id"]))

    assert completed["status"] == "completed"
    assert completed["progress"]["completed_leagues"] == 2
    assert completed["attempt_count"] == 1
    assert completed["last_claim_reason"] == "recovered_stale_runner"
    assert completed["recovered_at_utc"] is not None
    assert completed["runner_heartbeat_at_utc"] is not None
    assert calls == ["E0", "SP1"]
    assert {row["status"] for row in completed["league_results"]} == {"succeeded"}


def test_validation_job_service_heartbeat_prevents_false_stale_takeover(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    calls: list[str] = []

    async def scenario() -> None:
        started = asyncio.Event()
        release = asyncio.Event()

        async def fake_holdout(**kwargs):
            division = kwargs["divisions"][0]
            calls.append(division)
            started.set()
            await release.wait()
            item = {
                "division": division,
                "league": division,
                "validation_result": {
                    "division": division,
                    "evaluated_count": 10,
                    "bet_count": 5,
                    "profit": 1.0,
                    "roi": 0.2,
                    "model_log_loss_1x2": 0.5,
                    "market_log_loss_1x2": 0.55,
                    "model_brier_score_1x2": 0.2,
                    "market_brier_score_1x2": 0.24,
                },
                "calibrated_validation_result": {
                    "division": division,
                    "evaluated_count": 10,
                    "bet_count": 5,
                    "profit": 1.0,
                    "roi": 0.2,
                    "model_log_loss_1x2": 0.5,
                    "market_log_loss_1x2": 0.55,
                    "model_brier_score_1x2": 0.2,
                    "market_brier_score_1x2": 0.24,
                },
            }
            return {"status": "ok", "division_results": [item], "holdout_readiness": {"status": "watchlist"}}

        monkeypatch.setattr("football_data_mcp.services.validation_service.backtest.run_holdout_validation", fake_holdout)
        service = ValidationJobService(
            db_path=db_path,
            running_job_stale_after_seconds=60,
            running_job_heartbeat_interval_seconds=0.01,
        )
        config = HoldoutValidationJobConfig(
            divisions=["E0"],
            training_seasons=["2122"],
            validation_seasons=["2223"],
            edge_thresholds=[0.03],
            min_training_samples_options=[20],
            max_samples=60,
        )
        job = service.create_or_resume_holdout_job(config)
        task = asyncio.create_task(service.run_holdout_job_inline(job["job_id"]))
        await asyncio.wait_for(started.wait(), timeout=1)

        stale_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        with sqlite3.connect(db_path) as conn:
            conn.execute("UPDATE model_validation_jobs SET updated_at_utc = ? WHERE job_id = ?", (stale_at, job["job_id"]))
            conn.execute(
                "UPDATE model_validation_league_results SET updated_at_utc = ? WHERE job_id = ? AND division = 'E0'",
                (stale_at, job["job_id"]),
            )
            conn.commit()

        await asyncio.sleep(0.05)
        duplicate = await service.run_holdout_job_inline(job["job_id"])

        release.set()
        completed = await asyncio.wait_for(task, timeout=1)

        assert duplicate["status"] == "running"
        assert duplicate["progress"]["running_leagues"] == 1
        assert completed["status"] == "completed"
        assert calls == ["E0"]

    asyncio.run(scenario())


def test_validation_job_service_stale_runner_cannot_overwrite_recovered_runner(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    calls: list[str] = []

    async def scenario() -> None:
        old_started = asyncio.Event()
        new_finished = asyncio.Event()
        release_old = asyncio.Event()

        def result_for(division: str, marker: str, profit: float) -> dict:
            return {
                "division": division,
                "league": marker,
                "validation_result": {
                    "division": division,
                    "evaluated_count": 10,
                    "bet_count": 5,
                    "profit": profit,
                    "roi": profit / 5,
                    "model_log_loss_1x2": 0.5,
                    "market_log_loss_1x2": 0.55,
                    "model_brier_score_1x2": 0.2,
                    "market_brier_score_1x2": 0.24,
                },
                "calibrated_validation_result": {
                    "division": division,
                    "evaluated_count": 10,
                    "bet_count": 5,
                    "profit": profit,
                    "roi": profit / 5,
                    "model_log_loss_1x2": 0.5,
                    "market_log_loss_1x2": 0.55,
                    "model_brier_score_1x2": 0.2,
                    "market_brier_score_1x2": 0.24,
                },
            }

        async def fake_holdout(**kwargs):
            division = kwargs["divisions"][0]
            call_number = len(calls)
            if call_number == 0:
                calls.append("old")
                old_started.set()
                await release_old.wait()
                item = result_for(division, "old-runner", -3.0)
            else:
                calls.append("new")
                item = result_for(division, "new-runner", 4.0)
                new_finished.set()
            return {"status": "ok", "division_results": [item], "holdout_readiness": {"status": "watchlist"}}

        monkeypatch.setattr("football_data_mcp.services.validation_service.backtest.run_holdout_validation", fake_holdout)
        service = ValidationJobService(
            db_path=db_path,
            running_job_stale_after_seconds=60,
            running_job_heartbeat_interval_seconds=999,
        )
        config = HoldoutValidationJobConfig(
            divisions=["E0"],
            training_seasons=["2122"],
            validation_seasons=["2223"],
            edge_thresholds=[0.03],
            min_training_samples_options=[20],
            max_samples=60,
        )
        job = service.create_or_resume_holdout_job(config)
        old_task = asyncio.create_task(service.run_holdout_job_inline(job["job_id"]))
        await asyncio.wait_for(old_started.wait(), timeout=1)

        stale_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        with sqlite3.connect(db_path) as conn:
            conn.execute("UPDATE model_validation_jobs SET updated_at_utc = ? WHERE job_id = ?", (stale_at, job["job_id"]))
            conn.execute(
                "UPDATE model_validation_league_results SET updated_at_utc = ? WHERE job_id = ? AND division = 'E0'",
                (stale_at, job["job_id"]),
            )
            conn.commit()

        new_completed = await service.run_holdout_job_inline(job["job_id"])
        await asyncio.wait_for(new_finished.wait(), timeout=1)
        release_old.set()
        await asyncio.wait_for(old_task, timeout=1)

        final_job = validation_store.get_validation_job(job["job_id"], db_path=db_path)
        assert new_completed["status"] == "completed"
        assert final_job is not None
        assert calls == ["old", "new"]
        assert final_job["league_results"][0]["league"] == "new-runner"
        assert final_job["league_results"][0]["result"]["calibrated_validation_result"]["profit"] == 4.0
        assert final_job["result_summary"]["profit"] == 4.0

    asyncio.run(scenario())


def test_validation_job_service_retries_from_failed_league(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    calls: list[str] = []
    fail_sp1_once = True

    async def fake_holdout(**kwargs):
        nonlocal fail_sp1_once
        division = kwargs["divisions"][0]
        calls.append(division)
        if division == "SP1" and fail_sp1_once:
            fail_sp1_once = False
            raise RuntimeError("temporary SP1 failure")
        item = {
            "division": division,
            "league": division,
            "validation_result": {
                "division": division,
                "evaluated_count": 10,
                "bet_count": 5,
                "profit": 1.0,
                "roi": 0.2,
                "model_log_loss_1x2": 0.5,
                "market_log_loss_1x2": 0.55,
                "model_brier_score_1x2": 0.2,
                "market_brier_score_1x2": 0.24,
            },
            "calibrated_validation_result": {
                "division": division,
                "evaluated_count": 10,
                "bet_count": 5,
                "profit": 1.0,
                "roi": 0.2,
                "model_log_loss_1x2": 0.5,
                "market_log_loss_1x2": 0.55,
                "model_brier_score_1x2": 0.2,
                "market_brier_score_1x2": 0.24,
            },
        }
        return {"status": "ok", "division_results": [item], "holdout_readiness": {"status": "watchlist"}}

    monkeypatch.setattr("football_data_mcp.services.validation_service.backtest.run_holdout_validation", fake_holdout)
    service = ValidationJobService(db_path=db_path)
    config = HoldoutValidationJobConfig(
        divisions=["E0", "SP1"],
        training_seasons=["2122"],
        validation_seasons=["2223"],
        edge_thresholds=[0.03],
        min_training_samples_options=[20],
        max_samples=60,
    )
    job = service.create_or_resume_holdout_job(config)
    failed = asyncio.run(service.run_holdout_job_inline(job["job_id"]))

    retry_job = asyncio.run(service.retry_job_async(job["job_id"], start_background=False))
    completed = asyncio.run(service.run_holdout_job_inline(job["job_id"]))

    assert failed["status"] == "failed"
    assert failed["attempt_count"] == 1
    assert failed["failure_summary"]["failed_count"] == 1
    assert failed["failure_summary"]["recoverable"] is True
    assert failed["failure_summary"]["failed_leagues"][0]["division"] == "SP1"
    assert "temporary SP1 failure" in failed["failure_summary"]["latest_error"]
    assert retry_job["status"] == "pending"
    assert retry_job["retry_count"] == 1
    assert retry_job["last_retry_at_utc"] is not None
    assert completed["status"] == "completed"
    assert completed["attempt_count"] == 2
    assert completed["retry_count"] == 1
    assert completed["failure_summary"]["failed_count"] == 0
    event_types = [event["event_type"] for event in completed["events"]]
    assert event_types.count("job_claimed") == 2
    assert "job_retry_requested" in event_types
    assert "league_failed" in event_types
    assert event_types[-1] == "job_completed"
    assert calls == ["E0", "SP1", "SP1"]
    assert {row["status"] for row in completed["league_results"]} == {"succeeded"}


def test_validation_job_service_can_start_via_injected_queue(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    started: list[str] = []

    class FakeStarter:
        async def start_holdout_validation_job(self, job_id: str):
            started.append(job_id)
            from football_data_mcp.services.task_queue import ValidationJobStartResult

            return ValidationJobStartResult(backend="arq", queue_job_id=f"queue:{job_id}")

    service = ValidationJobService(db_path=db_path, job_starter=FakeStarter())
    config = HoldoutValidationJobConfig(
        divisions=["E0"],
        training_seasons=["2122"],
        validation_seasons=["2223"],
        edge_thresholds=[0.03],
        min_training_samples_options=[20],
        max_samples=10,
    )

    job = asyncio.run(service.create_or_resume_holdout_job_async(config, start_background=True))

    assert started == [job["job_id"]]
    assert job["status"] == "pending"
    assert job["progress"]["total_leagues"] == 1
    assert job["queue_backend"] == "arq"
    assert job["queue_job_id"] == f"queue:{job['job_id']}"
    assert job["queued_at_utc"] is not None
    assert "arq" in job["queue_status_message"].lower()


def test_validation_job_claim_metadata_tracks_runner_attempts(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    config = HoldoutValidationJobConfig(
        divisions=["E0"],
        training_seasons=["2122"],
        validation_seasons=["2223"],
        edge_thresholds=[0.03],
        min_training_samples_options=[20],
        max_samples=10,
    )
    job = validation_store.create_validation_job(
        method="holdout_validation_job_v1",
        divisions=config.divisions,
        training_seasons=config.training_seasons,
        validation_seasons=config.validation_seasons,
        config=config.to_store_config(),
        db_path=db_path,
    )

    first_claim = validation_store.claim_validation_job_run(
        str(job["job_id"]),
        stale_after_seconds=60,
        runner_id="runner-a",
        db_path=db_path,
    )
    duplicate_claim = validation_store.claim_validation_job_run(
        str(job["job_id"]),
        stale_after_seconds=60,
        runner_id="runner-b",
        db_path=db_path,
    )

    first_job = first_claim["job"]
    duplicate_job = duplicate_claim["job"]
    assert first_claim["claimed"] is True
    assert first_job["attempt_count"] == 1
    assert first_job["last_claim_reason"] == "claimed"
    assert first_job["runner_heartbeat_at_utc"] is not None
    assert duplicate_claim["claimed"] is False
    assert duplicate_claim["reason"] == "already_running"
    assert duplicate_job["attempt_count"] == 1
    assert duplicate_job["runner_heartbeat_at_utc"] == first_job["runner_heartbeat_at_utc"]

import asyncio

from football_data_mcp import validation_store
from football_data_mcp.config import TaskQueueSettings
from football_data_mcp.services.task_queue import (
    ArqOddsSourceSyncJobStarter,
    ArqValidationJobStarter,
    FallbackOddsSourceSyncJobStarter,
    FallbackValidationJobStarter,
    task_queue_health_snapshot,
)
from football_data_mcp.services.validation_service import HoldoutValidationJobConfig, ValidationJobService
from football_data_mcp.workers import arq_worker


def test_arq_validation_job_starter_enqueues_holdout_job():
    calls: list[dict[str, object]] = []

    class FakeRedis:
        async def enqueue_job(self, function: str, *args: object, **kwargs: object) -> object:
            calls.append({"function": function, "args": args, "kwargs": kwargs})
            return object()

        async def aclose(self) -> None:
            calls.append({"function": "aclose", "args": (), "kwargs": {}})

    async def fake_create_pool(redis_settings: object, queue_name: str) -> FakeRedis:
        calls.append({"function": "create_pool", "args": (queue_name,), "kwargs": {}})
        return FakeRedis()

    settings = TaskQueueSettings(
        backend="arq",
        arq_redis_host="redis",
        arq_queue_name="football-data-test",
        fallback_to_thread=False,
    )
    starter = ArqValidationJobStarter(settings=settings, create_pool=fake_create_pool)

    start_result = asyncio.run(starter.start_holdout_validation_job("job-123"))

    assert start_result.backend == "arq"
    assert start_result.queue_job_id == "holdout-validation:job-123"
    assert calls[0] == {"function": "create_pool", "args": ("football-data-test",), "kwargs": {}}
    assert calls[1]["function"] == "run_holdout_validation_job"
    assert calls[1]["args"] == ("job-123",)
    assert calls[1]["kwargs"] == {
        "_job_id": "holdout-validation:job-123",
        "_queue_name": "football-data-test",
    }
    assert calls[2]["function"] == "aclose"


def test_arq_odds_source_sync_job_starter_enqueues_oddsportal_payload():
    calls: list[dict[str, object]] = []

    class FakeRedis:
        async def enqueue_job(self, function: str, *args: object, **kwargs: object) -> object:
            calls.append({"function": function, "args": args, "kwargs": kwargs})
            return object()

        async def aclose(self) -> None:
            calls.append({"function": "aclose", "args": (), "kwargs": {}})

    async def fake_create_pool(redis_settings: object, queue_name: str) -> FakeRedis:
        calls.append({"function": "create_pool", "args": (queue_name,), "kwargs": {}})
        return FakeRedis()

    settings = TaskQueueSettings(
        backend="arq",
        arq_redis_host="redis",
        arq_queue_name="football-data-test",
        fallback_to_thread=False,
    )
    starter = ArqOddsSourceSyncJobStarter(settings=settings, create_pool=fake_create_pool)

    start_result = asyncio.run(
        starter.start_oddsportal_snapshot_sync_job(
            "odds-job-123",
            {"event_urls": ["https://www.oddsportal.com/football/h2h/example/#abc"], "markets": ["asian_handicap"]},
        )
    )

    assert start_result.backend == "arq"
    assert start_result.queue_job_id == "oddsportal-sync:odds-job-123"
    assert calls[0] == {"function": "create_pool", "args": ("football-data-test",), "kwargs": {}}
    assert calls[1]["function"] == "run_oddsportal_snapshot_sync_job"
    assert calls[1]["args"] == (
        {
            "event_urls": ["https://www.oddsportal.com/football/h2h/example/#abc"],
            "markets": ["asian_handicap"],
            "job_id": "odds-job-123",
        },
    )
    assert calls[1]["kwargs"] == {
        "_job_id": "oddsportal-sync:odds-job-123",
        "_queue_name": "football-data-test",
    }
    assert calls[2]["function"] == "aclose"


def test_fallback_validation_job_starter_uses_thread_when_arq_enqueue_fails():
    started: list[str] = []

    class BrokenStarter:
        async def start_holdout_validation_job(self, job_id: str) -> str:
            raise RuntimeError(f"redis unavailable for {job_id}")

    class ThreadStarter:
        async def start_holdout_validation_job(self, job_id: str) -> str:
            started.append(job_id)
            return "thread"

    starter = FallbackValidationJobStarter(primary=BrokenStarter(), fallback=ThreadStarter())

    start_result = asyncio.run(starter.start_holdout_validation_job("job-456"))

    assert start_result.backend == "thread"
    assert start_result.queue_job_id is None
    assert started == ["job-456"]


def test_fallback_odds_source_sync_job_starter_uses_thread_when_arq_enqueue_fails():
    started: list[tuple[str, dict[str, object]]] = []

    class BrokenStarter:
        async def start_oddsportal_snapshot_sync_job(self, job_id: str, payload: dict[str, object]) -> str:
            raise RuntimeError(f"redis unavailable for {job_id}")

    class ThreadStarter:
        async def start_oddsportal_snapshot_sync_job(self, job_id: str, payload: dict[str, object]) -> str:
            started.append((job_id, payload))
            return "thread"

    starter = FallbackOddsSourceSyncJobStarter(primary=BrokenStarter(), fallback=ThreadStarter())

    start_result = asyncio.run(
        starter.start_oddsportal_snapshot_sync_job("odds-job-456", {"markets": ["asian_handicap"]})
    )

    assert start_result.backend == "thread"
    assert start_result.queue_job_id is None
    assert started == [("odds-job-456", {"markets": ["asian_handicap"], "job_id": "odds-job-456"})]


def test_task_queue_health_reports_thread_backend():
    settings = TaskQueueSettings(backend="thread")

    health = task_queue_health_snapshot(settings)

    assert health["status"] == "ok"
    assert health["backend"] == "thread"
    assert health["worker_healthy"] is None


def test_task_queue_health_reports_arq_worker_health():
    closed: list[bool] = []

    class FakeRedis:
        def ping(self) -> bool:
            return True

        def zcard(self, key: str) -> int:
            assert key == "football-data-test"
            return 2

        def get(self, key: str) -> bytes:
            assert key == "football-data-test:health-check"
            return b"healthy"

        def ttl(self, key: str) -> int:
            assert key == "football-data-test:health-check"
            return 300

        def close(self) -> None:
            closed.append(True)

    settings = TaskQueueSettings(backend="arq", arq_queue_name="football-data-test")

    health = task_queue_health_snapshot(settings, redis_client_factory=lambda _settings: FakeRedis())

    assert health["status"] == "ok"
    assert health["backend"] == "arq"
    assert health["redis_reachable"] is True
    assert health["queued_jobs"] == 2
    assert health["worker_healthy"] is True
    assert health["worker_health"] == "healthy"
    assert health["worker_health_ttl_seconds"] == 300
    assert health["validation_job_stale_after_seconds"] == settings.validation_job_stale_after_seconds
    assert closed == [True]


def test_task_queue_health_degrades_worker_health_without_ttl():
    class FakeRedis:
        def ping(self) -> bool:
            return True

        def zcard(self, key: str) -> int:
            assert key == "football-data-test"
            return 0

        def get(self, key: str) -> bytes:
            assert key == "football-data-test:health-check"
            return b"old health"

        def ttl(self, key: str) -> int:
            assert key == "football-data-test:health-check"
            return -1

        def close(self) -> None:
            pass

    settings = TaskQueueSettings(backend="arq", arq_queue_name="football-data-test")

    health = task_queue_health_snapshot(settings, redis_client_factory=lambda _settings: FakeRedis())

    assert health["status"] == "degraded"
    assert health["worker_healthy"] is False
    assert health["worker_health_ttl_seconds"] == -1
    assert "没有过期时间" in health["detail"]


def test_task_queue_health_turns_redis_errors_into_error_status():
    class BrokenRedis:
        def ping(self) -> bool:
            raise RuntimeError("redis down")

        def close(self) -> None:
            pass

    settings = TaskQueueSettings(backend="arq", arq_queue_name="football-data-test")

    health = task_queue_health_snapshot(settings, redis_client_factory=lambda _settings: BrokenRedis())

    assert health["status"] == "error"
    assert health["redis_reachable"] is False
    assert "redis down" in health["detail"]


def test_arq_worker_entrypoint_runs_validation_job_and_persists_progress(monkeypatch, tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    monkeypatch.setenv("FOOTBALL_DATA_LEARNING_DB", db_path)
    calls: list[str] = []

    async def fake_holdout(**kwargs):
        division = kwargs["divisions"][0]
        calls.append(division)
        item = {
            "division": division,
            "league": division,
            "validation_result": {
                "division": division,
                "evaluated_count": 12,
                "bet_count": 6,
                "profit": 2.4,
                "roi": 0.4,
                "model_log_loss_1x2": 0.5,
                "market_log_loss_1x2": 0.55,
                "model_brier_score_1x2": 0.2,
                "market_brier_score_1x2": 0.24,
            },
            "calibrated_validation_result": {
                "division": division,
                "evaluated_count": 12,
                "bet_count": 6,
                "profit": 2.4,
                "roi": 0.4,
                "model_log_loss_1x2": 0.5,
                "market_log_loss_1x2": 0.55,
                "model_brier_score_1x2": 0.2,
                "market_brier_score_1x2": 0.24,
            },
        }
        return {"status": "ok", "division_results": [item], "holdout_readiness": {"status": "watchlist"}}

    monkeypatch.setattr("football_data_mcp.services.validation_service.backtest.run_holdout_validation", fake_holdout)
    service = ValidationJobService()
    config = HoldoutValidationJobConfig(
        divisions=["E0", "SP1"],
        training_seasons=["2122"],
        validation_seasons=["2223"],
        edge_thresholds=[0.03],
        min_training_samples_options=[20],
        max_samples=20,
    )
    job = service.create_or_resume_holdout_job(config, start_background=False)

    completed = asyncio.run(arq_worker.run_holdout_validation_job({"job_id": "arq-job-1"}, str(job["job_id"])))
    stored = validation_store.get_validation_job(str(job["job_id"]), db_path=db_path)

    assert completed["status"] == "completed"
    assert stored is not None
    assert stored["queue_job_id"] == "arq-job-1"
    assert stored["current_runner_id"]
    assert any(
        event["event_type"] == "worker_started" and event["metadata"]["queue_job_id"] == "arq-job-1"
        for event in stored["events"]
    )
    assert stored["progress"]["completed_leagues"] == 2
    assert stored["result_summary"]["profit"] == 4.8
    assert calls == ["E0", "SP1"]


def test_arq_worker_entrypoint_runs_oddsportal_snapshot_sync(monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_sync_oddsportal_odds_snapshots(**kwargs):
        calls.append(kwargs)
        return {
            "tool": "sync_oddsportal_odds_snapshots",
            "status": "ok",
            "saved_snapshot_count": 12,
        }

    monkeypatch.setattr(
        "football_data_mcp.workers.arq_worker.sources.sync_oddsportal_odds_snapshots",
        fake_sync_oddsportal_odds_snapshots,
    )
    payload = {
        "job_id": "odds-job-789",
        "event_urls": ["https://www.oddsportal.com/football/h2h/example/#abc"],
        "markets": ["asian_handicap"],
        "limit": 1,
        "force": True,
    }

    completed = asyncio.run(arq_worker.run_oddsportal_snapshot_sync_job({"job_id": "arq-odds-1"}, payload))

    assert completed["status"] == "ok"
    assert completed["job_id"] == "odds-job-789"
    assert completed["queue_job_id"] == "arq-odds-1"
    assert calls == [
        {
            "event_urls": ["https://www.oddsportal.com/football/h2h/example/#abc"],
            "markets": ["asian_handicap"],
            "limit": 1,
            "force": True,
            "job_id": "odds-job-789",
        }
    ]

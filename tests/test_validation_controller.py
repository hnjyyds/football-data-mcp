from __future__ import annotations

import asyncio
import json
from typing import Any

from starlette.requests import Request

from football_data_mcp import validation_store
from football_data_mcp.api.controllers import validation as validation_controller
from football_data_mcp.services.validation_service import HoldoutValidationJobConfig, ValidationJobService


def _json_request(path: str, payload: dict[str, Any], *, path_params: dict[str, str] | None = None) -> Request:
    body = json.dumps(payload).encode("utf-8")

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [(b"content-type", b"application/json")],
            "query_string": b"",
            "path_params": path_params or {},
        },
        receive,
    )


def test_holdout_validation_create_api_persists_job_and_enqueues_background_run(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    started: list[str] = []

    class FakeStarter:
        async def start_holdout_validation_job(self, job_id: str):
            started.append(job_id)
            from football_data_mcp.services.task_queue import ValidationJobStartResult

            return ValidationJobStartResult(backend="arq", queue_job_id=f"queue:{job_id}")

    def service_factory() -> ValidationJobService:
        return ValidationJobService(db_path=db_path, job_starter=FakeStarter())

    validation_controller.configure_validation_dependencies(service_factory=service_factory)
    try:
        response = asyncio.run(
            validation_controller.holdout_validation_jobs_api(
                _json_request(
                    "/api/validation/holdout/jobs",
                    {
                        "divisions": ["E0", "SP1"],
                        "training_seasons": ["2122"],
                        "validation_seasons": ["2223"],
                        "edge_thresholds": [0.03],
                        "min_training_samples_options": [20],
                        "max_samples": 20,
                        "start": True,
                    },
                )
            )
        )
    finally:
        validation_controller.configure_validation_dependencies()

    body = json.loads(response.body)

    assert response.status_code == 200
    assert body["status"] == "pending"
    assert body["progress"]["total_leagues"] == 2
    assert body["progress"]["pending_leagues"] == 2
    assert body["attempt_count"] == 0
    assert body["retry_count"] == 0
    assert body["failure_summary"]["failed_count"] == 0
    assert [event["event_type"] for event in body["events"]] == ["job_created", "job_queued"]
    assert body["queue_backend"] == "arq"
    assert body["queue_job_id"] == f"queue:{body['job_id']}"
    assert body["queued_at_utc"] is not None
    assert "arq" in body["queue_status_message"].lower()
    assert started == [body["job_id"]]


def test_holdout_validation_retry_api_resets_job_and_enqueues_resume(tmp_path):
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
        max_samples=20,
    )
    job = service.create_or_resume_holdout_job(config, start_background=False)
    validation_store.upsert_validation_league_result(
        str(job["job_id"]),
        division="E0",
        league="E0",
        status="failed",
        cache_key=config.cache_key_for_division("E0"),
        error="temporary data source failure",
        db_path=db_path,
    )
    validation_store.mark_validation_job_finished(
        str(job["job_id"]),
        status="failed",
        result_summary={"failed_leagues": 1},
        error="One or more league validations failed.",
        db_path=db_path,
    )

    def service_factory() -> ValidationJobService:
        return ValidationJobService(db_path=db_path, job_starter=FakeStarter())

    validation_controller.configure_validation_dependencies(service_factory=service_factory)
    try:
        response = asyncio.run(
            validation_controller.holdout_validation_retry_job_api(
                _json_request(
                    f"/api/validation/holdout/jobs/{job['job_id']}/retry",
                    {},
                    path_params={"job_id": str(job["job_id"])},
                )
            )
        )
    finally:
        validation_controller.configure_validation_dependencies()

    body = json.loads(response.body)

    assert response.status_code == 200
    assert body["job_id"] == job["job_id"]
    assert body["status"] == "pending"
    assert body["progress"]["pending_leagues"] == body["progress"]["total_leagues"]
    assert body["attempt_count"] == 0
    assert body["retry_count"] == 1
    assert body["last_retry_at_utc"] is not None
    assert body["failure_summary"]["recoverable"] is True
    assert body["events"][-2]["event_type"] == "job_retry_requested"
    assert body["events"][-1]["event_type"] == "job_queued"
    assert body["queue_backend"] == "arq"
    assert body["queue_job_id"] == f"queue:{job['job_id']}"
    assert body["queued_at_utc"] is not None
    assert "arq" in body["queue_status_message"].lower()
    assert started == [job["job_id"]]

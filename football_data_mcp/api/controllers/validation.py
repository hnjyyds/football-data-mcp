from __future__ import annotations

import json
import logging
from collections.abc import Callable
from urllib.parse import unquote

from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import Response

from football_data_mcp.api.controllers._helpers import api_error_response, headers_for, options_response, route
from football_data_mcp.api.registry import SupportsCustomRoute
from football_data_mcp.api.schemas.common import success_json
from football_data_mcp.api.schemas.validation import HoldoutValidationJobRequest, ValidationJobResponse
from football_data_mcp.core.errors import NotFoundError, RequestValidationAppError
from football_data_mcp.services.validation_service import HoldoutValidationJobConfig, ValidationJobService


logger = logging.getLogger("football_data_mcp.api.validation")
ValidationServiceFactory = Callable[[], ValidationJobService]
_validation_service_factory: ValidationServiceFactory = ValidationJobService


def configure_validation_dependencies(*, service_factory: ValidationServiceFactory | None = None) -> None:
    """Inject validation services for tests and alternate runtimes without coupling routes to infrastructure."""
    global _validation_service_factory
    _validation_service_factory = service_factory or ValidationJobService


def register(mcp: SupportsCustomRoute) -> list[dict[str, object]]:
    routes = [
        ("/api/validation/holdout/jobs", ["POST", "OPTIONS"], holdout_validation_jobs_api),
        ("/api/validation/holdout/jobs/latest", ["GET", "OPTIONS"], holdout_validation_latest_job_api),
        ("/api/validation/holdout/jobs/{job_id}", ["GET", "OPTIONS"], holdout_validation_job_api),
        ("/api/validation/holdout/jobs/{job_id}/cancel", ["POST", "OPTIONS"], holdout_validation_cancel_job_api),
        ("/api/validation/holdout/jobs/{job_id}/retry", ["POST", "OPTIONS"], holdout_validation_retry_job_api),
    ]
    for path, methods, handler in routes:
        mcp.custom_route(path, methods=methods, include_in_schema=False)(handler)
    return [route(path, methods) for path, methods, _ in routes]


async def holdout_validation_jobs_api(request: Request) -> Response:
    headers = headers_for(request, allow_methods="POST, OPTIONS")
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        try:
            payload = await request.json()
        except json.JSONDecodeError as exc:
            raise RequestValidationAppError(
                code="invalid_json_body",
                message="Request body must be valid JSON.",
                details={"reason": str(exc)},
            ) from exc
        try:
            parsed = HoldoutValidationJobRequest.model_validate(payload or {})
        except ValidationError as exc:
            raise RequestValidationAppError(
                code="request_validation_failed",
                message="Request body did not match the holdout validation job schema.",
                details={"errors": exc.errors()},
            ) from exc
        config = HoldoutValidationJobConfig(
            divisions=parsed.divisions,
            training_seasons=parsed.training_seasons,
            validation_seasons=parsed.validation_seasons,
            edge_thresholds=parsed.edge_thresholds,
            min_training_samples_options=parsed.min_training_samples_options,
            max_samples=parsed.max_samples,
            min_selection_bets=parsed.min_selection_bets,
            min_selection_evaluated=parsed.min_selection_evaluated,
            min_validation_bets=parsed.min_validation_bets,
            min_validation_evaluated=parsed.min_validation_evaluated,
            historical_rho_min_samples=parsed.historical_rho_min_samples,
            use_cache=parsed.use_cache,
        )
        job = await _validation_service_factory().create_or_resume_holdout_job_async(
            config,
            start_background=parsed.start,
            resume=parsed.resume,
        )
        logger.info("holdout_validation_job_api: job_id=%s status=%s", job.get("job_id"), job.get("status"))
        return success_json(ValidationJobResponse.model_validate(job), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)


async def holdout_validation_latest_job_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        job = _validation_service_factory().latest_job()
        if not job:
            raise NotFoundError(code="validation_job_not_found", message="No holdout validation job exists.")
        return success_json(ValidationJobResponse.model_validate(job), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)


async def holdout_validation_job_api(request: Request) -> Response:
    headers = headers_for(request)
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        job_id = unquote(request.path_params.get("job_id", ""))
        job = _validation_service_factory().get_job(job_id)
        if not job:
            raise NotFoundError(
                code="validation_job_not_found",
                message="Holdout validation job was not found.",
                details={"job_id": job_id},
            )
        return success_json(ValidationJobResponse.model_validate(job), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)


async def holdout_validation_cancel_job_api(request: Request) -> Response:
    headers = headers_for(request, allow_methods="POST, OPTIONS")
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        job_id = unquote(request.path_params.get("job_id", ""))
        try:
            job = _validation_service_factory().cancel_job(job_id)
        except ValueError as exc:
            raise NotFoundError(
                code="validation_job_not_found",
                message="Holdout validation job was not found.",
                details={"job_id": job_id},
            ) from exc
        return success_json(ValidationJobResponse.model_validate(job), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)


async def holdout_validation_retry_job_api(request: Request) -> Response:
    headers = headers_for(request, allow_methods="POST, OPTIONS")
    if request.method == "OPTIONS":
        return options_response(headers)
    try:
        job_id = unquote(request.path_params.get("job_id", ""))
        try:
            job = await _validation_service_factory().retry_job_async(job_id, start_background=True)
        except ValueError as exc:
            raise NotFoundError(
                code="validation_job_not_found",
                message="Holdout validation job was not found.",
                details={"job_id": job_id},
            ) from exc
        return success_json(ValidationJobResponse.model_validate(job), headers=headers)
    except Exception as exc:
        return api_error_response(exc, headers=headers)

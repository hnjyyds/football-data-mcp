from __future__ import annotations

import asyncio
import json

from starlette.requests import Request

from football_data_mcp import server


def _request(*, query_string: str = "") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/project",
            "headers": [],
            "query_string": query_string.encode("latin-1"),
            "path_params": {},
        }
    )


def test_project_controller_returns_layered_architecture_contract() -> None:
    response = asyncio.run(server.project_api(_request()))
    body = json.loads(response.body)

    assert response.status_code == 200
    assert body["status"] == "ok"
    assert body["name"] == "football-data-mcp"
    assert "project" in body["controllers"]
    assert [layer["name"] for layer in body["architecture"]] == ["api", "service", "repository", "core"]


def test_query_schema_validation_uses_unified_error_response() -> None:
    response = asyncio.run(server.fdo_matches_api(_request(query_string=f"date_from={'x' * 33}")))
    body = json.loads(response.body)

    assert response.status_code == 422
    assert body["status"] == "error"
    assert body["error"]["code"] == "request_validation_failed"
    assert "generated_at_utc" in body

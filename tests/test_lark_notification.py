from __future__ import annotations

import asyncio
import json
from typing import Any

from starlette.requests import Request

from football_data_mcp import learning_store
from football_data_mcp.api.controllers import dashboard as dashboard_controller
from football_data_mcp.config import LarkNotificationSettings
from football_data_mcp.services.lark_notification_service import (
    LarkNotificationService,
    build_lark_prediction_message,
)


class FakeDashboardService:
    async def match_detail(self, ledger_id: str) -> dict[str, Any]:
        return {
            "status": "ok",
            "record": {
                "ledger_id": ledger_id,
                "league": "测试联赛",
                "home_team": "主队",
                "away_team": "客队",
                "kickoff_utc_plus_8": "06/02 20:00",
                "selection": "主队 +0.25",
                "decimal_odds": 1.88,
                "model_probability": 0.57,
                "learned_probability": 0.55,
                "market_probability": 0.51,
                "edge": 0.04,
                "expected_multiplier": 1.034,
                "prediction_type_label": "观察样本",
                "recommendation": "condition_observe",
            },
            "evidence": {
                "prediction_diagnostic": {
                    "actionability_label": "观察样本",
                    "primary_reason": "正式推荐门禁未开放",
                }
            },
        }


def _post_request(path_params: dict[str, str]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/dashboard/match/recommendation%3A1/lark",
            "headers": [],
            "query_string": b"",
            "path_params": path_params,
        }
    )


def test_build_lark_prediction_message_labels_prediction_not_recommendation() -> None:
    message = build_lark_prediction_message(asyncio.run(FakeDashboardService().match_detail("recommendation:1")))

    assert "预测样本（非推荐）" in message.title
    assert "主队 vs 客队" in message.text
    assert "模型概率：57.0%" in message.text
    assert "不是推荐发布，不构成投注指令" in message.text


def test_lark_notification_service_posts_prediction_payload_without_changing_recommendation() -> None:
    posted: list[dict[str, Any]] = []

    def fake_post(url: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        posted.append({"url": url, "payload": payload, "timeout": timeout})
        return {"code": 0, "msg": "ok"}

    service = LarkNotificationService(
        settings=LarkNotificationSettings(webhook_url="https://open.larksuite.com/webhook/test", timeout_seconds=2),
        dashboard_service=FakeDashboardService(),  # type: ignore[arg-type]
        poster=fake_post,
    )

    result = asyncio.run(service.send_prediction("recommendation:1"))

    assert result["sent"] is True
    assert result["policy"]["prediction_only"] is True
    assert result["policy"]["not_recommendation"] is True
    assert posted[0]["url"] == "https://open.larksuite.com/webhook/test"
    assert posted[0]["timeout"] == 2
    assert posted[0]["payload"]["msg_type"] == "text"
    assert "预测样本（非推荐）" in posted[0]["payload"]["content"]["text"]


def test_lark_notification_service_auto_pushes_new_run_predictions_once(tmp_path) -> None:
    db_path = str(tmp_path / "learning.sqlite3")
    run_id = "auto-learning-test"
    learning_store.save_recommendation_records(
        [
            {
                "run_id": run_id,
                "tool": "shortlist_value_matches",
                "mode": "balanced_observation",
                "target_market": "asian_handicap",
                "match": {
                    "league": "测试联赛",
                    "home_team": "主队",
                    "away_team": "客队",
                    "kickoff_utc_plus_8": "06/02 20:00",
                },
                "best_candidate": {
                    "market": "asian_handicap",
                    "selection": "主队 +0.25",
                    "selection_key": "home_cover",
                    "line": 0.25,
                    "decimal_odds": 1.88,
                    "model_probability": 0.57,
                    "calibrated_probability": 0.55,
                    "market_probability": 0.51,
                    "edge": 0.04,
                    "expected_multiplier": 1.034,
                    "recommendation": "condition_observe",
                },
                "selection_confidence": {"calibrated_probability": 0.55},
                "risk_flags": [],
                "caution_flags": [],
            }
        ],
        db_path=db_path,
    )
    posted: list[dict[str, Any]] = []

    def fake_post(url: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        posted.append({"url": url, "payload": payload, "timeout": timeout})
        return {"code": 0, "msg": "ok"}

    service = LarkNotificationService(
        settings=LarkNotificationSettings(
            webhook_url="https://open.larksuite.com/webhook/test",
            timeout_seconds=2,
            auto_push_predictions=True,
            auto_push_limit=10,
        ),
        dashboard_service=FakeDashboardService(),  # type: ignore[arg-type]
        poster=fake_post,
    )

    first = asyncio.run(service.send_unsent_predictions_for_run(run_id, db_path=db_path))
    second = asyncio.run(service.send_unsent_predictions_for_run(run_id, db_path=db_path))
    deliveries = learning_store.list_notification_deliveries(
        db_path=db_path,
        channel="lark",
        notification_type="prediction",
    )

    assert first["status"] == "sent"
    assert first["sent_count"] == 1
    assert second["status"] == "skipped_all_duplicates"
    assert second["skipped_duplicate_count"] == 1
    assert len(posted) == 1
    assert deliveries[0]["status"] == "sent"
    assert deliveries[0]["attempt_count"] == 1


def test_dashboard_match_lark_api_uses_injected_service() -> None:
    class FakeLarkService:
        async def send_prediction(self, ledger_id: str) -> dict[str, Any]:
            return {
                "status": "ok",
                "tool": "lark_prediction_notification",
                "sent": True,
                "channel": "lark",
                "ledger_id": ledger_id,
            }

    dashboard_controller.configure_dashboard_dependencies(
        lark_notification_service_factory=lambda: FakeLarkService()  # type: ignore[return-value]
    )
    try:
        response = asyncio.run(
            dashboard_controller.dashboard_match_lark_api(
                _post_request({"ledger_id": "recommendation%3A1"})
            )
        )
    finally:
        dashboard_controller.configure_dashboard_dependencies()

    body = json.loads(response.body)
    assert response.status_code == 200
    assert body["tool"] == "lark_prediction_notification"
    assert body["sent"] is True
    assert body["ledger_id"] == "recommendation:1"

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from football_data_mcp import learning_store
from football_data_mcp.config import LarkNotificationSettings, load_lark_notification_settings
from football_data_mcp.core.errors import AppError, ErrorCategory, ServiceExecutionError
from football_data_mcp.services.dashboard_service import DashboardReadService


class LarkWebhookPoster(Protocol):
    def __call__(self, url: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        ...


class DashboardMatchDetailService(Protocol):
    async def match_detail(self, ledger_id: str) -> dict[str, Any]:
        ...


def _default_lark_post(url: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    response = httpx.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    try:
        body = response.json()
    except ValueError:
        return {"status_code": response.status_code, "raw": response.text[:500]}
    return body if isinstance(body, dict) else {"status_code": response.status_code, "body": body}


@dataclass(frozen=True)
class LarkPredictionMessage:
    title: str
    text: str


class LarkNotificationService:
    def __init__(
        self,
        *,
        settings: LarkNotificationSettings | None = None,
        dashboard_service: DashboardMatchDetailService | None = None,
        poster: LarkWebhookPoster | None = None,
    ) -> None:
        self._settings = settings or load_lark_notification_settings()
        self._dashboard_service = dashboard_service or DashboardReadService()
        self._poster = poster or _default_lark_post

    async def send_prediction(self, ledger_id: str, *, db_path: str | None = None) -> dict[str, Any]:
        webhook_url = self._settings.webhook_url.strip()
        if not webhook_url:
            raise AppError(
                code="lark_webhook_not_configured",
                message="Lark webhook is not configured.",
                status_code=400,
                category=ErrorCategory.CONFIGURATION,
                details={"env": "FOOTBALL_DATA_LARK_WEBHOOK_URL"},
            )
        detail = await self._match_detail(ledger_id, db_path=db_path)
        message = build_lark_prediction_message(detail)
        payload = _lark_text_payload(message.text, secret=self._settings.webhook_secret)
        try:
            response = await asyncio.to_thread(
                self._poster,
                webhook_url,
                payload,
                timeout=self._settings.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise ServiceExecutionError(
                code="lark_webhook_http_error",
                message="Lark webhook request failed.",
                details={"reason": str(exc)},
            ) from exc
        except Exception as exc:
            raise ServiceExecutionError(
                code="lark_webhook_send_failed",
                message="Lark prediction message could not be sent.",
                details={"reason": str(exc)},
            ) from exc
        return {
            "status": "ok",
            "tool": "lark_prediction_notification",
            "sent": True,
            "channel": "lark",
            "ledger_id": str(ledger_id),
            "message_title": message.title,
            "policy": {
                "prediction_only": True,
                "not_recommendation": True,
                "no_real_bet": True,
            },
            "lark_response": response,
        }

    async def send_unsent_predictions_for_run(
        self,
        run_id: str,
        *,
        db_path: str | None = None,
        include_shadow_predictions: bool = True,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Send newly persisted paper predictions for one run without duplicating old messages."""
        bounded_limit = max(0, int(limit if limit is not None else self._settings.auto_push_limit))
        summary: dict[str, Any] = {
            "enabled": bool(self._settings.auto_push_predictions),
            "channel": "lark",
            "notification_type": "prediction",
            "run_id": str(run_id or ""),
            "candidate_count": 0,
            "sent_count": 0,
            "skipped_duplicate_count": 0,
            "failed_count": 0,
            "limit": bounded_limit,
        }
        if not self._settings.auto_push_predictions:
            return {**summary, "status": "disabled"}
        if bounded_limit <= 0:
            return {**summary, "status": "skipped_limit_zero"}
        if not self._settings.webhook_url.strip():
            return {
                **summary,
                "status": "not_configured",
                "reason": "FOOTBALL_DATA_LARK_WEBHOOK_URL is empty",
            }

        ledger_ids = learning_store.list_prediction_ledger_ids_for_run(
            run_id,
            db_path=db_path,
            include_shadow_predictions=include_shadow_predictions,
            limit=bounded_limit,
            recommendation_allowlist=("condition_observe",),
        )
        summary["candidate_count"] = len(ledger_ids)
        if not ledger_ids:
            return {**summary, "status": "no_predictions"}

        sent_ledger_ids: list[str] = []
        failed_ledger_ids: list[str] = []
        for ledger_id in ledger_ids:
            reserved = learning_store.reserve_notification_delivery(
                channel="lark",
                notification_type="prediction",
                ledger_id=ledger_id,
                db_path=db_path,
            )
            if not reserved:
                summary["skipped_duplicate_count"] += 1
                continue
            try:
                result = await self.send_prediction(ledger_id, db_path=db_path)
            except Exception as exc:
                summary["failed_count"] += 1
                failed_ledger_ids.append(ledger_id)
                learning_store.complete_notification_delivery(
                    channel="lark",
                    notification_type="prediction",
                    ledger_id=ledger_id,
                    status="failed",
                    error=f"{type(exc).__name__}: {exc}",
                    db_path=db_path,
                )
                continue
            summary["sent_count"] += 1
            sent_ledger_ids.append(ledger_id)
            response = result.get("lark_response") if isinstance(result.get("lark_response"), dict) else {}
            learning_store.complete_notification_delivery(
                channel="lark",
                notification_type="prediction",
                ledger_id=ledger_id,
                status="sent",
                response=response,
                db_path=db_path,
            )

        status = "sent" if summary["sent_count"] else "skipped_all_duplicates"
        if summary["failed_count"] and summary["sent_count"]:
            status = "partial_failure"
        elif summary["failed_count"] and not summary["sent_count"]:
            status = "failed"
        return {
            **summary,
            "status": status,
            "sent_ledger_ids": sent_ledger_ids[:20],
            "failed_ledger_ids": failed_ledger_ids[:20],
        }

    async def _match_detail(self, ledger_id: str, *, db_path: str | None) -> dict[str, Any]:
        if db_path is None or not isinstance(self._dashboard_service, DashboardReadService):
            return await self._dashboard_service.match_detail(ledger_id)

        # 测试或离线任务会传入临时学习库；这里显式读取对应库，避免误读默认生产库。
        from football_data_mcp import sources

        return await asyncio.to_thread(sources.dashboard_match_detail, ledger_id, db_path=db_path)


def build_lark_prediction_message(detail: dict[str, Any]) -> LarkPredictionMessage:
    record_raw = detail.get("record")
    evidence_raw = detail.get("evidence")
    record: dict[str, Any] = record_raw if isinstance(record_raw, dict) else {}
    evidence: dict[str, Any] = evidence_raw if isinstance(evidence_raw, dict) else {}
    diagnostic_raw = evidence.get("prediction_diagnostic")
    diagnostic: dict[str, Any] = diagnostic_raw if isinstance(diagnostic_raw, dict) else {}
    league = _text(record.get("league"), "未知联赛")
    home = _text(record.get("home_team"), "主队")
    away = _text(record.get("away_team"), "客队")
    title = f"预测样本（非推荐）｜{home} vs {away}"
    lines = [
        title,
        f"联赛：{league}",
        f"开赛：{_text(record.get('kickoff_utc_plus_8'), '时间待确认')}",
        f"盘口：{_text(record.get('selection'), '暂无盘口')} @ {_decimal(record.get('decimal_odds'))}",
        f"模型概率：{_percent(record.get('model_probability'))}；校准概率：{_percent(record.get('learned_probability'))}；市场概率：{_percent(record.get('market_probability'))}",
        f"价值边际：{_signed_percent(record.get('edge'))}；预期回报：{_multiplier(record.get('expected_multiplier'))}",
        f"预测状态：{_text(record.get('prediction_type_label') or diagnostic.get('actionability_label'), '观察样本')}",
        f"原因：{_text(diagnostic.get('primary_reason') or record.get('rejection_reason') or record.get('recommendation'), '暂无')}",
        "说明：这是预测/观察消息，不是推荐发布，不构成投注指令。",
    ]
    return LarkPredictionMessage(title=title, text="\n".join(lines))


def _lark_text_payload(text: str, *, secret: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "msg_type": "text",
        "content": {"text": text},
    }
    if secret.strip():
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = _lark_sign(timestamp, secret.strip())
    return payload


def _lark_sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(string_to_sign, b"", digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _text(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    return text or fallback


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _percent(value: Any) -> str:
    number = _number(value)
    return "—" if number is None else f"{number * 100:.1f}%"


def _signed_percent(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "—"
    return f"{'+' if number > 0 else ''}{number * 100:.1f}%"


def _decimal(value: Any) -> str:
    number = _number(value)
    return "—" if number is None else f"{number:.2f}"


def _multiplier(value: Any) -> str:
    number = _number(value)
    return "—" if number is None else f"x{number:.3f}"

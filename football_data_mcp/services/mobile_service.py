from __future__ import annotations

import asyncio
import copy
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from football_data_mcp import learning_store, sources, validation_store
from football_data_mcp.services.data_source_service import DataSourceService


_CACHE_MAX_ITEMS = 128
_MATCHES_CACHE_TTL_SECONDS = 20.0
_ANALYSIS_CACHE_TTL_SECONDS = 120.0
_CACHE_LOCK = asyncio.Lock()
_MATCHES_CACHE: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
_ANALYSIS_CACHE: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
_MATCHES_INFLIGHT: dict[str, asyncio.Task[dict[str, Any]]] = {}
_ANALYSIS_INFLIGHT: dict[str, asyncio.Task[dict[str, Any]]] = {}
_SETTLEMENT_REFRESH_TTL_SECONDS = 300.0
_SETTLEMENT_REFRESH_TIMEOUT_SECONDS = 12.0
_SETTLEMENT_REFRESH_LOCK = asyncio.Lock()
_LAST_SETTLEMENT_REFRESH_AT = 0.0
_LAST_SETTLEMENT_REFRESH: dict[str, Any] | None = None


class MobileAnalysisService:
    """Shape existing MCP analysis results into the compact contract used by the iOS app."""

    def __init__(
        self,
        source_module: Any = sources,
        *,
        validation_store_module: Any = validation_store,
        data_source_service: Any | None = None,
        learning_store_module: Any = learning_store,
        record_recommendations: bool = True,
    ) -> None:
        self._sources = source_module
        self._validation_store = validation_store_module
        self._data_source_service = data_source_service or DataSourceService()
        self._learning_store = learning_store_module
        self._record_recommendations = record_recommendations

    async def matches(
        self,
        *,
        query: str = "",
        league: str | None = None,
        as_of: str | None = None,
        timezone_name: str | None = "Asia/Shanghai",
        window_hours: int = 24,
        limit: int = 30,
        analysis_ready_only: bool = True,
    ) -> dict[str, Any]:
        bounded_window_hours = max(1, min(int(window_hours or 24), 168))
        bounded_limit = max(1, min(int(limit or 30), 100))
        cache_key = _cache_key(
            "matches",
            id(self._sources),
            query,
            league,
            as_of,
            timezone_name or "Asia/Shanghai",
            bounded_window_hours,
            bounded_limit,
            analysis_ready_only,
        )

        async def compute() -> dict[str, Any]:
            result = await self._sources.list_matches(
                query=query,
                league=league,
                as_of=as_of,
                timezone_name=timezone_name or "Asia/Shanghai",
                window_hours=bounded_window_hours,
                limit=bounded_limit,
                analysis_ready_only=analysis_ready_only,
            )
            model_readiness = _mobile_model_readiness(self._latest_validation())
            odds_source_health = _mobile_odds_source_health(self._odds_source_status())
            matches = [_mobile_match_summary(item) for item in result.get("matches") or []]
            return {
                "status": result.get("status") or "ok",
                "generatedAtUTC": _now_utc(),
                "source": result.get("source") or {},
                "timeWindowPolicy": result.get("time_window_policy") or {},
                "totalCount": result.get("total_count") or len(matches),
                "returnedCount": len(matches),
                "matches": matches,
                "analysisReadyOnly": analysis_ready_only,
                "modelReadiness": model_readiness,
                "oddsSourceHealth": odds_source_health,
            }

        payload, cache_hit = await _cached_or_inflight(
            cache=_MATCHES_CACHE,
            inflight=_MATCHES_INFLIGHT,
            cache_key=cache_key,
            ttl_seconds=_MATCHES_CACHE_TTL_SECONDS,
            compute=compute,
        )
        return _mobile_cache_response(payload, cache_hit=cache_hit, ttl_seconds=_MATCHES_CACHE_TTL_SECONDS)

    async def _uncached_analysis(
        self,
        *,
        query: str,
        home_team: str | None,
        away_team: str | None,
        league: str | None,
        as_of: str | None,
        timezone_name: str | None,
        window_hours: int,
        include_raw: bool,
    ) -> dict[str, Any]:
        model_readiness = _mobile_model_readiness(self._latest_validation())
        odds_source_health = _mobile_odds_source_health(self._odds_source_status())
        raw = await self._sources.analyze_single_match(
            query,
            home_team=home_team,
            away_team=away_team,
            league=league,
            as_of=as_of,
            timezone_name=timezone_name or "Asia/Shanghai",
            window_hours=window_hours,
            include_source_probe=False,
        )
        payload = {
            "status": raw.get("status") or "ok",
            "generatedAtUTC": _now_utc(),
            "analysis": _mobile_analysis(
                raw,
                model_readiness=model_readiness,
                odds_source_health=odds_source_health,
            ),
            "tracking": self._save_mobile_recommendation(raw),
        }
        if include_raw:
            payload["raw"] = {
                "final_decision": raw.get("final_decision") or {},
                "final_execution_advice": raw.get("final_execution_advice") or {},
                "betting_decision_support": raw.get("betting_decision_support") or {},
                "analysis_pack": raw.get("analysis_pack") or {},
            }
        return payload

    def _save_mobile_recommendation(self, raw: dict[str, Any]) -> dict[str, Any]:
        if not self._record_recommendations:
            return {"status": "disabled", "message": "当前服务未启用推荐入库。"}
        if str(raw.get("status") or "ok") != "ok":
            return {"status": "skipped", "message": "本次分析未成功，不写入战绩。"}

        record, reason = _mobile_recommendation_record(raw)
        if not record:
            return {"status": "skipped", "message": reason or "没有可结算的推荐候选。"}

        saver = getattr(self._learning_store, "save_recommendation_records", None)
        if not callable(saver):
            return {"status": "unavailable", "message": "学习记录库不可用。"}
        try:
            changed_count = saver([record])
        except Exception as exc:
            return {"status": "error", "message": f"推荐入库失败：{type(exc).__name__}"}
        return {
            "status": "saved" if changed_count else "unchanged",
            "message": "推荐已进入战绩跟踪，赛果结算后会进入命中率曲线。",
            "recordKey": self._learning_store.recommendation_record_key(record)
            if hasattr(self._learning_store, "recommendation_record_key")
            else None,
            "changedCount": changed_count,
        }

    def _latest_validation(self) -> dict[str, Any] | None:
        getter = getattr(self._validation_store, "get_latest_validation", None)
        if not callable(getter):
            return None
        try:
            value = getter()
        except Exception:
            return None
        return value if isinstance(value, dict) else None

    def _odds_source_status(self) -> dict[str, Any] | None:
        getter = getattr(self._data_source_service, "odds_source_status", None)
        if not callable(getter):
            return None
        try:
            value = getter()
        except Exception:
            return None
        return value if isinstance(value, dict) else None

    async def analysis(
        self,
        *,
        query: str,
        home_team: str | None = None,
        away_team: str | None = None,
        league: str | None = None,
        as_of: str | None = None,
        timezone_name: str | None = "Asia/Shanghai",
        window_hours: int = 24,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        bounded_window_hours = max(1, min(int(window_hours or 24), 168))
        if include_raw:
            payload = await self._uncached_analysis(
                query=query,
                home_team=home_team,
                away_team=away_team,
                league=league,
                as_of=as_of,
                timezone_name=timezone_name,
                window_hours=bounded_window_hours,
                include_raw=include_raw,
            )
            return _mobile_cache_response(payload, cache_hit=False, ttl_seconds=0.0)

        cache_key = _cache_key(
            "analysis",
            id(self._sources),
            query,
            home_team,
            away_team,
            league,
            as_of,
            timezone_name or "Asia/Shanghai",
            bounded_window_hours,
        )

        async def compute() -> dict[str, Any]:
            return await self._uncached_analysis(
                query=query,
                home_team=home_team,
                away_team=away_team,
                league=league,
                as_of=as_of,
                timezone_name=timezone_name,
                window_hours=bounded_window_hours,
                include_raw=False,
            )

        payload, cache_hit = await _cached_or_inflight(
            cache=_ANALYSIS_CACHE,
            inflight=_ANALYSIS_INFLIGHT,
            cache_key=cache_key,
            ttl_seconds=_ANALYSIS_CACHE_TTL_SECONDS,
            compute=compute,
        )
        return _mobile_cache_response(payload, cache_hit=cache_hit, ttl_seconds=_ANALYSIS_CACHE_TTL_SECONDS)

    async def performance(
        self,
        *,
        limit: int = 160,
        refresh_results: bool = True,
        db_path: str | None = None,
    ) -> dict[str, Any]:
        bounded_limit = max(20, min(int(limit or 160), 500))
        settlement_refresh = await self._refresh_settlements_if_needed(db_path=db_path) if refresh_results else {
            "status": "disabled",
            "message": "本次未自动刷新赛果。",
        }
        lister = getattr(self._learning_store, "list_recommendation_records", None)
        if not callable(lister):
            records: list[dict[str, Any]] = []
        else:
            records = lister(db_path=db_path, limit=bounded_limit)
        performance = _mobile_performance(records)
        performance.update({
            "status": "ok",
            "generatedAtUTC": _now_utc(),
            "settlementRefresh": settlement_refresh,
        })
        return performance

    async def _refresh_settlements_if_needed(self, *, db_path: str | None = None) -> dict[str, Any]:
        global _LAST_SETTLEMENT_REFRESH_AT, _LAST_SETTLEMENT_REFRESH
        lister = getattr(self._learning_store, "list_recommendation_records", None)
        if not callable(lister):
            return {"status": "unavailable", "message": "学习记录库不可用。"}
        open_records = lister(db_path=db_path, status="open", limit=1)
        if not open_records:
            return {"status": "skipped", "message": "没有待结算推荐。"}

        now = time.monotonic()
        if _LAST_SETTLEMENT_REFRESH and now - _LAST_SETTLEMENT_REFRESH_AT < _SETTLEMENT_REFRESH_TTL_SECONDS:
            return {
                **_LAST_SETTLEMENT_REFRESH,
                "cacheHit": True,
                "message": "赛果刷新刚运行过，本次直接复用结果。",
            }

        refresher = getattr(self._sources, "settle_learning_recommendations", None)
        if not callable(refresher):
            return {"status": "unavailable", "message": "当前数据源没有自动结算能力。"}

        async with _SETTLEMENT_REFRESH_LOCK:
            now = time.monotonic()
            if _LAST_SETTLEMENT_REFRESH and now - _LAST_SETTLEMENT_REFRESH_AT < _SETTLEMENT_REFRESH_TTL_SECONDS:
                return {
                    **_LAST_SETTLEMENT_REFRESH,
                    "cacheHit": True,
                    "message": "赛果刷新刚运行过，本次直接复用结果。",
                }
            try:
                result = await asyncio.wait_for(
                    refresher(days_back=7, days_forward=0, db_path=db_path),
                    timeout=_SETTLEMENT_REFRESH_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                refresh = {"status": "timeout", "message": "赛果源响应较慢，本次先展示本地战绩。"}
            except Exception as exc:
                refresh = {"status": "error", "message": f"自动刷新赛果失败：{type(exc).__name__}"}
            else:
                settlement = _as_dict(result.get("settlement"))
                refresh = {
                    "status": "ok",
                    "message": "已尝试从公开赛果源刷新待结算推荐。",
                    "settledCount": int(_number(settlement.get("settled_count"), 0)),
                    "skippedCount": int(_number(settlement.get("skipped_count"), 0)),
                    "unsupportedCount": int(_number(settlement.get("unsupported_count"), 0)),
                }
            _LAST_SETTLEMENT_REFRESH_AT = time.monotonic()
            _LAST_SETTLEMENT_REFRESH = refresh
            return refresh


def _cache_key(*parts: Any) -> str:
    return "|".join(str(part or "").strip().lower() for part in parts)


def _cache_get(
    cache: OrderedDict[str, tuple[float, dict[str, Any]]],
    cache_key: str,
    *,
    ttl_seconds: float,
) -> dict[str, Any] | None:
    cached = cache.get(cache_key)
    if not cached:
        return None
    stored_at, payload = cached
    if time.monotonic() - stored_at > ttl_seconds:
        cache.pop(cache_key, None)
        return None
    cache.move_to_end(cache_key)
    return copy.deepcopy(payload)


def _cache_set(
    cache: OrderedDict[str, tuple[float, dict[str, Any]]],
    cache_key: str,
    payload: dict[str, Any],
) -> None:
    cache[cache_key] = (time.monotonic(), copy.deepcopy(payload))
    cache.move_to_end(cache_key)
    while len(cache) > _CACHE_MAX_ITEMS:
        cache.popitem(last=False)


async def _cached_or_inflight(
    *,
    cache: OrderedDict[str, tuple[float, dict[str, Any]]],
    inflight: dict[str, asyncio.Task[dict[str, Any]]],
    cache_key: str,
    ttl_seconds: float,
    compute: Any,
) -> tuple[dict[str, Any], bool]:
    cached = _cache_get(cache, cache_key, ttl_seconds=ttl_seconds)
    if cached is not None:
        return cached, True

    created_task = False
    async with _CACHE_LOCK:
        cached = _cache_get(cache, cache_key, ttl_seconds=ttl_seconds)
        if cached is not None:
            return cached, True
        task = inflight.get(cache_key)
        if task is None:
            task = asyncio.create_task(compute())
            inflight[cache_key] = task
            created_task = True

    try:
        payload = await task
    except Exception:
        async with _CACHE_LOCK:
            if inflight.get(cache_key) is task:
                inflight.pop(cache_key, None)
        raise

    if created_task:
        async with _CACHE_LOCK:
            _cache_set(cache, cache_key, payload)
            if inflight.get(cache_key) is task:
                inflight.pop(cache_key, None)
    return copy.deepcopy(payload), False


def _mobile_cache_response(payload: dict[str, Any], *, cache_hit: bool, ttl_seconds: float) -> dict[str, Any]:
    response = copy.deepcopy(payload)
    response["generatedAtUTC"] = _now_utc()
    response["cache"] = {
        "hit": cache_hit,
        "ttlSeconds": int(ttl_seconds),
    }
    return response


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:
        return default
    return number


def _optional_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _round_metric(value: float | None, ndigits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), ndigits)


def _mobile_recommendation_record(raw: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    match = _as_dict(raw.get("match") or _as_dict(raw.get("agent_brief")).get("match"))
    support = _as_dict(raw.get("betting_decision_support"))
    best = _as_dict(support.get("best_candidate"))
    if not best:
        best = next((_as_dict(item) for item in _as_list(support.get("market_candidates")) if _as_dict(item)), {})
    if not best:
        return None, "本次没有明确推荐候选。"

    market = str(best.get("market") or "").strip()
    if market not in {"1x2", "jingcai_hhad", "asian_handicap"}:
        return None, f"{_market_label(market)} 暂不进入命中率曲线，等待结算规则补齐。"
    decimal_odds = _optional_number(best.get("decimal_odds"))
    model_probability = _optional_number(best.get("model_probability"))
    if decimal_odds is None or decimal_odds <= 1:
        return None, "当前候选缺少可结算赔率。"
    if model_probability is None or model_probability <= 0:
        return None, "当前候选缺少模型概率。"

    selection_key = str(best.get("selection_key") or "").strip() or _infer_selection_key(best)
    if not selection_key:
        return None, "当前候选缺少可结算方向。"

    tracked_best = {
        **best,
        "market": market,
        "selection_key": selection_key,
        "decimal_odds": decimal_odds,
        "model_probability": model_probability,
    }
    return {
        "run_id": f"mobile-pwa:{datetime.now(timezone.utc).strftime('%Y%m%d')}",
        "tool": "mobile_pwa",
        "mode": "single_match",
        "target_market": market,
        "match": {
            "match_id": match.get("match_id"),
            "match_num_str": match.get("match_num_str"),
            "league": match.get("league") or match.get("division"),
            "home_team": match.get("home_team"),
            "away_team": match.get("away_team"),
            "kickoff_utc": match.get("kickoff_utc"),
            "kickoff_utc_plus_8": match.get("kickoff_utc_plus_8"),
        },
        "best_candidate": tracked_best,
        "selection_confidence": {
            "calibrated_probability": best.get("calibrated_probability") or model_probability,
        },
        "final_execution_advice": raw.get("final_execution_advice") or raw.get("final_decision") or {},
        "risk_flags": support.get("blocking_flags") or [],
        "caution_flags": support.get("caution_flags") or [],
        "raw": {
            "match": match,
            "betting_decision_support": support,
            "analysis_pack": raw.get("analysis_pack") or {},
        },
        "settlement_status": "open",
    }, ""


def _infer_selection_key(best: dict[str, Any]) -> str:
    selection = str(best.get("selection") or "").lower()
    market = str(best.get("market") or "")
    if market == "1x2":
        if "draw" in selection or "平" in selection:
            return "draw"
        if "away" in selection or "客" in selection:
            return "away"
        if "home" in selection or "主" in selection:
            return "home"
    if market == "asian_handicap":
        if "away" in selection or "客" in selection:
            return "away_cover"
        return "home_cover"
    if market == "jingcai_hhad":
        if "draw" in selection or "平" in selection:
            return "draw"
        if "away" in selection or "客" in selection:
            return "away"
        if "home" in selection or "主" in selection:
            return "home"
    return ""


def _mobile_performance(records: list[dict[str, Any]]) -> dict[str, Any]:
    display_records = [_mobile_record_row(record) for record in records]
    settled_records = [
        record for record in display_records
        if record["settlementStatus"] == "settled" and record["hit"] is not None
    ]
    settled_records.sort(key=lambda record: (
        str(record.get("settledAtUTC") or record.get("createdAtUTC") or ""),
        int(record.get("id") or 0),
    ))

    curve_points: list[dict[str, Any]] = []
    cumulative_profit = 0.0
    hit_count = 0
    miss_count = 0
    rolling_hits: list[int] = []
    current_streak_type = ""
    current_streak_count = 0
    for index, record in enumerate(settled_records, start=1):
        hit = 1 if record["hit"] else 0
        profit = _number(record.get("profitUnits"), 0.0)
        cumulative_profit += profit
        hit_count += hit
        miss_count += 0 if hit else 1
        rolling_hits.append(hit)
        streak_type = "hit" if hit else "miss"
        if streak_type == current_streak_type:
            current_streak_count += 1
        else:
            current_streak_type = streak_type
            current_streak_count = 1
        rolling_window = rolling_hits[-10:]
        curve_points.append({
            "index": index,
            "id": record["id"],
            "dateLabel": _date_label(record.get("settledAtUTC") or record.get("createdAtUTC")),
            "matchTitle": record["matchTitle"],
            "selectionLabel": record["selectionLabel"],
            "marketLabel": record["marketLabel"],
            "hit": bool(hit),
            "profitUnits": _round_metric(profit, 4),
            "hitRate": _round_metric(hit_count / index),
            "rollingHitRate": _round_metric(sum(rolling_window) / len(rolling_window)),
            "cumulativeProfitUnits": _round_metric(cumulative_profit, 4),
        })

    settled_count = len(settled_records)
    open_count = sum(1 for record in display_records if record["settlementStatus"] == "open")
    total_profit = sum(_number(record.get("profitUnits"), 0.0) for record in settled_records)
    status = "empty" if not display_records else "waiting_settlements" if not settled_records else "ready"
    return {
        "summary": {
            "status": status,
            "totalRecommendations": len(display_records),
            "openCount": open_count,
            "settledCount": settled_count,
            "hitCount": hit_count,
            "missCount": miss_count,
            "hitRate": _round_metric(hit_count / settled_count) if settled_count else None,
            "profitUnits": _round_metric(total_profit, 4),
            "roi": _round_metric(total_profit / settled_count, 6) if settled_count else None,
            "currentStreakType": current_streak_type,
            "currentStreakCount": current_streak_count,
        },
        "curve": {
            "title": "命中率曲线",
            "rollingWindow": 10,
            "points": curve_points[-120:],
        },
        "recentRecords": display_records[:30],
    }


def _mobile_record_row(record: dict[str, Any]) -> dict[str, Any]:
    home_team = str(record.get("home_team") or "主队")
    away_team = str(record.get("away_team") or "客队")
    status = str(record.get("settlement_status") or "")
    hit_value = record.get("hit")
    hit = None if hit_value is None else int(hit_value or 0) == 1
    return {
        "id": int(_number(record.get("id"), 0)),
        "matchTitle": f"{home_team} vs {away_team}",
        "league": str(record.get("league") or "未知赛事"),
        "kickoffText": str(record.get("kickoff_utc_plus_8") or record.get("kickoff_utc") or "时间待定"),
        "market": str(record.get("market") or ""),
        "marketLabel": _market_label(record.get("market")),
        "selectionLabel": _selection_label(record),
        "decimalOdds": _optional_number(record.get("decimal_odds")),
        "modelProbability": _optional_number(record.get("model_probability")),
        "edge": _optional_number(record.get("edge")),
        "settlementStatus": status or "unknown",
        "statusLabel": _settlement_status_label(status),
        "homeScore": None if record.get("home_score") is None else int(_number(record.get("home_score"), 0)),
        "awayScore": None if record.get("away_score") is None else int(_number(record.get("away_score"), 0)),
        "scoreText": _score_text(record),
        "hit": hit,
        "hitLabel": "命中" if hit else "未中" if hit is False else "待赛果",
        "profitUnits": _optional_number(record.get("profit_units")),
        "createdAtUTC": record.get("created_at_utc"),
        "settledAtUTC": record.get("settled_at_utc"),
    }


def _market_label(value: Any) -> str:
    labels = {
        "1x2": "胜平负",
        "jingcai_hhad": "让球胜平负",
        "asian_handicap": "亚盘",
        "over_under": "大小球",
        "parlay": "组合",
    }
    key = str(value or "")
    return labels.get(key, key or "未知玩法")


def _selection_label(record: dict[str, Any]) -> str:
    selection = str(record.get("selection") or "").strip()
    if selection:
        return selection
    selection_key = str(record.get("selection_key") or "").strip()
    return {
        "home": "主胜",
        "draw": "平局",
        "away": "客胜",
        "home_cover": "主队方向",
        "away_cover": "客队方向",
    }.get(selection_key, selection_key or "未命名方向")


def _settlement_status_label(status: str) -> str:
    return {
        "open": "待赛果",
        "settled": "已结算",
        "unsupported_market": "玩法待支持",
        "unsettleable": "无法结算",
        "postponed": "延期/取消",
        "tracked_only": "仅跟踪",
    }.get(str(status or ""), "未知")


def _score_text(record: dict[str, Any]) -> str:
    if record.get("home_score") is None or record.get("away_score") is None:
        return "待赛果"
    return f"{int(_number(record.get('home_score'), 0))}-{int(_number(record.get('away_score'), 0))}"


def _date_label(value: Any) -> str:
    text = str(value or "")
    if "T" in text:
        return text.split("T", 1)[0][5:]
    return text[:10] or "待定"


def _normalized_triple(values: dict[str, Any] | None, *, fallback: tuple[float, float, float]) -> dict[str, float]:
    home = _number(_as_dict(values).get("home"), fallback[0])
    draw = _number(_as_dict(values).get("draw"), fallback[1])
    away = _number(_as_dict(values).get("away"), fallback[2])
    total = home + draw + away
    if total <= 0:
        home, draw, away = fallback
        total = home + draw + away
    return {
        "home": round(home / total, 6),
        "draw": round(draw / total, 6),
        "away": round(away / total, 6),
    }


def _mobile_match_summary(match: dict[str, Any]) -> dict[str, Any]:
    home = str(match.get("home_team") or "")
    away = str(match.get("away_team") or "")
    league = str(match.get("league") or match.get("competition_name") or "")
    kickoff = str(match.get("kickoff_utc_plus_8") or match.get("kickoff_utc") or "")
    match_id = str(match.get("match_id") or "")
    stable_id = match_id or f"{home}-{away}-{kickoff}"
    readiness = _as_dict(match.get("analysis_readiness"))
    can_analyze = bool(readiness.get("can_run_single_match_analysis", True))
    return {
        "id": stable_id,
        "query": f"{home} vs {away}".strip(),
        "homeTeam": home or "主队",
        "awayTeam": away or "客队",
        "league": league or "未知赛事",
        "kickoffText": kickoff or "时间待定",
        "kickoffUTC": match.get("kickoff_utc"),
        "statusLabel": "可分析" if can_analyze else "资料不足",
        "dataQuality": "完整" if can_analyze else "部分",
        "analysisReady": can_analyze,
    }


def _mobile_analysis(
    raw: dict[str, Any],
    *,
    model_readiness: dict[str, Any] | None = None,
    odds_source_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    match = _as_dict(raw.get("match") or _as_dict(raw.get("agent_brief")).get("match"))
    support = _as_dict(raw.get("betting_decision_support"))
    model = _as_dict(support.get("model_engine") or raw.get("model_engine"))
    odds = _as_dict(raw.get("odds"))
    quality = _as_dict(odds.get("quality_contract"))
    market_candidates = _as_list(support.get("market_candidates"))
    best_candidate = _as_dict(support.get("best_candidate"))
    analysis_pack = _as_dict(raw.get("analysis_pack"))
    data_bundle = _as_dict(raw.get("data_bundle"))

    derived = _as_dict(model.get("derived_probabilities"))
    one_x_two = _normalized_triple(_as_dict(derived.get("1x2")), fallback=(0.4, 0.3, 0.3))
    moneyline_metrics = _as_dict(_as_dict(quality.get("preferred_moneyline_1x2")).get("current_metrics"))
    market_probs = _normalized_triple(_as_dict(moneyline_metrics.get("normalized_probability")), fallback=(
        one_x_two["home"],
        one_x_two["draw"],
        one_x_two["away"],
    ))
    odds_values = _moneyline_odds(_as_dict(quality.get("preferred_moneyline_1x2")), market_probs)
    expected_goals = _as_dict(model.get("expected_goals"))
    score_matrix = _score_matrix(_as_list(model.get("scoreline_distribution")))
    home_team = str(match.get("home_team") or "主队")
    away_team = str(match.get("away_team") or "客队")
    readiness = model_readiness or _mobile_model_readiness(None)
    source_health = odds_source_health or _mobile_odds_source_health(None)

    return {
        "id": str(match.get("match_id") or f"{home_team}-{away_team}-{match.get('kickoff_utc') or ''}"),
        "league": str(match.get("league") or match.get("division") or "未知赛事"),
        "kickoffText": str(match.get("kickoff_utc_plus_8") or match.get("kickoff_utc") or "时间待定"),
        "venue": str(match.get("venue") or "场地待确认"),
        "homeTeam": {"name": home_team, "shortName": _short_team_name(home_team)},
        "awayTeam": {"name": away_team, "shortName": _short_team_name(away_team)},
        "finalProbabilities": one_x_two,
        "confidence": _confidence_label(support),
        "dataQuality": _data_quality_label(support, analysis_pack),
        "marketBaseline": {
            "homeOdds": odds_values["home"],
            "drawOdds": odds_values["draw"],
            "awayOdds": odds_values["away"],
            "raw": _raw_probability_triple(odds_values),
            "devig": market_probs,
            "overround": max(0.0, sum(_raw_probability_triple(odds_values).values()) - 1.0),
        },
        "oddsMovement": _odds_movement(best_candidate, data_bundle),
        "expectedGoals": {
            "home": _number(expected_goals.get("home"), 1.25),
            "away": _number(expected_goals.get("away"), 1.05),
        },
        "scoreMatrix": score_matrix,
        "dataSources": _data_sources(analysis_pack, data_bundle, odds_source_health=source_health),
        "adjustments": _adjustments(best_candidate),
        "calibration": _calibration(support),
        "modelReadiness": readiness,
        "oddsSourceHealth": source_health,
        "asian": _asian_analysis(
            derived=_as_dict(derived.get("asian_handicap")),
            candidates=market_candidates,
            score_distribution=_as_list(model.get("scoreline_distribution")),
        ),
        "totals": _totals_analysis(_as_dict(derived.get("over_under")), market_candidates),
        "risks": _risk_flags(support, model_readiness=readiness, odds_source_health=source_health),
    }


def _short_team_name(name: str) -> str:
    stripped = str(name or "").strip()
    return stripped[:4] if len(stripped) > 4 else stripped or "球队"


def _moneyline_odds(moneyline: dict[str, Any], market_probs: dict[str, float]) -> dict[str, float]:
    current = _as_dict(moneyline.get("current"))
    metrics_odds = _as_dict(moneyline.get("odds") or _as_dict(moneyline.get("current_metrics")).get("odds"))
    values = {
        "home": _number(current.get("home") or metrics_odds.get("home"), 1 / max(market_probs["home"], 0.01)),
        "draw": _number(current.get("draw") or metrics_odds.get("draw"), 1 / max(market_probs["draw"], 0.01)),
        "away": _number(current.get("away") or metrics_odds.get("away"), 1 / max(market_probs["away"], 0.01)),
    }
    return {key: round(max(value, 1.01), 4) for key, value in values.items()}


def _raw_probability_triple(odds: dict[str, float]) -> dict[str, float]:
    return {
        "home": round(1 / max(odds["home"], 1.01), 6),
        "draw": round(1 / max(odds["draw"], 1.01), 6),
        "away": round(1 / max(odds["away"], 1.01), 6),
    }


def _confidence_label(support: dict[str, Any]) -> str:
    confidence = _number(support.get("confidence"), 0.5)
    if confidence >= 0.66:
        return "高"
    if confidence >= 0.52:
        return "中等"
    return "偏低"


def _data_quality_label(support: dict[str, Any], analysis_pack: dict[str, Any]) -> str:
    if support.get("blocking_flags"):
        return "受限"
    blocks = _as_dict(_as_dict(analysis_pack.get("data_coverage")).get("blocks"))
    usable_count = sum(1 for value in blocks.values() if value is True)
    if usable_count >= 4:
        return "良好"
    if usable_count >= 2:
        return "部分"
    return "基础"


def _score_matrix(distribution: list[Any], *, bucket_max: int = 4) -> list[dict[str, Any]]:
    buckets: dict[tuple[int, int], float] = {}
    for item in distribution:
        row = _as_dict(item)
        home_goals = min(int(_number(row.get("home_goals"), 0)), bucket_max)
        away_goals = min(int(_number(row.get("away_goals"), 0)), bucket_max)
        buckets[(home_goals, away_goals)] = buckets.get((home_goals, away_goals), 0.0) + _number(row.get("probability"), 0.0)
    total = sum(buckets.values()) or 1.0
    cells = []
    for home_bucket in range(bucket_max + 1):
        for away_bucket in range(bucket_max + 1):
            cells.append({
                "homeBucket": home_bucket,
                "awayBucket": away_bucket,
                "homeLabel": f"{home_bucket}+" if home_bucket == bucket_max else str(home_bucket),
                "awayLabel": f"{away_bucket}+" if away_bucket == bucket_max else str(away_bucket),
                "probability": round(buckets.get((home_bucket, away_bucket), 0.0) / total, 6),
            })
    return cells


def _odds_movement(best_candidate: dict[str, Any], data_bundle: dict[str, Any]) -> dict[str, Any]:
    movement = _as_dict(best_candidate.get("market_movement"))
    market_movement = _as_dict(data_bundle.get("market_movement"))
    odds_profile = _as_dict(best_candidate.get("odds_research_profile"))
    key_movements = _as_list(market_movement.get("key_movements"))
    primary = movement or _as_dict(market_movement.get("primary_movement"))
    points = []
    if movement:
        points.append(_movement_point(str(best_candidate.get("selection") or "当前候选"), movement))
    for item in key_movements:
        if len(points) >= 4:
            break
        row = _as_dict(item)
        label = str(row.get("selection") or row.get("selection_key") or "盘口")
        if label == str(best_candidate.get("selection") or ""):
            continue
        points.append(_movement_point(label, row))
    if not points:
        points.append({
            "label": "赔率走势",
            "opening": "暂无",
            "current": "暂无",
            "change": "等待快照",
            "direction": "neutral",
            "note": "后端还没有足够的开盘到当前快照，当前只按最新赔率计算。",
        })
    signal = str(best_candidate.get("market_movement_signal") or primary.get("direction_label") or "等待更多快照")
    risk_note = str(best_candidate.get("odds_research_note") or "").strip()
    if not risk_note and odds_profile.get("status") == "available":
        best_price = _number(odds_profile.get("best_available_odds"), 0.0)
        consensus_price = _number(odds_profile.get("current_consensus_odds"), 0.0)
        if best_price > 1 and consensus_price > 1:
            risk_note = f"赔率研究会比较去水概率、当前共识价和可拿到的最好价格；本方向共识价约 {consensus_price:.2f}，最好价约 {best_price:.2f}。"
    return {
        "openingTime": _compact_time(primary.get("first_observed_at_utc")) or "早盘",
        "currentTime": _compact_time(primary.get("latest_observed_at_utc")) or "当前",
        "summary": str(best_candidate.get("market_movement_note") or "赔率走势用于小幅校准模型概率，但当前赔率仍决定价值。"),
        "marketSignal": _signal_label(signal),
        "points": points,
        "riskNote": risk_note or "赔率变化是强信号，但不能单独决定结论；系统会把它和当前价格、比分模型、风险标记一起看。",
    }


def _movement_point(label: str, movement: dict[str, Any]) -> dict[str, Any]:
    opening_line = movement.get("opening_line")
    latest_line = movement.get("latest_line")
    opening_odds = movement.get("opening_decimal_odds")
    latest_odds = movement.get("latest_decimal_odds")
    opening = _line_odds_text(opening_line, opening_odds)
    latest = _line_odds_text(latest_line, latest_odds)
    probability_delta = _number(movement.get("implied_probability_delta"), 0.0)
    line_delta = _number(movement.get("line_delta"), 0.0)
    direction = "neutral"
    if probability_delta > 0.005:
        direction = "supportsHome"
    elif probability_delta < -0.005:
        direction = "supportsAway"
    if str(movement.get("direction") or "") == "stable":
        direction = "neutral"
    if probability_delta > 0.005 and _number(movement.get("odds_delta"), 0.0) < 0:
        note = "隐含概率上升，市场对这个方向更认可，但当前入场价格也更紧。"
    elif probability_delta < -0.005:
        note = "隐含概率下降，市场对这个方向的支持变弱。"
    else:
        note = "变化不大，更多作为稳定性参考。"
    change_bits = []
    if probability_delta:
        change_bits.append(f"{probability_delta * 100:+.1f}%")
    if line_delta:
        change_bits.append(f"盘口 {line_delta:+g}")
    return {
        "label": label,
        "opening": opening,
        "current": latest,
        "change": " / ".join(change_bits) if change_bits else "基本平稳",
        "direction": direction,
        "note": note,
    }


def _line_odds_text(line: Any, odds: Any) -> str:
    price = _number(odds, 0.0)
    line_number = _number(line, 999.0)
    if price <= 1:
        return "暂无"
    if line_number == 999.0:
        return f"{price:.2f}"
    return f"{line_number:+g} @ {price:.2f}"


def _compact_time(value: Any) -> str:
    text = str(value or "")
    if "T" in text:
        return text.split("T", 1)[1][:5]
    return text[:16]


def _signal_label(signal: str) -> str:
    if signal == "supports_selection":
        return "盘口走势支持当前候选"
    if signal == "against_selection":
        return "盘口走势和当前候选相反"
    if signal in {"stable", "平稳"}:
        return "盘口整体平稳"
    return str(signal or "等待更多走势")


def _data_sources(
    analysis_pack: dict[str, Any],
    data_bundle: dict[str, Any],
    *,
    odds_source_health: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    blocks = _as_dict(_as_dict(analysis_pack.get("data_coverage")).get("blocks"))
    movement = _as_dict(data_bundle.get("market_movement"))
    rows = [
        _source_row("赛程", "公开赛程源", "已确认", "高", "参与计算", blocks.get("schedule"), "用于确认比赛双方和开球时间。"),
        _source_row("赔率/盘口", "多源赔率", "当前快照", "高", "参与计算", blocks.get("moneyline_1x2") or blocks.get("asian_handicap"), "用于换算基础概率和计算当前价值。"),
        _source_row("赔率走势", "market_snapshots", "历史快照", "中等", "参与计算" if movement.get("status") == "available" else "仅作参考", movement.get("status") == "available", "用于小幅校准概率，并提示价格是否已经变紧。"),
        _source_row("比分模型", "Dixon-Coles/Poisson", "本次计算", "中等", "参与计算", blocks.get("model_engine"), "把赔率、大小球和亚盘转换成比分分布。"),
        _source_row("阵容/新闻", "公开上下文", "赛前更新", "偏低", "仅作参考", blocks.get("lineup"), "未确认信号默认只提示，不直接改动结论。"),
    ]
    health = odds_source_health or {}
    if health:
        rows.insert(
            2,
            {
                "name": "独立赔率源",
                "provider": str(health.get("activeSourceLabel") or "未识别"),
                "freshness": str(health.get("label") or "待确认"),
                "confidence": "高" if bool(health.get("productionReady")) else "偏低",
                "usage": "参与计算" if bool(health.get("productionReady")) else "仅作参考",
                "note": str(health.get("summary") or "当前赔率源健康状态待确认。"),
            },
        )
    return rows


def _source_row(
    name: str,
    provider: str,
    freshness: str,
    confidence: str,
    usage: str,
    available: Any,
    note: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "provider": provider,
        "freshness": freshness if available else "待补充",
        "confidence": confidence if available else "偏低",
        "usage": usage if available else "未采用",
        "note": note,
    }


def _adjustments(best_candidate: dict[str, Any]) -> list[dict[str, Any]]:
    raw_probability = _number(best_candidate.get("raw_model_probability"), _number(best_candidate.get("model_probability"), 0.0))
    final_probability = _number(best_candidate.get("model_probability"), raw_probability)
    calibration = _as_dict(best_candidate.get("odds_movement_calibration"))
    movement_delta = _number(calibration.get("adjustment"), final_probability - raw_probability)
    odds_profile = _as_dict(best_candidate.get("odds_research_profile"))
    no_vig_edge = _number(odds_profile.get("probability_edge_vs_no_vig"), 0.0)
    return [
        {
            "title": "原始模型概率",
            "value": raw_probability,
            "note": "由当前赔率、亚盘、大小球和比分模型得到。",
            "used": True,
        },
        {
            "title": "赔率走势校准",
            "value": movement_delta,
            "note": "只在有历史快照时小幅调整，避免盲目追涨。",
            "used": bool(calibration),
        },
        {
            "title": "当前赔率价值",
            "value": _number(best_candidate.get("edge"), 0.0),
            "note": "最终是否值得关注仍按当前赔率重新计算 EV。",
            "used": True,
        },
        {
            "title": "去水市场对照",
            "value": no_vig_edge,
            "note": "比较模型概率和去水后的市场共识，判断优势来自真实概率还是只是某家公司给了更好价格。",
            "used": odds_profile.get("status") == "available",
        },
    ]


def _calibration(support: dict[str, Any]) -> dict[str, Any]:
    confidence = _number(support.get("confidence"), 0.5)
    return {
        "rangeLabel": f"{max(0, confidence - 0.05) * 100:.0f}%-{min(1, confidence + 0.05) * 100:.0f}%",
        "actualRate": confidence,
        "sampleCount": 0,
        "note": "移动端当前展示本次 MCP 置信度；历史回测样本会在后续版本接入。",
    }


def _asian_analysis(
    *,
    derived: dict[str, Any],
    candidates: list[Any],
    score_distribution: list[Any],
) -> dict[str, Any]:
    asian_candidate = next((_as_dict(item) for item in candidates if _as_dict(item).get("market") == "asian_handicap"), {})
    line = _number(derived.get("line"), _number(asian_candidate.get("line"), -0.25))
    if _number(asian_candidate.get("line"), line) > 0 and str(asian_candidate.get("selection_key")) == "away_cover":
        line = -_number(asian_candidate.get("line"), line)
    full_win, half_win, push, half_loss, full_loss = _asian_settlement(score_distribution, line)
    return {
        "line": line,
        "lineLabel": f"主队 {line:+g}",
        "sideLabel": "主队方向",
        "odds": _number(asian_candidate.get("decimal_odds"), 1.90),
        "fullWin": full_win,
        "halfWin": half_win,
        "push": push,
        "halfLoss": half_loss,
        "fullLoss": full_loss,
        "priceNote": str(asian_candidate.get("market_movement_note") or "亚盘概率来自比分分布，当前赔率决定是否还有价值。"),
    }


def _asian_settlement(distribution: list[Any], line: float) -> tuple[float, float, float, float, float]:
    full_win = half_win = push = half_loss = full_loss = 0.0
    split_lines = _split_quarter_line(line)
    for item in distribution:
        row = _as_dict(item)
        margin = _number(row.get("home_goals"), 0) - _number(row.get("away_goals"), 0)
        probability = _number(row.get("probability"), 0.0)
        score = sum(_settlement_score(margin, split_line) for split_line in split_lines) / len(split_lines)
        if score >= 0.99:
            full_win += probability
        elif score > 0.01:
            half_win += probability
        elif abs(score) < 0.01:
            push += probability
        elif score > -0.99:
            half_loss += probability
        else:
            full_loss += probability
    total = full_win + half_win + push + half_loss + full_loss or 1.0
    return (
        round(full_win / total, 6),
        round(half_win / total, 6),
        round(push / total, 6),
        round(half_loss / total, 6),
        round(full_loss / total, 6),
    )


def _split_quarter_line(line: float) -> list[float]:
    doubled = line * 2
    if abs(round(doubled) - doubled) < 0.0001:
        return [line]
    lower = int(doubled // 1) / 2
    return [lower, lower + 0.5]


def _settlement_score(margin: float, line: float) -> float:
    adjusted = margin + line
    if adjusted > 0.0001:
        return 1.0
    if adjusted < -0.0001:
        return -1.0
    return 0.0


def _totals_analysis(derived: dict[str, Any], candidates: list[Any]) -> dict[str, Any]:
    totals_candidate = next((_as_dict(item) for item in candidates if _as_dict(item).get("market") == "over_under"), {})
    line = _number(derived.get("line"), _number(totals_candidate.get("line"), 2.5))
    over = _number(derived.get("over"), 0.5)
    under = _number(derived.get("under"), 1 - over)
    return {
        "line": line,
        "lineLabel": f"{line:g}球",
        "overOdds": _number(totals_candidate.get("decimal_odds"), 1.90),
        "underOdds": 0.0,
        "overProbability": over,
        "underProbability": under,
        "note": str(totals_candidate.get("market_movement_note") or "大小球概率来自比分分布：总进球超过盘口线算大球。"),
    }


def _risk_flags(
    support: dict[str, Any],
    *,
    model_readiness: dict[str, Any] | None = None,
    odds_source_health: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    flags = []
    readiness = model_readiness or {}
    readiness_status = str(readiness.get("status") or "")
    if readiness_status and readiness_status != "production_ready":
        flags.append({
            "title": str(readiness.get("label") or "模型验证未完成"),
            "detail": str(readiness.get("summary") or "当前仍应按研究模式使用。"),
        })
    source_health = odds_source_health or {}
    source_status = str(source_health.get("status") or "")
    if source_status in {"fallback", "degraded", "blocked", "unknown"}:
        flags.append({
            "title": str(source_health.get("label") or "赔率源需要关注"),
            "detail": str(source_health.get("summary") or "当前赔率源稳定性不足。"),
        })
    for flag in _as_list(support.get("blocking_flags")):
        flags.append({"title": "硬性阻断", "detail": str(flag)})
    for flag in _as_list(support.get("caution_flags"))[:4]:
        flags.append({"title": "需要注意", "detail": str(flag)})
    if not flags:
        flags.append({"title": "模型用途", "detail": "概率是分析参考，不是结果保证。"})
    return flags


def _mobile_model_readiness(latest_validation: dict[str, Any] | None) -> dict[str, Any]:
    item = _as_dict(latest_validation)
    readiness = str(item.get("automation_readiness") or "").strip() or "unknown"
    labels = {
        "production_ready": "可进入发布闸门",
        "paper_trade_only": "仅限纸面学习",
        "watchlist": "进入观察名单",
        "not_ready": "未通过验证",
        "unknown": "尚未验证",
    }
    summaries = {
        "production_ready": "最近 holdout 已通过当前发布闸门，但移动端仍应保留研究性质提示。",
        "paper_trade_only": "最近 holdout 只支持纸面学习，不允许真实自动化或生产推荐。",
        "watchlist": "最近 holdout 进入观察名单，方向可能有用，但还不够稳定。",
        "not_ready": "最近 holdout 仍未通过，不能把当前模型当成生产自动化信号。",
        "unknown": "还没有可用 holdout 验证快照，移动端必须按研究模式展示。",
    }
    roi = _number(item.get("roi"), 0.0) if item else 0.0
    evaluated_count = int(_number(item.get("evaluated_count"), 0.0)) if item else 0
    bet_count = int(_number(item.get("bet_count"), 0.0)) if item else 0
    detail_bits = []
    if item:
        method = str(item.get("method") or "").strip()
        if method:
            detail_bits.append(f"方法 {method}")
        if evaluated_count > 0:
            detail_bits.append(f"评估 {evaluated_count} 场")
        if bet_count > 0:
            detail_bits.append(f"下注样本 {bet_count} 场")
        if item.get("roi") is not None:
            detail_bits.append(f"ROI {roi * 100:+.1f}%")
        if item.get("log_loss_diff") is not None:
            detail_bits.append(f"log-loss 差值 {_number(item.get('log_loss_diff'), 0.0):+.3f}")
    return {
        "status": readiness,
        "label": labels.get(readiness, labels["unknown"]),
        "summary": summaries.get(readiness, summaries["unknown"]),
        "detail": " · ".join(detail_bits) if detail_bits else summaries.get(readiness, summaries["unknown"]),
        "updatedAtUTC": item.get("created_at_utc"),
        "method": item.get("method"),
        "evaluatedCount": evaluated_count,
        "betCount": bet_count,
        "roi": item.get("roi"),
        "beatsMarket": item.get("beats_market"),
        "productionApproved": readiness == "production_ready",
    }


def _mobile_odds_source_health(odds_status: dict[str, Any] | None) -> dict[str, Any]:
    data = _as_dict(odds_status)
    closure = _as_dict(data.get("closure"))
    sources_state = _as_dict(data.get("sources"))
    active_source = str(closure.get("active_source") or "").strip()
    active_source_state = _as_dict(sources_state.get(active_source)) if active_source else {}
    production_ready = bool(closure.get("production_ready"))
    active_labels = {
        "leisu": "雷速",
        "oddsportal_scraper": "OddsPortal",
        "the_odds_api": "The Odds API",
        "analysis_odds": "分析沉淀快照",
        "": "无独立赔率源",
    }
    if active_source == "leisu" and production_ready:
        status = "healthy"
        label = "独立赔率源正常"
    elif production_ready:
        status = "fallback"
        label = "使用兜底赔率源"
    elif active_source:
        status = "degraded"
        label = "赔率源降级"
    else:
        status = "blocked"
        label = "独立赔率源不可用"
    next_action = str(active_source_state.get("next_action") or "").strip()
    if not next_action:
        leisu_state = _as_dict(sources_state.get("leisu"))
        next_action = str(leisu_state.get("next_action") or closure.get("reason") or "需要恢复独立赔率快照。")
    detail = str(closure.get("reason") or next_action or "赔率源状态待确认。")
    return {
        "status": status,
        "label": label,
        "summary": detail,
        "detail": detail,
        "activeSource": active_source or None,
        "activeSourceLabel": active_labels.get(active_source, active_source or active_labels[""]),
        "productionReady": production_ready,
        "checkedAtUTC": closure.get("checked_at_utc"),
        "nextAction": next_action,
    }

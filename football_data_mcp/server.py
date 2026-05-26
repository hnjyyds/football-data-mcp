from __future__ import annotations

import asyncio
import os
import threading
from typing import Any
from urllib.parse import unquote

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from football_data_mcp import backtest, sources


mcp = FastMCP(
    "football-data-mcp",
    instructions=(
        "Single-match and short-list football data MCP. Use it to resolve a user-specified match, "
        "probe multiple football data sources, fetch numeric 1X2 and Asian handicap odds, normalized lineup_analysis, and return schedule/form evidence. "
        "When paid-source keys are configured, sync_market_snapshots stores The Odds API market snapshots locally and get_match_data_bundle returns multi-source consensus. "
        "When Leisu access is configured, sync_leisu_odds_snapshots stores gated Leisu multi-company odds snapshots locally for time-series audit. "
        "For 'pick the most valuable upcoming matches' requests, use shortlist_value_matches with mode='value'. "
        "For 'pick the most reliable / highest confidence match' requests, use shortlist_value_matches with mode='confidence' and audit with run_top_k_confidence_backtest. "
        "For balanced hit-rate plus non-crushed odds requests, use shortlist_value_matches with mode='balanced'. "
        "For parlay/串单 requests, use recommend_jingcai_parlay so combinations, total odds, stake_level, and risk flags stay MCP-driven. "
        "For automated paper-learning loops, use run_auto_learning_cycle, settle_learning_recommendations, and learning_calibration_status. "
        "When lineup data is present, use match_context.lineup.lineup_analysis only; do not infer from raw formation codes. "
        "Leisu schedule is supplemental Chinese fixture corroboration; Leisu odds become usable only after explicit odds parsing and quality-gated snapshot sync."
    ),
    host=os.getenv("FOOTBALL_DATA_MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("FOOTBALL_DATA_MCP_PORT", "8910")),
    stateless_http=True,
)


def _dashboard_cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Cache-Control": "no-store",
    }


@mcp.custom_route("/api/dashboard", methods=["GET", "OPTIONS"], include_in_schema=False)
async def dashboard_api(request: Request) -> Response:
    """Read-only JSON snapshot for the local dashboard frontend."""
    headers = _dashboard_cors_headers()
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=headers)
    snapshot = await asyncio.to_thread(sources.dashboard_snapshot)
    return JSONResponse(snapshot, headers=headers)


@mcp.custom_route("/api/dashboard/record/{record_id}", methods=["GET", "OPTIONS"], include_in_schema=False)
async def dashboard_record_api(request: Request) -> Response:
    """Read-only JSON detail for one persisted dashboard recommendation."""
    headers = _dashboard_cors_headers()
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=headers)
    record_id = unquote(request.path_params.get("record_id", ""))
    detail = await asyncio.to_thread(sources.dashboard_record_detail, record_id)
    status_code = 404 if detail.get("status") == "not_found" else 200
    return JSONResponse(detail, status_code=status_code, headers=headers)


@mcp.custom_route("/api/dashboard/match/{ledger_id}", methods=["GET", "OPTIONS"], include_in_schema=False)
async def dashboard_match_api(request: Request) -> Response:
    """Read-only JSON detail for one persisted dashboard prediction sample."""
    headers = _dashboard_cors_headers()
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=headers)
    ledger_id = unquote(request.path_params.get("ledger_id", ""))
    detail = await asyncio.to_thread(sources.dashboard_match_detail, ledger_id)
    status_code = 404 if detail.get("status") == "not_found" else 200
    return JSONResponse(detail, status_code=status_code, headers=headers)


@mcp.tool()
async def source_health() -> dict[str, Any]:
    """Check primary structured sources plus supplemental source health such as Leisu schedule parsing."""
    return await sources.source_health()


@mcp.tool()
async def sync_market_snapshots(
    sport_keys: list[str] | None = None,
    regions: str = "",
    markets: list[str] | None = None,
    limit_per_sport: int | None = None,
) -> dict[str, Any]:
    """
    Refresh paid-source odds snapshots into the local snapshot store.

    Use this before shortlist/parlay runs when API keys are configured. The tool
    gracefully returns not_configured when THE_ODDS_API_KEY is absent, so agents
    should not treat that as a failure of existing public-source analysis.
    """
    return await sources.sync_market_snapshots(
        sport_keys=sport_keys,
        regions=regions or None,
        markets=markets,
        limit_per_sport=limit_per_sport,
    )


@mcp.tool()
async def sync_leisu_odds_snapshots(
    as_of: str = "",
    timezone_name: str = "Asia/Shanghai",
    window_minutes: int = 24 * 60,
    limit: int = 20,
    concurrency: int = 4,
    require_quality_gate: bool = True,
) -> dict[str, Any]:
    """
    Probe Leisu odds pages and persist accessible multi-company odds snapshots.

    This is a free-source snapshot sync path. It respects the Leisu quality gate:
    by default only parsed numeric odds with usable access are persisted. Use it
    to build odds time series for CLV, movement, and shadow-model validation.
    """
    return await sources.sync_leisu_odds_snapshots(
        as_of=as_of or None,
        timezone_name=timezone_name or "Asia/Shanghai",
        window_minutes=window_minutes or (24 * 60),
        limit=limit or 20,
        concurrency=concurrency or 4,
        require_quality_gate=require_quality_gate,
    )


@mcp.tool()
async def run_auto_learning_cycle(
    query: str = "",
    league: str = "",
    as_of: str = "",
    timezone_name: str = "Asia/Shanghai",
    asian_window_minutes: int = 10,
    parlay_window_minutes: int = 10,
    top_n: int = 3,
    limit: int = 30,
    include_asian_shortlist: bool = True,
    include_jingcai_parlay: bool = True,
    include_shadow_predictions: bool = True,
    shadow_prediction_limit: int = 100,
    analysis_candidate_limit: int = 80,
    analysis_concurrency: int = 10,
    include_market_snapshot_sync: bool = True,
    market_snapshot_limit: int = 80,
    market_snapshot_concurrency: int = 4,
    market_snapshot_window_minutes: int = 24 * 60,
    include_snapshot_reanalysis: bool = True,
    snapshot_reanalysis_limit: int = 20,
    snapshot_reanalysis_concurrency: int = 4,
    auto_settle: bool = True,
) -> dict[str, Any]:
    """
    Run one automated paper-learning loop.

    This records future-window Asian handicap balanced picks and Jingcai parlay
    recommendations into the learning database, optionally fetches public
    completed scores, settles open records, and recomputes calibration buckets.
    It is paper learning only and never places real-money bets.
    """
    return await sources.run_auto_learning_cycle(
        query=query or "",
        league=league or None,
        as_of=as_of or None,
        timezone_name=timezone_name or "Asia/Shanghai",
        asian_window_minutes=asian_window_minutes or 10,
        parlay_window_minutes=parlay_window_minutes or 10,
        top_n=top_n or 3,
        limit=limit or 30,
        include_asian_shortlist=include_asian_shortlist,
        include_jingcai_parlay=include_jingcai_parlay,
        include_shadow_predictions=include_shadow_predictions,
        shadow_prediction_limit=shadow_prediction_limit or 100,
        analysis_candidate_limit=analysis_candidate_limit or 80,
        analysis_concurrency=analysis_concurrency or 10,
        include_market_snapshot_sync=include_market_snapshot_sync,
        market_snapshot_limit=market_snapshot_limit or 80,
        market_snapshot_concurrency=market_snapshot_concurrency or 4,
        market_snapshot_window_minutes=market_snapshot_window_minutes or (24 * 60),
        include_snapshot_reanalysis=include_snapshot_reanalysis,
        snapshot_reanalysis_limit=snapshot_reanalysis_limit or 20,
        snapshot_reanalysis_concurrency=snapshot_reanalysis_concurrency or 4,
        auto_settle=auto_settle,
    )


@mcp.tool()
async def settle_learning_recommendations(
    results: list[dict[str, Any]] | None = None,
    auto_fetch: bool = True,
    as_of: str = "",
    timezone_name: str = "Asia/Shanghai",
    days_back: int = 3,
    days_forward: int = 1,
) -> dict[str, Any]:
    """
    Settle open paper recommendations and recompute calibration buckets.

    Pass explicit score rows when available, or leave auto_fetch=true to attempt
    public-source score discovery. Results must include home_team, away_team,
    home_score, and away_score when supplied manually.
    """
    return await sources.settle_learning_recommendations(
        results=results,
        auto_fetch=auto_fetch,
        as_of=as_of or None,
        timezone_name=timezone_name or "Asia/Shanghai",
        days_back=days_back or 3,
        days_forward=days_forward or 1,
    )


@mcp.tool()
async def learning_calibration_status(limit: int = 50) -> dict[str, Any]:
    """
    Show current paper-learning record counts and calibration buckets.

    Use this before trusting live-calibrated recommendations; small buckets are
    diagnostic only and should not be treated as reliable edges.
    """
    return sources.learning_calibration_status(limit=limit or 50)


@mcp.tool()
async def get_match_data_bundle(
    query: str,
    home_team: str = "",
    away_team: str = "",
    league: str = "",
    as_of: str = "",
    timezone_name: str = "Asia/Shanghai",
    window_hours: int = 24,
    include_match_resolution: bool = False,
    include_context_refresh: bool = True,
) -> dict[str, Any]:
    """
    Return source coverage, local snapshot freshness, and market consensus for one match.

    Use this to audit whether paid-source snapshots exist before making claims
    about multi-bookmaker odds. It does not replace analyze_single_match; it
    complements it with source coverage and local consensus evidence.
    """
    return await sources.get_match_data_bundle(
        query=query,
        home_team=home_team or None,
        away_team=away_team or None,
        league=league or None,
        as_of=as_of or None,
        timezone_name=timezone_name or "Asia/Shanghai",
        window_hours=window_hours or 24,
        include_match_resolution=include_match_resolution,
        include_context_refresh=include_context_refresh,
    )


@mcp.tool()
async def probe_sources(
    query: str = "",
    home_team: str = "",
    away_team: str = "",
    limit_chars: int = 500,
) -> dict[str, Any]:
    """
    Probe all configured football data sources and report which are currently usable.

    Use this when source quality is uncertain. The result explains whether a site
    returned parseable HTML/CSV, looked blocked, or exposed useful match hints.
    Leisu schedule rows are useful as Chinese fixture/link corroboration, but
    do not by themselves make a match analysis-ready.
    """
    return await sources.probe_sources(
        query=query,
        home_team=home_team or None,
        away_team=away_team or None,
        limit_chars=limit_chars or 500,
    )


@mcp.tool()
async def probe_leisu_odds(
    match_id: str = "",
    odds_url: str = "",
    include_snippet: bool = False,
    snippet_chars: int = 600,
) -> dict[str, Any]:
    """
    Probe a Leisu odds page and parse multi-company 1X2/AH/totals markets when accessible.

    Use this before promoting Leisu as an odds source. Direct HTTP may return an
    Aliyun WAF challenge; configure LEISU_ODDS_PROXY_URL, LEISU_COOKIE, or
    LEISU_ACW_SC_V2 for cookie/proxy-assisted fetches. Never invent odds when
    access.status reports waf_challenge/blocked.
    """
    return await sources.probe_leisu_odds(
        match_id=match_id or "",
        odds_url=odds_url or "",
        include_snippet=include_snippet,
        snippet_chars=snippet_chars or 600,
    )


@mcp.tool()
async def search_fixtures(
    query: str,
    home_team: str = "",
    away_team: str = "",
    league: str = "",
    as_of: str = "",
    timezone_name: str = "Asia/Shanghai",
    window_hours: int = 24,
    limit: int = 8,
) -> dict[str, Any]:
    """
    Search Football-Data fixtures for a user-specified single match.

    Use query like "Liverpool vs Arsenal"; optionally pass home_team, away_team,
    and league. Leave as_of empty unless the user explicitly supplied an absolute
    local time; empty as_of uses the server's current Asia/Shanghai time. The
    default time window is [T0, T0+24h].
    """
    return await sources.find_candidates(
        query,
        home_team=home_team or None,
        away_team=away_team or None,
        league=league or None,
        as_of=as_of or None,
        timezone_name=timezone_name or "Asia/Shanghai",
        window_hours=window_hours or 24,
        limit=limit or 8,
    )


@mcp.tool()
async def list_matches(
    query: str = "",
    league: str = "",
    as_of: str = "",
    timezone_name: str = "Asia/Shanghai",
    window_hours: int = 24,
    limit: int = 50,
    analysis_ready_only: bool = True,
) -> dict[str, Any]:
    """
    List football fixtures in the default [T0, T0+24h] window.

    Use this when the user asks "有哪些比赛" or wants a match list. This tool is
    for listing only; downstream betting analysis must still be run one match at a time.
    Dongqiudi is the primary broad match-list source. By default it only returns
    matches that already have a schedule anchor and odds snapshot, so listed
    matches can proceed to analyze_single_match. Leave as_of empty unless the
    user explicitly supplied an absolute local time; empty as_of uses the server's
    current Asia/Shanghai time. The response also includes supplemental Leisu
    schedule status for Chinese team-name/link corroboration only.
    """
    return await sources.list_matches(
        query=query or "",
        league=league or None,
        as_of=as_of or None,
        timezone_name=timezone_name or "Asia/Shanghai",
        window_hours=window_hours or 24,
        limit=limit or 50,
        analysis_ready_only=analysis_ready_only,
    )


@mcp.tool()
async def shortlist_value_matches(
    query: str = "",
    league: str = "",
    as_of: str = "",
    timezone_name: str = "Asia/Shanghai",
    window_minutes: int = 60,
    top_n: int = 3,
    limit: int = 30,
    min_edge: float = 0.01,
    mode: str = "confidence",
    target_market: str = "any",
    min_calibrated_probability: float = 0.58,
    min_decimal_odds: float = 1.65,
    max_decimal_odds: float = 2.05,
    min_value_edge: float = 0.02,
    require_core_markets: bool = True,
    analysis_candidate_limit: int = 30,
    analysis_concurrency: int = 6,
    use_learning_policy: bool = True,
) -> dict[str, Any]:
    """
    Pick the most valuable football matches starting in the next window, default next 60 minutes.

    Use this when the user asks for "未来1小时内最有把握", "精选几场", "挑最有价值的比赛",
    or similar shortlist requests. Set mode="confidence" for稳胆/highest-confidence requests,
    mode="balanced" (or alias mode="balance") for high-confidence picks whose odds are not crushed, and explicit mode="value"
    for value/edge requests. Set target_market="asian_handicap" for亚盘-only
    requests. The tool lists upcoming matches, runs MCP single-match
    analysis for up to 100 listed candidates concurrently, rejects hard blockers/missing core markets/no positive
    edge, ranks the remaining picks, and returns how to bet via final_decision.headline.
    For mode="balanced" with target_market="asian_handicap", use_learning_policy=true lets settled paper results
    tighten thresholds and live-calibrate probabilities automatically after enough samples.
    It intentionally skips repeated per-match source probes so the call fits normal tool timeouts.
    Downstream agents should not recalculate probabilities outside MCP.
    """
    return await sources.shortlist_value_matches(
        query=query or "",
        league=league or None,
        as_of=as_of or None,
        timezone_name=timezone_name or "Asia/Shanghai",
        window_minutes=window_minutes or 60,
        top_n=top_n or 3,
        limit=limit or 30,
        min_edge=min_edge,
        mode=mode or "confidence",
        target_market=target_market or "any",
        min_calibrated_probability=min_calibrated_probability,
        min_decimal_odds=min_decimal_odds,
        max_decimal_odds=max_decimal_odds,
        min_value_edge=min_value_edge,
        require_core_markets=require_core_markets,
        analysis_candidate_limit=analysis_candidate_limit or 30,
        analysis_concurrency=analysis_concurrency or 6,
        use_learning_policy=use_learning_policy,
    )


@mcp.tool()
async def recommend_jingcai_parlay(
    query: str = "",
    league: str = "",
    as_of: str = "",
    timezone_name: str = "Asia/Shanghai",
    window_minutes: int = 24 * 60,
    top_n: int = 3,
    limit: int = 30,
    min_edge: float = 0.01,
    min_combined_edge: float = 0.03,
    max_legs: int = 3,
    parlay_mode: str = "confidence",
    min_confidence_leg_probability: float = 0.60,
    min_confidence_decimal_odds: float = 1.15,
    max_confidence_decimal_odds: float = 2.05,
    min_confidence_edge: float = -0.12,
    min_confidence_combined_odds_2: float = 1.60,
    min_confidence_combined_odds_3: float = 2.00,
    include_non_official_markets: bool = False,
    allow_observe_legs: bool = False,
) -> dict[str, Any]:
    """
    Recommend 2串1/3串1 tickets from MCP shortlist picks.

    Use this when the user asks for 竞彩串单, 串关, 2串1, 3串1, or combined tickets.
    Default parlay_mode="confidence" targets higher-hit-rate official HAD legs,
    accepting lower odds and small negative EV proxy for parlays. Use
    parlay_mode="value" for strict positive-edge combinations.
    The tool first runs MCP shortlist selection, then builds combinations inside MCP.
    Default window is next 24 hours, because Jingcai parlays are not near-kickoff-only.
    By default this returns only 1X2 legs marked as jingcai_supported, because they
    map cleanly to 胜平负-style Jingcai output. Asian handicap and over/under legs
    are included only when include_non_official_markets=True and must not be
    described as official Jingcai odds. Downstream agents must display returned
    parlay_tickets and must not create extra combinations outside MCP.
    """
    return await sources.recommend_jingcai_parlay(
        query=query or "",
        league=league or None,
        as_of=as_of or None,
        timezone_name=timezone_name or "Asia/Shanghai",
        window_minutes=window_minutes or (24 * 60),
        top_n=top_n or 3,
        limit=limit or 30,
        min_edge=min_edge,
        min_combined_edge=min_combined_edge,
        max_legs=max_legs or 3,
        parlay_mode=parlay_mode or "confidence",
        min_confidence_leg_probability=min_confidence_leg_probability,
        min_confidence_decimal_odds=min_confidence_decimal_odds,
        max_confidence_decimal_odds=max_confidence_decimal_odds,
        min_confidence_edge=min_confidence_edge,
        min_confidence_combined_odds_2=min_confidence_combined_odds_2,
        min_confidence_combined_odds_3=min_confidence_combined_odds_3,
        include_non_official_markets=include_non_official_markets,
        allow_observe_legs=allow_observe_legs,
    )


@mcp.tool()
async def run_historical_backtest(
    division: str = "E0",
    season: str = "",
    min_training_samples: int = 20,
    edge_threshold: float = 0.02,
    stake: float = 1.0,
    max_samples: int | None = None,
) -> dict[str, Any]:
    """
    Run a Football-Data walk-forward paper backtest for one league season.

    Use this to audit whether MCP model_engine probabilities beat the market
    baseline before trusting shortlist or parlay recommendations. The backtest
    builds form features only from matches earlier than each evaluated sample.
    Profit is flat-stake paper trading, not real-money authorization.
    """
    return await backtest.run_football_data_backtest(
        division=division or "E0",
        season=season or "",
        min_training_samples=min_training_samples or 20,
        edge_threshold=edge_threshold,
        stake=stake or 1.0,
        max_samples=max_samples,
    )


@mcp.tool()
async def run_backtest_sweep(
    divisions: list[str] | None = None,
    seasons: list[str] | None = None,
    edge_thresholds: list[float] | None = None,
    min_training_samples_options: list[int] | None = None,
    stake: float = 1.0,
    max_samples: int | None = None,
    include_records: bool = False,
) -> dict[str, Any]:
    """
    Sweep Football-Data walk-forward backtests across leagues, seasons, and recommendation thresholds.

    Use this before changing model weights or enabling paper/live automation. The
    result ranks configs, summarizes league/season segments, warns on small
    samples, and returns an automation_readiness gate.
    """
    return await backtest.run_backtest_sweep(
        divisions=divisions,
        seasons=seasons,
        edge_thresholds=edge_thresholds,
        min_training_samples_options=min_training_samples_options,
        stake=stake or 1.0,
        max_samples=max_samples,
        include_records=include_records,
    )


@mcp.tool()
async def run_holdout_validation(
    divisions: list[str] | None = None,
    training_seasons: list[str] | None = None,
    validation_seasons: list[str] | None = None,
    edge_thresholds: list[float] | None = None,
    min_training_samples_options: list[int] | None = None,
    stake: float = 1.0,
    max_samples: int | None = None,
    min_selection_bets: int = 30,
    min_validation_bets: int = 50,
) -> dict[str, Any]:
    """
    Select parameters on training seasons, then score the selected config on holdout seasons.

    Use this after run_backtest_sweep to test whether historical signals survive
    sample-out validation. Validation seasons never participate in parameter
    selection. A pass still authorizes paper trading only, not real-money betting.
    """
    return await backtest.run_holdout_validation(
        divisions=divisions,
        training_seasons=training_seasons,
        validation_seasons=validation_seasons,
        edge_thresholds=edge_thresholds,
        min_training_samples_options=min_training_samples_options,
        stake=stake or 1.0,
        max_samples=max_samples,
        min_selection_bets=min_selection_bets,
        min_validation_bets=min_validation_bets,
    )


@mcp.tool()
async def run_top_k_confidence_backtest(
    divisions: list[str] | None = None,
    training_seasons: list[str] | None = None,
    validation_seasons: list[str] | None = None,
    min_training_samples: int = 120,
    top_k_options: list[int] | None = None,
    probability_floors: list[float] | None = None,
    stake: float = 1.0,
    max_samples: int | None = None,
    bucket_size: float = 0.05,
    prior_strength: int = 20,
    include_records: bool = False,
) -> dict[str, Any]:
    """
    Backtest selecting only the highest calibrated-confidence 1X2 picks.

    Use this for requests like "只从一批比赛里挑最稳的一场". Training seasons build
    empirical probability calibration buckets; validation seasons score Top-K
    picks only. Results are paper-trading diagnostics, not real-money approval.
    """
    return await backtest.run_top_k_confidence_backtest(
        divisions=divisions,
        training_seasons=training_seasons,
        validation_seasons=validation_seasons,
        min_training_samples=min_training_samples or 120,
        top_k_options=top_k_options,
        probability_floors=probability_floors,
        stake=stake or 1.0,
        max_samples=max_samples,
        bucket_size=bucket_size or 0.05,
        prior_strength=prior_strength or 20,
        include_records=include_records,
    )


@mcp.tool()
async def get_match_odds(
    query: str,
    home_team: str = "",
    away_team: str = "",
    league: str = "",
    as_of: str = "",
    timezone_name: str = "Asia/Shanghai",
    window_hours: int = 24,
) -> dict[str, Any]:
    """
    Return numeric 1X2, Asian handicap, and over/under odds for one match.

    For Dongqiudi matches this fetches the match odds index and returns
    preferred_moneyline_1x2, preferred_asian_handicap, the full
    asian_handicap_markets list, and asian_handicap_consensus. Use one supported
    market at a time for calculations, but inspect consensus before Asian
    handicap recommendations. Keep schedule snapshots as backup evidence only.
    Leave as_of empty unless the user explicitly supplied an absolute local time.
    """
    best, search = await sources.get_best_match(
        query,
        home_team=home_team or None,
        away_team=away_team or None,
        league=league or None,
        as_of=as_of or None,
        timezone_name=timezone_name or "Asia/Shanghai",
        window_hours=window_hours or 24,
    )
    if not best:
        return {"status": "not_found", "search": search}
    odds = best.get("odds_summary") or {}
    match_context = None
    if best.get("source_name") == "dongqiudi" and best.get("match_id"):
        match_context = await sources.dongqiudi_match_context(str(best["match_id"]))
        odds = sources.merge_odds(odds, ((match_context.get("odds_index") or {}).get("odds") or {}))
    return {
        "status": "ok",
        "match": best,
        "time_window": best.get("time_window"),
        "time_window_policy": search.get("time_window_policy"),
        "odds": odds,
        "match_context_readiness": (match_context or {}).get("readiness") or {},
        "source_policy": (
            "For 1X2 calculations use odds.preferred_moneyline_1x2 when present. "
            "For Asian handicap calculations use odds.preferred_asian_handicap when present, "
            "and inspect odds.asian_handicap_consensus plus odds.asian_handicap_markets before recommendations. "
            "Do not mix schedule_snapshot odds with the preferred market. "
            "Dongqiudi covers broad match lists including J.League; Football-Data covers supported European leagues. "
            "Leisu can corroborate Chinese schedule links but is not an odds source unless explicit odds numbers are returned."
        ),
    }


@mcp.tool()
async def analyze_single_match(
    query: str,
    home_team: str = "",
    away_team: str = "",
    league: str = "",
    as_of: str = "",
    timezone_name: str = "Asia/Shanghai",
    window_hours: int = 24,
    include_source_probe: bool = True,
) -> dict[str, Any]:
    """
    Resolve one match and aggregate schedule, odds, time-window status, recent form, normalized lineup_analysis,
    market_intelligence, analysis_pack, and betting_decision_support.

    This tool is the preferred first call for single-match betting analysis. Leave
    as_of empty unless the user explicitly supplied an absolute local time; empty
    as_of uses the server's current Asia/Shanghai time. If match_context.lineup is
    returned, downstream agents should use lineup_analysis, respect its warnings,
    and ignore raw formation codes such as formation_raw when formation_valid is false.
    Downstream agents must distinguish betting_decision_support.blocking_flags from
    caution_flags: only blocking_flags force no-bet; caution_flags reduce stake or
    require conditional observation. analysis_pack gives agents a compact data
    coverage map and structured model inputs; market_intelligence summarizes 1X2,
    Asian handicap, and over/under consensus without replacing raw odds.
    """
    return await sources.analyze_single_match(
        query,
        home_team=home_team or None,
        away_team=away_team or None,
        league=league or None,
        as_of=as_of or None,
        timezone_name=timezone_name or "Asia/Shanghai",
        window_hours=window_hours or 24,
        include_source_probe=include_source_probe,
    )


def main() -> None:
    _start_auto_learning_daemon_if_enabled()
    transport = os.getenv("FOOTBALL_DATA_MCP_TRANSPORT", "streamable-http")
    if transport not in {"stdio", "sse", "streamable-http"}:
        raise ValueError(f"Unsupported transport: {transport}")
    mcp.run(transport=transport)


def _start_auto_learning_daemon_if_enabled() -> None:
    enabled = os.getenv("FOOTBALL_DATA_AUTO_LEARNING_ENABLED", "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return
    config = _auto_learning_config_from_env()

    def runner() -> None:
        asyncio.run(
            sources.auto_learning_daemon(
                **config,
            )
        )

    thread = threading.Thread(target=runner, name="football-data-auto-learning", daemon=True)
    thread.start()


def _auto_learning_config_from_env() -> dict[str, Any]:
    def env_bool(name: str, default: bool) -> bool:
        raw = os.getenv(name, "true" if default else "false").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    return {
        "interval_seconds": int(os.getenv("FOOTBALL_DATA_AUTO_LEARNING_INTERVAL_SECONDS", "120") or "120"),
        "top_n": int(os.getenv("FOOTBALL_DATA_AUTO_LEARNING_TOP_N", "12") or "12"),
        "limit": int(os.getenv("FOOTBALL_DATA_AUTO_LEARNING_LIMIT", "80") or "80"),
        "timezone_name": os.getenv("FOOTBALL_DATA_AUTO_LEARNING_TIMEZONE", "Asia/Shanghai"),
        "asian_window_minutes": int(os.getenv("FOOTBALL_DATA_AUTO_LEARNING_ASIAN_WINDOW_MINUTES", "10") or "10"),
        "parlay_window_minutes": int(
            os.getenv("FOOTBALL_DATA_AUTO_LEARNING_PARLAY_WINDOW_MINUTES", "10") or "10"
        ),
        "learning_observation_limit": int(os.getenv("FOOTBALL_DATA_AUTO_LEARNING_OBSERVATION_LIMIT", "30") or "30"),
        "analysis_candidate_limit": int(os.getenv("FOOTBALL_DATA_AUTO_LEARNING_ANALYSIS_CANDIDATE_LIMIT", "80") or "80"),
        "analysis_concurrency": int(os.getenv("FOOTBALL_DATA_AUTO_LEARNING_ANALYSIS_CONCURRENCY", "10") or "10"),
        "shadow_prediction_limit": int(os.getenv("FOOTBALL_DATA_AUTO_LEARNING_SHADOW_PREDICTION_LIMIT", "100") or "100"),
        "include_market_snapshot_sync": env_bool("FOOTBALL_DATA_AUTO_SYNC_LEISU_ODDS", True),
        "market_snapshot_window_minutes": int(
            os.getenv("FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_WINDOW_MINUTES", "1440") or "1440"
        ),
        "market_snapshot_limit": int(os.getenv("FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_LIMIT", "80") or "80"),
        "market_snapshot_concurrency": int(os.getenv("FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_CONCURRENCY", "4") or "4"),
        "market_snapshot_require_quality_gate": env_bool("FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_REQUIRE_QUALITY_GATE", True),
        "include_snapshot_reanalysis": env_bool("FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_REANALYSIS", True),
        "snapshot_reanalysis_limit": int(os.getenv("FOOTBALL_DATA_AUTO_LEARNING_REANALYSIS_LIMIT", "20") or "20"),
        "snapshot_reanalysis_concurrency": int(os.getenv("FOOTBALL_DATA_AUTO_LEARNING_REANALYSIS_CONCURRENCY", "4") or "4"),
    }


if __name__ == "__main__":
    main()

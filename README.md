# Football Data MCP

Standalone MCP service for single-match football analysis.

Reference modeling principles:

- [`docs/reference-modeling-principles.md`](./docs/reference-modeling-principles.md)

Primary numeric odds source:

- `https://www.football-data.co.uk/fixtures.csv`

The service also probes public football pages such as OddsPortal, ScoreBat, Soccerway, Flashscore mobile, and Sky Sports. These are used as corroborating schedule/context sources when parseable. Football-Data remains the strongest numeric odds source because it returns concrete bookmaker, max, and average odds through ordinary HTTP requests.

Free candidate odds sites worth evaluating next for sparse fallback snapshots:

- `BetExplorer`
- `7M`
- `Titan007 / 球探新球`
- `Goaloo`

Current source-evaluation note:

- Prefer `BetExplorer` first when validating a new free fallback odds site: its public football routes and match detail URLs are the most explicit among the current candidates.
- Then try `7M` as an Asian-market-oriented fallback source when you are willing to traverse its score pages into deeper match detail routes.
- Treat `Titan007 / 球探新球` as a later candidate only if connectivity is stable from the current network path.
- Treat `Goaloo` as a later experiment for now: public routes currently return `200` with empty bodies in this environment, so it is not the best first integration target.
- Treat `Nowgoal`, `AiScore`, `Oddspedia`, `FootballAnt`, and similar Cloudflare / WAF-heavy sites as browser-session fallback candidates only, not as the next default source.
- Keep the acquisition model conservative: sparse anchor snapshots (`opening`, `decision`, `latest`, `closing`), low-frequency serial fetches, persistent browser sessions only when necessary, and multi-source fallback rather than one high-frequency scraper.

BetExplorer integration status:

- Match discovery is already viable from public football listing pages.
- Match detail pages expose stable market-tab URLs for `1x2`, `over-under`, and `asian-handicap`.
- The actual odds table is not present in the first HTML response; current reverse-engineering indicates the next step should read the site AJAX chain around:
  - `/gres/ajax/betting-type-tabs.php`
  - `/gres/ajax/match-content.php`
- This means BetExplorer should be integrated as a low-frequency structured fallback only after those AJAX responses are normalized into sparse `market_snapshots`.

Run locally:

```bash
uv run python -m football_data_mcp.server
```

Run with Docker:

```bash
docker compose up -d --build
```

Quality gate:

```bash
scripts/check.sh
```

The local gate runs Python lint/type checks, the full backend test suite, frontend unit tests, and the production frontend build. CI runs the same checks on pull requests and pushes to `main`.
When working on the host machine, prefer `uv run ...` instead of bare `python`/`pytest` so commands use the project environment rather than the shell's global PATH.

MCP endpoint:

```text
http://127.0.0.1:8910/mcp
```

Mobile API / PWA / iOS:

- The repo now also exposes a compact mobile facade for the PWA at `/mobile` and the personal iOS client in [`ios/FootballProbabilityApp`](./ios/FootballProbabilityApp).
- Current mobile endpoints:
  - `GET /api/mobile/matches`
  - `GET /api/mobile/analysis`
- The mobile facade is intentionally smaller than `/api/dashboard`; it is for match browsing and single-match explanation, not for operating the whole learning loop.
- Every mobile response must keep the product in research mode:
  - `modelReadiness` tells the client whether latest holdout validation is `not_ready`, `watchlist`, `paper_trade_only`, or better.
  - `oddsSourceHealth` tells the client whether fresh independent odds currently come from `leisu`, a fallback such as `oddsportal_scraper`, or no production-ready source at all.
- Clients should not present the output as production automation when `modelReadiness.productionApproved=false`, and should visually warn when `oddsSourceHealth.status != "healthy"`.

Tools:

- `source_health`
- `sync_market_snapshots`
- `sync_leisu_odds_snapshots`
- `run_auto_learning_cycle`
- `settle_learning_recommendations`
- `learning_calibration_status`
- `get_match_data_bundle`
- `probe_sources`
- `search_fixtures`
- `list_matches`
- `shortlist_value_matches`
- `recommend_jingcai_parlay`
- `run_historical_backtest`
- `run_backtest_sweep`
- `run_holdout_validation`
- `run_top_k_confidence_backtest`
- `get_match_odds`
- `analyze_single_match`

Analysis model:

- `analyze_single_match` and shortlist/parlay tools use a market-anchored Poisson scoreline model when enough 1X2 or totals data is present.
- The model returns `model_engine.version`, `method`, expected goals, top scorelines, 1X2 probabilities, Asian handicap settlement probabilities, over/under probabilities, and market edges.
- Jingcai analysis treats `价值` as 命中率 + 赔率支撑/组合性价比, not pure EV hunting. Agents should first review fundamentals, historical record/head-to-head, current form, injuries, schedule, tactical matchup, and odds movement, then ask whether the price is过热,诱高, and whether it supports the team's real ability.
- `shortlist_value_matches` defaults to `mode="confidence"` and ranks shortlisted candidates by calibrated probability when available, then reliability, raw model probability, and edge as a secondary diagnostic. Explicit `mode="value"` is for strict edge/EV diagnostics, not the normal Jingcai selection objective.
- `recommend_jingcai_parlay` defaults to `parlay_mode="confidence"` for 竞彩组合分析: it uses official Sporttery HAD legs, ranks by estimated hit probability first, and can surface lower-odds structures with small negative EV proxy plus explicit risk flags. Use `parlay_mode="value"` only when you intentionally want strict positive-edge组合 diagnostics.
- The shortlist default now analyzes all 30 listed candidates (`limit=30`, `analysis_candidate_limit=30`) with concurrency 6, so a 30-match window is not silently cut down to 12 deep analyses.
- `shortlist_value_matches(target_market="asian_handicap")` is disabled in the MCP. Use `target_market="1x2"` for 胜平负, `target_market="jingcai_hhad"` when official 让球胜平负 odds are available, and treat Asian handicap only as supporting context inside single-match analysis.
- Walk-forward analysis now also exposes `team_strength.rolling_elo`, an internal Elo context built only from completed matches before the evaluated fixture. It is available for audit and future calibration.
- The default model reports `expected_goals.strength_goal_diff_hint` when rolling Elo is present, but leaves `strength_goal_diff_loss_weight=0.0` until holdout validation proves that Elo should move probabilities. This prevents an unvalidated strength prior from degrading market-baseline accuracy.
- The model is still an auditable analysis-support layer, not a backtested automated betting system. `model_engine.model_quality.limits` and `betting_decision_support.risk_overlay` should be shown when explaining analysis results.

Backtesting:

- `run_historical_backtest` loads a Football-Data season CSV for one division and runs a walk-forward paper backtest.
- Each evaluated match builds recent-form and rolling Elo features only from matches with earlier kickoff times; future rows are not used for form or team-strength features.
- It reports model-vs-market `log_loss_1x2`, `brier_score_1x2`, calibration buckets, flat-stake paper ROI, and per-match paper prediction records.
- Treat negative or market-lagging results as a no-automation signal. The backtest is designed to prevent shortlist/parlay tools from being trusted before they beat the market baseline over enough historical samples.
- `run_backtest_sweep` scans multiple divisions, seasons, edge thresholds, and warmup sizes. It returns `best_configs`, `worst_configs`, `league_summary`, `season_summary`, `sample_size_warnings`, and an `automation_readiness` gate.
- `run_holdout_validation` separates parameter selection from verification: training seasons select the best config, validation seasons only score that preselected config. Passing this gate still means paper trading only.
- `run_top_k_confidence_backtest` trains empirical confidence calibration buckets on training seasons, then validates "only pick Top K highest-confidence matches" on holdout seasons. This is the right diagnostic for "只挑最稳的一场/几场".
- Current empirical gate: the 5-league holdout (`E0`, `SP1`, `I1`, `D1`, `F1`; training `2122`-`2425`; validation `2526`) remains `not_ready`. Naive rolling-Elo probability pushes worsened log-loss, so Elo is currently context-only rather than an automated betting signal.
- Current Top-K confidence diagnostic: using `2122`-`2425` as calibration seasons and `2526` as validation, Top 1 with calibrated probability floor `0.65` hit 62/84 (`73.8%`) but ROI was `-7.3%`. This supports "higher hit-rate candidate selection", not profitable automation.

Paper learning loop:

- `run_auto_learning_cycle` records future-window Jingcai-first 1X2 analysis candidates and Jingcai combination diagnostics into a local SQLite learning database, then optionally settles completed matches and recomputes calibration buckets. It never places real-money bets. Asian handicap sampling is disabled in the MCP.
- `settle_learning_recommendations` accepts explicit score rows or attempts public-source score discovery, then settles open paper records for 1X2, Jingcai HHAD, and Asian handicap markets. The function name is legacy; the product mode is analysis-only.
- Paper prediction records are keyed by match/market/selection/line so repeated background cycles do not over-count the same paper signal. Jingcai parlay tickets are tracked for audit but are not left in single-match `open` settlement queues.
- Background learning also records a bounded set of analyzed Jingcai shortlist rejections as `*_observation` rows. These are not user-facing conclusions; they are paper observations used to calibrate whether the model probability is honest across more market states.
- Background shortlist analysis now also writes a separate shadow prediction pool. Shadow rows include both accepted analysis candidates and rejected analyzed candidates, plus rejection reason, thresholds, quality evidence, selected market, model probability, odds, edge, compact `model_engine` evidence, and later settlement metrics. These rows increase validation sample size without increasing user-facing conclusions.
- `sync_leisu_odds_snapshots` can persist gated Leisu multi-company odds into the local snapshot store. It first tries the Leisu mobile API, including the mobile `auth_key` signature, Aliyun WAF `acw_sc__v2` challenge, encrypted response decoding, and per-company odds-detail timelines; then it falls back to proxy/direct HTML parsing. When Leisu returns an Aliyun interactive slider page, the direct mobile path opens a longer circuit breaker and reports that a cookie or proxy is required instead of repeatedly hammering the upstream. Each accessible page is expanded into 1X2, Asian handicap, and over/under snapshot rows by bookmaker, market, selection, line, source timestamp, and fetched timestamp; unchanged rows are de-duplicated by a stable snapshot key. Downstream audit should prioritize sparse anchor points such as opening, decision-time, latest, and closing instead of assuming that every match needs a dense full-history curve.
- `learning_calibration_status` reports record counts and exact plus broad calibration buckets by market, league, line, odds range, and probability range. Live calibration only applies buckets with enough settled samples and shrinks empirical hit rate toward the raw model probability.
- `shortlist_value_matches` returns `funnel_report`, which explains how many candidates were listed, analyzed, rejected, returned, and why they were rejected. This is the first place to inspect when prediction volume looks too low.
- Settlement also refreshes a machine-readable `strategy_state` for Jingcai 1X2 confidence selection by default. Probability calibration still uses all settled paper prediction and observation rows, but strategy threshold tuning only uses positive-signal rows (`immediate_bet` / `condition_observe`); `no_value` observations remain calibration evidence rather than strategy ROI.
- Docker Compose enables the background paper-learning loop by default with `FOOTBALL_DATA_AUTO_LEARNING_ENABLED=true`. It stores data in `/data/football_data_mcp_learning.sqlite3`, runs every 120 seconds, times out a stuck cycle after 300 seconds (`FOOTBALL_DATA_AUTO_LEARNING_CYCLE_TIMEOUT_SECONDS=300`), caps each single-match shortlist analysis at 45 seconds (`FOOTBALL_DATA_AUTO_LEARNING_ANALYSIS_TIMEOUT_SECONDS=45`), and only analyzes/persists Jingcai predictions for matches kicking off in the next 10 minutes (`FOOTBALL_DATA_AUTO_LEARNING_JINGCAI_WINDOW_MINUTES=10`, legacy fallback `FOOTBALL_DATA_AUTO_LEARNING_ASIAN_WINDOW_MINUTES=10`, `FOOTBALL_DATA_AUTO_LEARNING_PARLAY_WINDOW_MINUTES=10`, `FOOTBALL_DATA_AUTO_LEARNING_TOP_N=12`, `FOOTBALL_DATA_AUTO_LEARNING_LIMIT=80`, `FOOTBALL_DATA_AUTO_LEARNING_ANALYSIS_CANDIDATE_LIMIT=80`, `FOOTBALL_DATA_AUTO_LEARNING_ANALYSIS_CONCURRENCY=10`, `FOOTBALL_DATA_AUTO_LEARNING_SHADOW_PREDICTION_LIMIT=100`, `FOOTBALL_DATA_AUTO_LEARNING_OBSERVATION_LIMIT=30`). Leisu odds snapshot collection is disabled by default (`FOOTBALL_DATA_AUTO_SYNC_LEISU_ODDS=false`) because the upstream uses interactive WAF checks; enable it only after an authorized proxy/session is ready. Its match window remains wider when enabled (`FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_WINDOW_MINUTES=1440`, `FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_LIMIT=80`) so the system can accumulate enough key anchor points before kickoff. User-facing shortlist requests still keep their explicit/default time window and conservative `top_n`.
- Docker Compose passes through optional Leisu access variables: `LEISU_ODDS_PROXY_URL`, `LEISU_COOKIE`, and `LEISU_ACW_SC_V2`. For Leisu's current interactive slider flow, run the local manual browser proxy and set `LEISU_ODDS_PROXY_URL=http://host.docker.internal:8918/leisu/odds/{match_id}`. `LEISU_MOBILE_DETAIL_COMPANY_LIMIT` controls how many bookmakers per market get full historical timelines (`0` means all, default `3` to reduce rate-limit pressure). If Leisu changes WAF behavior, rate-limits the host, or local Node.js is unavailable, the sync tool degrades without inventing prices.
- When Leisu odds remain unstable, OddsPortal can be used as a fallback odds snapshot producer instead of replacing the whole fixture/score source chain. `sync_oddsportal_odds_snapshots` accepts explicit event URLs, defaults to `asian_handicap`, decrypts the OddsPortal market payload, and writes the same `market_snapshots` table used by charts, CLV, and model audit. `/api/sources/odds/oddsportal/sync` queues the fallback sync through the configured task backend; pass `resume_failed=true` to retry failed/empty OddsPortal URLs from `odds_source_sync_state`, or pass `auto_discover=true` with `discovery_urls`/`FOOTBALL_DATA_ODDSPORTAL_DISCOVERY_URLS` so open prediction targets are matched against OddsPortal listing pages before queuing. If the open ledger is empty, the service falls back to recent `analysis_odds` events as discovery seeds, then uses the built-in league-to-OddsPortal listing map for common leagues before falling back to the football landing page. Docker Compose enables this fallback ability by default (`FOOTBALL_DATA_AUTO_SYNC_ODDSPORTAL_ODDS=true`, `FOOTBALL_DATA_ODDSPORTAL_SCRAPER_ENABLED=true`), but the auto-learning daemon first checks `/api/sources/odds/status`: if Leisu or another independent odds source is fresh, OddsPortal is skipped; if only analysis-derived snapshots are fresh, OddsPortal auto-discovery is queued. Limits are controlled by `FOOTBALL_DATA_AUTO_LEARNING_ODDSPORTAL_SNAPSHOT_LIMIT` and `FOOTBALL_DATA_AUTO_LEARNING_ODDSPORTAL_TARGET_LIMIT`. `/api/sources/odds/status` plus dashboard `odds_source_status` expose queued/running/failed/succeeded rows, target source, active source, freshness, production readiness, and the next operator action.

Leisu manual browser proxy:

```bash
uv sync --extra browser-proxy
uv run python -m playwright install chromium
uv run --extra browser-proxy python -m scripts.leisu_browser_proxy --port 8918 --profile-dir .leisu-browser-profile
```

The proxy now also exposes lightweight session-health endpoints:

- `GET /health`
- `GET /leisu/session`

`DataSourceService.odds_source_status()` reads that browser-session state when available, so the backend can distinguish "needs manual verification" from "session ready but snapshots not refreshed yet". See [docs/browser-assisted-crawler-stack.md](./docs/browser-assisted-crawler-stack.md).

If you want to bootstrap the same persistent profile with `Crawlee + Playwright` instead of the lightweight proxy flow:

```bash
uv sync --extra crawler-runtime
uv run --extra crawler-runtime python -m scripts.leisu_crawlee_session --match-id 4512919
```

You can also enqueue the same Leisu session bootstrap through the backend job system:

- `POST /api/sources/odds/leisu/session/refresh`

And the health/runtime state is now visible from:

- `GET /api/sources/odds/status`
- `GET /api/health`

League blocking:

- The backend now computes `league_breakdown` and can automatically block long-term losing leagues.
- The repo also ships a conservative default blocked set for obvious losing fringe leagues seen in prior paper-trade runs: `南球杯`、`阿大都乙`、`解放者杯`、`澳足总`、`冈比亚超`。
- Manual overrides can be added through `FOOTBALL_DATA_LEAGUE_BLOCKLIST` (comma-separated); env values are merged on top of the repo defaults.

If Leisu keeps rejecting the slider in the Playwright browser, use a real local Chrome profile instead:

```bash
open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir="$HOME/.leisu-real-chrome-profile"
uv run --extra browser-proxy python -m scripts.leisu_browser_proxy --port 8918 --connect-cdp http://127.0.0.1:9222
```

In that Chrome window, open `https://m.leisu.com/` first and manually browse a match page until verification passes. Keep `FOOTBALL_DATA_AUTO_SYNC_LEISU_ODDS=false` while authorizing so the backend does not generate a request burst during the slider challenge; re-enable it only after the proxy returns real `euro` / `asia` / `size` data. Background Leisu snapshot sync also defaults to `FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_REQUIRES_LEISU_PROXY=true`, so turning on `FOOTBALL_DATA_AUTO_SYNC_LEISU_ODDS=true` will skip Leisu odds collection unless `LEISU_ODDS_PROXY_URL` is configured. When `LEISU_ODDS_PROXY_URL` is configured, snapshot sync is forced to serial requests and capped by `LEISU_PROXY_SYNC_LIMIT` (default `12`) with `LEISU_PROXY_REQUEST_SPACING_SECONDS` (default `2.0`) between requests, because request bursts are a strong risk signal for Leisu/Alibaba WAF.

Then configure Docker Compose to use the authorized local session:

```bash
LEISU_ODDS_PROXY_URL='http://host.docker.internal:8918/leisu/odds/{match_id}' docker compose up -d --force-recreate football-data-mcp
```

The proxy opens a real browser. When the proxy response says `interactive_captcha` or `forbidden`, complete the Leisu slider manually in that browser and retry. The profile directory stores the authorized session; do not expose the proxy outside localhost.
- Dashboard API CORS is allowlist-based through `FOOTBALL_DATA_DASHBOARD_CORS_ORIGINS` and defaults to local dashboard origins only. `/api/db/janitor?execute=true` requires `FOOTBALL_DATA_ADMIN_TOKEN` plus the matching `X-Admin-Token` header; without it, the endpoint remains dry-run/read-only.

Dashboard:

- Docker Compose also starts a read-only frontend at `http://localhost:8920`. The frontend image serves the locally built `frontend/dist`, so run `npm run build` in `frontend/` before rebuilding the dashboard container after UI changes.
- The dashboard does not expose search boxes or query inputs. It polls `/api/dashboard`, which reads persisted MCP paper-learning state, current Jingcai `strategy_state`, primary/Jingcai picks, legacy Asian-handicap picks, candidate filter reasons, recent settlements, and learning events.
- The dashboard model audit reads compact `model_engine` evidence when available and falls back to legacy candidate summaries for older rows, so model usage and market anchoring remain visible without rerunning historical predictions. Legacy rows cannot recover historical rho internals that were not persisted.
- Match rows expose optional `home_team_logo_url` and `away_team_logo_url` fields. The UI renders real provider crests when present and falls back to deterministic team badges when persisted data only has team names.
- The dashboard now also shows local sparse odds-snapshot coverage from the snapshot store, including source, market types, snapshot count, covered matches, bookmaker count, and latest fetch time.
- The frontend is a cockpit for monitoring the automatic loop; it does not place bets and does not trigger real-money actions.

Example:

```python
from football_data_mcp import backtest

result = await backtest.run_football_data_backtest(
    division="E0",
    season="2526",
    min_training_samples=40,
    edge_threshold=0.02,
)
```

Sweep example:

```python
result = await backtest.run_backtest_sweep(
    divisions=["E0", "SP1", "I1", "D1", "F1"],
    seasons=["2122", "2223", "2324", "2425", "2526"],
    edge_thresholds=[0.01, 0.02, 0.03, 0.04, 0.05],
    min_training_samples_options=[20, 40, 80, 120],
)
```

Holdout validation example:

```python
result = await backtest.run_holdout_validation(
    divisions=["E0", "SP1", "I1", "D1", "F1"],
    training_seasons=["2122", "2223", "2324", "2425"],
    validation_seasons=["2526"],
    edge_thresholds=[0.01, 0.02, 0.03, 0.04, 0.05],
    min_training_samples_options=[20, 40, 80, 120],
)
```

Top-K confidence example:

```python
result = await backtest.run_top_k_confidence_backtest(
    divisions=["E0", "SP1", "I1", "D1", "F1"],
    training_seasons=["2122", "2223", "2324", "2425"],
    validation_seasons=["2526"],
    top_k_options=[1, 2, 3],
    probability_floors=[0.0, 0.55, 0.6, 0.65],
)
```

Next-hour Jingcai 1X2 balanced shortlist:

```python
result = await sources.shortlist_value_matches(
    window_minutes=60,
    mode="balanced",
    target_market="1x2",
    analysis_candidate_limit=30,
    analysis_concurrency=6,
    min_calibrated_probability=0.58,
    min_decimal_odds=1.65,
    max_decimal_odds=2.05,
    min_value_edge=0.02,
    top_n=3,
)
```

Odds quality contract:

- `get_match_odds` and `analyze_single_match` return `odds.quality_contract` when a preferred 1X2 market is available.
- Asian handicap fields remain available as supporting context (`preferred_asian_handicap`, `asian_handicap_markets`, `asian_handicap_consensus`) for line distribution, latest market, main line, freshness span, and preferred-vs-consensus warnings, but they are not final MCP target markets.
- The contract includes raw implied probabilities, normalized probabilities, `overround`, `payout_rate`, key anchor movement (opening / latest and, when available, decision / closing), and timestamp quality.
- Downstream agents should treat `quality_contract.can_use_for_calculation=false` or `quality.flags` hard flags as observation/no-bet input unless another explicit source resolves the issue.
- Timestamp warnings such as `future_source_timestamp` mean the provider's timestamp field is unreliable. The returned odds can still be used as the fetched response snapshot when `can_use_for_calculation=true`, but the timestamp must not be used for freshness or dense time-series analysis.

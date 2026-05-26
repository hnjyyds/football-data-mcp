# Football Data MCP

Standalone MCP service for single-match football analysis.

Primary numeric odds source:

- `https://www.football-data.co.uk/fixtures.csv`

The service also probes public football pages such as OddsPortal, ScoreBat, Soccerway, Flashscore mobile, and Sky Sports. These are used as corroborating schedule/context sources when parseable. Football-Data remains the strongest numeric odds source because it returns concrete bookmaker, max, and average odds through ordinary HTTP requests.

Run locally:

```bash
python -m football_data_mcp.server
```

Run with Docker:

```bash
docker compose up -d --build
```

MCP endpoint:

```text
http://127.0.0.1:8910/mcp
```

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
- `shortlist_value_matches` defaults to `mode="confidence"` and ranks shortlisted candidates by calibrated probability when available, then reliability, raw model probability, and edge. Explicit `mode="value"` keeps the edge/value-oriented ranking.
- `recommend_jingcai_parlay` defaults to `parlay_mode="confidence"` for 竞彩串关: it uses official Sporttery HAD legs, ranks by estimated hit probability first, and can accept lower odds plus small negative EV proxy with explicit risk flags. Use `parlay_mode="value"` when you want strict positive-edge串关 only.
- The shortlist default now analyzes all 30 listed candidates (`limit=30`, `analysis_candidate_limit=30`) with concurrency 6, so a 30-match window is not silently cut down to 12 deep analyses.
- For "next hour, safest Asian handicap with odds not crushed" requests, call `shortlist_value_matches(window_minutes=60, mode="balanced", target_market="asian_handicap")`. `mode="balance"` is accepted as an alias. Balanced mode requires a minimum calibrated probability, a decimal-odds range, and positive value edge after break-even probability before ranking.
- For pure "next hour, highest-confidence Asian handicap" requests, call `shortlist_value_matches(window_minutes=60, mode="confidence", target_market="asian_handicap")`. This filters each analyzed match down to Asian handicap candidates before ranking.
- Walk-forward analysis now also exposes `team_strength.rolling_elo`, an internal Elo context built only from completed matches before the evaluated fixture. It is available for audit and future calibration.
- The default model reports `expected_goals.strength_goal_diff_hint` when rolling Elo is present, but leaves `strength_goal_diff_loss_weight=0.0` until holdout validation proves that Elo should move probabilities. This prevents an unvalidated strength prior from degrading market-baseline accuracy.
- The model is still an auditable decision-support layer, not a backtested automated betting system. `model_engine.model_quality.limits` and `betting_decision_support.risk_overlay` should be shown when explaining recommendations.

Backtesting:

- `run_historical_backtest` loads a Football-Data season CSV for one division and runs a walk-forward paper backtest.
- Each evaluated match builds recent-form and rolling Elo features only from matches with earlier kickoff times; future rows are not used for form or team-strength features.
- It reports model-vs-market `log_loss_1x2`, `brier_score_1x2`, calibration buckets, flat-stake paper ROI, and per-match recommendation records.
- Treat negative or market-lagging results as a no-automation signal. The backtest is designed to prevent shortlist/parlay tools from being trusted before they beat the market baseline over enough historical samples.
- `run_backtest_sweep` scans multiple divisions, seasons, edge thresholds, and warmup sizes. It returns `best_configs`, `worst_configs`, `league_summary`, `season_summary`, `sample_size_warnings`, and an `automation_readiness` gate.
- `run_holdout_validation` separates parameter selection from verification: training seasons select the best config, validation seasons only score that preselected config. Passing this gate still means paper trading only.
- `run_top_k_confidence_backtest` trains empirical confidence calibration buckets on training seasons, then validates "only pick Top K highest-confidence matches" on holdout seasons. This is the right diagnostic for "只挑最稳的一场/几场".
- Current empirical gate: the 5-league holdout (`E0`, `SP1`, `I1`, `D1`, `F1`; training `2122`-`2425`; validation `2526`) remains `not_ready`. Naive rolling-Elo probability pushes worsened log-loss, so Elo is currently context-only rather than an automated betting signal.
- Current Top-K confidence diagnostic: using `2122`-`2425` as calibration seasons and `2526` as validation, Top 1 with calibrated probability floor `0.65` hit 62/84 (`73.8%`) but ROI was `-7.3%`. This supports "higher hit-rate candidate selection", not profitable automation.

Paper learning loop:

- `run_auto_learning_cycle` records future-window balanced Asian handicap picks and Jingcai parlay recommendations into a local SQLite learning database, then optionally settles completed matches and recomputes calibration buckets. It never places real-money bets.
- `settle_learning_recommendations` accepts explicit score rows or attempts public-source score discovery, then settles open recommendation records for 1X2, Jingcai HHAD, and Asian handicap markets.
- Recommendation records are keyed by match/market/selection/line so repeated background cycles do not over-count the same paper pick. Jingcai parlay tickets are tracked for audit but are not left in single-match `open` settlement queues.
- Background learning also records a bounded set of analyzed Asian handicap rejections as `*_observation` rows. These are not user-facing recommendations; they are paper observations used to calibrate whether the model probability is honest across more market states.
- Background shortlist analysis now also writes a separate shadow prediction pool. Shadow rows include both accepted picks and rejected analyzed candidates, plus rejection reason, thresholds, quality evidence, selected market, model probability, odds, edge, and later settlement metrics. These rows increase validation sample size without increasing user-facing recommendations.
- `sync_leisu_odds_snapshots` can persist gated Leisu multi-company odds into the local snapshot store. It first tries the Leisu mobile API, including the mobile `auth_key` signature, Aliyun WAF `acw_sc__v2` challenge, encrypted response decoding, and per-company odds-detail timelines; then it falls back to proxy/direct HTML parsing. Each accessible page is expanded into 1X2, Asian handicap, and over/under snapshot rows by bookmaker, market, selection, line, source timestamp, and fetched timestamp; unchanged rows are de-duplicated by a stable snapshot key. The background learning loop now attempts this sync before shortlist analysis so the dashboard and model can use fresh odds snapshots when Leisu access is available.
- `learning_calibration_status` reports record counts and exact plus broad calibration buckets by market, league, line, odds range, and probability range. Live calibration only applies buckets with enough settled samples and shrinks empirical hit rate toward the raw model probability.
- `shortlist_value_matches` returns `funnel_report`, which explains how many candidates were listed, analyzed, rejected, returned, and why they were rejected. This is the first place to inspect when prediction volume looks too low.
- Settlement also refreshes a machine-readable `strategy_state` for balanced Asian handicap selection. Once enough settled samples exist, `shortlist_value_matches(mode="balanced", target_market="asian_handicap")` reads this state by default to tighten probability/value/odds thresholds and use live-calibrated probabilities in the next shortlist cycle.
- Docker Compose enables the background paper-learning loop by default with `FOOTBALL_DATA_AUTO_LEARNING_ENABLED=true`. It stores data in `/data/football_data_mcp_learning.sqlite3`, runs every 120 seconds, and only analyzes/persists predictions for matches kicking off in the next 10 minutes (`FOOTBALL_DATA_AUTO_LEARNING_ASIAN_WINDOW_MINUTES=10`, `FOOTBALL_DATA_AUTO_LEARNING_PARLAY_WINDOW_MINUTES=10`, `FOOTBALL_DATA_AUTO_LEARNING_TOP_N=12`, `FOOTBALL_DATA_AUTO_LEARNING_LIMIT=80`, `FOOTBALL_DATA_AUTO_LEARNING_ANALYSIS_CANDIDATE_LIMIT=80`, `FOOTBALL_DATA_AUTO_LEARNING_ANALYSIS_CONCURRENCY=10`, `FOOTBALL_DATA_AUTO_LEARNING_SHADOW_PREDICTION_LIMIT=100`, `FOOTBALL_DATA_AUTO_LEARNING_OBSERVATION_LIMIT=30`). Odds snapshot collection stays wider by default (`FOOTBALL_DATA_AUTO_SYNC_LEISU_ODDS=true`, `FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_WINDOW_MINUTES=1440`, `FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_LIMIT=80`) so the model can use the accumulated odds timeline from first successful fetch through the latest pre-kickoff refresh. User-facing shortlist requests still keep their explicit/default time window and conservative `top_n`.
- Docker Compose passes through optional Leisu access variables: `LEISU_ODDS_PROXY_URL`, `LEISU_COOKIE`, and `LEISU_ACW_SC_V2`. The default path no longer requires a personal login cookie when the mobile API challenge can be solved locally; `LEISU_MOBILE_DETAIL_COMPANY_LIMIT` controls how many bookmakers per market get full historical timelines (`0` means all, default `3` to reduce rate-limit pressure). If Leisu changes WAF behavior, rate-limits the host, or local Node.js is unavailable, the sync tool degrades without inventing prices.

Dashboard:

- Docker Compose also starts a read-only frontend at `http://localhost:8920`. The frontend image serves the locally built `frontend/dist`, so run `npm run build` in `frontend/` before rebuilding the dashboard container after UI changes.
- The dashboard does not expose search boxes or query inputs. It polls `/api/dashboard`, which reads persisted MCP paper-learning state, current `strategy_state`, Asian handicap picks, candidate filter reasons, recent settlements, and learning events.
- The dashboard now also shows local odds time-series coverage from the snapshot store, including source, market types, snapshot count, covered matches, bookmaker count, and latest fetch time.
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

Next-hour Asian handicap balanced shortlist:

```python
result = await sources.shortlist_value_matches(
    window_minutes=60,
    mode="balanced",
    target_market="asian_handicap",
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
- Asian handicap responses keep `preferred_asian_handicap`, return the full `asian_handicap_markets` list, and add `asian_handicap_consensus` for line distribution, latest market, main line, freshness span, and preferred-vs-consensus warnings.
- The contract includes raw implied probabilities, normalized probabilities, `overround`, `payout_rate`, opening-to-current movement, and timestamp quality.
- Downstream agents should treat `quality_contract.can_use_for_calculation=false` or `quality.flags` hard flags as observation/no-bet input unless another explicit source resolves the issue.
- Timestamp warnings such as `future_source_timestamp` mean the provider's timestamp field is unreliable. The returned odds can still be used as the fetched response snapshot when `can_use_for_calculation=true`, but the timestamp must not be used for freshness or time-series analysis.

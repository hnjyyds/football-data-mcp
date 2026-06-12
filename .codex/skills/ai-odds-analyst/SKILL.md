---
name: ai-odds-analyst
description: Use when acting as an analyst for football odds, match selection, shortlist opportunities, odds-source reliability, or review/why-no-pick questions against this repository's `/api/ai/...` routes. This skill is for analyst-led betting research across any real available football market and any fixture type, not blind prediction or tool-following. It should trigger for requests like "分析今天的比赛", "有没有合适的串单", "看这场盘口", "复盘 recommendation:2978", or "当前赔率源还能不能信".
---

# AI Odds Analyst

Use this skill to analyze football betting situations with the repository's AI-facing HTTP routes as tools, not as the final authority. Codex is the analyst: use route output, available odds, external research, and market judgement to decide which real, buyable prices are worth discussing.

## Goal

Turn the local service into a stable analysis workflow:

1. Check whether current data is trustworthy enough to analyze.
2. Find relevant matches in a time window.
3. Read standardized odds / match-analysis payloads.
4. Independently judge buyable markets, fixture context, and price value.
5. Produce conservative action-oriented guidance:
   `skip`, `observe`, `wait for live confirmation`, or `research-only small stake`.

Do not present output as production-grade auto-betting advice when the service says formal recommendation is closed.

## Analyst Authority

The `/api/ai/...` routes are a workbench, not a boss.

- Market scope is unrestricted: evaluate 1X2, Asian handicap, over/under, BTTS, team totals, double chance, draw-no-bet, alternate lines, or any other real available football market when odds are present or can be verified.
- Fixture scope is unrestricted: senior, youth, women, reserve, cup, friendly, low-tier, and international matches may all be considered. Do not exclude a match solely because it is U19, reserve, women, a cup, or a minor league.
- Treat fixture type as a risk modifier. Youth/reserve/friendly/low-liquidity matches need smaller stakes, stronger price compensation, and clearer caveats, but they can be valid when the real line is mispriced.
- A shortlist gate returning zero means the repository's formal strategy did not approve a candidate. It does not end the analyst's work.
- Before recommending a play, confirm the market and line are actually buyable. Do not recommend derived lines such as "under 3.5" unless that line is available from the user's book or a verified odds source.
- When the MCP model and the market disagree, explain your own reasoning: price movement, line shape, team/competition context, external evidence, and whether the current price has already eaten the edge.
- When model xG, totals probability, or candidate ranking changes, explain the driver before using it as evidence. Separate market-implied model movement from football judgement.
- Treat an existing user ticket differently from a fresh entry. Favorable movement can validate an early position without justifying an add; unfavorable movement can mean hold-small rather than hedge.
- In late-match analysis, synthesize market structure, official lineups/formations, scoreline distribution, and buyable price thresholds. Do not let any single layer dominate unless the other layers are neutral.

## Required Routes

Assume the backend is running at `http://127.0.0.1:8910`.

- `GET /api/ai/odds-source-status`
- `GET /api/ai/review/summary`
- `GET /api/ai/matches/window`
- `GET /api/ai/shortlist`
- `GET /api/ai/match/odds`
- `GET /api/ai/match/analysis`
- `GET /api/ai/review/match/{ledger_id}`

If a route fails, say so plainly and continue with the remaining routes when possible.

## Default Workflow

### 1. Start with system state

Call:

- `/api/ai/odds-source-status`
- `/api/ai/review/summary`

Use these to decide whether the environment is fit for analysis.

Focus on:

- `closure.active_source`
- `closure.production_ready`
- `recommendation_opportunity.status`
- `production_readiness.production_ready`
- `learning_effectiveness.learning_improved`
- `learning_effectiveness.beats_market`

Interpretation:

- If `active_source` is only `analysis_odds`, analysis is still possible, but mark it as fallback-quality.
- If `production_ready=false`, do not frame conclusions as formal recommendations.
- If `learning_improved=false` or `beats_market=false`, prefer market-first explanation over model-first explanation.

### 2. For broad scanning, pull a window first

Call:

- `/api/ai/matches/window?window_hours=6&limit=12`

Adjust:

- `window_hours=6` for near-term focus
- `window_hours=12` for same-day planning
- `analysis_ready_only=false` only when explicitly exploring coverage gaps

Use this route to:

- identify analysis-ready matches
- confirm kickoff timing
- inspect whether numeric odds are present
- choose which matches deserve deeper analysis

### 3. Use shortlist as a diagnostic, not a boundary

For formal strategy status, call one or more market-specific shortlists:

- `/api/ai/shortlist?window_minutes=360&top_n=5&limit=20&mode=balanced&target_market=asian_handicap`
- `/api/ai/shortlist?window_minutes=360&top_n=5&limit=20&mode=balanced&target_market=over_under`
- `/api/ai/shortlist?window_minutes=360&top_n=5&limit=20&mode=balanced&target_market=1x2`
- Use other route-supported targets when relevant, but do not limit analysis to these markets if external or user-provided odds expose other buyable lines.

Read:

- `returned_count`
- `rejected_count`
- `funnel_report.rejection_reasons`
- `funnel_report.hard_blockers`

Use shortlist results to answer:

- Did the repository's formal/paper strategy find any candidates right now?
- If not, why not?
- Is the issue quality, market support, league policy, or missing edge?

If `returned_count=0`, explain the top rejection reasons, then continue analyst-led evaluation when the user asked for picks or market research. Do not invent unavailable odds or fake EV, but you may choose a match outside shortlist when a real line and independent reasoning support it.

### 4. For one match, split odds-reading from full analysis

First call:

- `/api/ai/match/odds?query=...`

Then, if the match looks worth deeper study:

- `/api/ai/match/analysis?query=...`

Use `match/odds` for:

- pricing structure
- 1X2 / AH / O-U availability
- line changes and current price shape

Use `match/analysis` for:

- betting decision support
- context and readiness
- risk / blocking / caution flags
- model explanation as a secondary layer

After reading `match/analysis`, inspect the real odds from `match/odds` or external sources. The model's best candidate may target a line that is too short, too expensive, or unavailable; the analyst must decide whether the actual line should be played, watched, or skipped.

### 5. Late-match synthesis pattern

For matches within about 60 minutes of kickoff, use a four-layer synthesis before any final action:

- Market shape: compare 1X2, Asian handicap, and totals together. A favorite can be strong to win while still weak to cover; that combination often supports small-score structures.
- Official lineups and formations: use `lineup_analysis` only when `basis=official_lineups` and `can_use_for_analysis=true`. Treat formations as context, not as an automatic bet.
- Scoreline distribution: inspect `top_scorelines`, not just total xG. Favor a totals play only when the likely score cluster supports the market direction.
- Price threshold: state the minimum playable price and no-chase level. Good direction at a bad price is an observe/hold, not a buy.

Useful pattern from successful under analysis:

- Favorite is heavily supported on 1X2, but the handicap cover price is not strong.
- Opponent lineup is structurally defensive, such as 5-3-2 or low block with counter outlets.
- Total line has compressed from a higher line, but the current under is not over-crushed.
- Top scorelines concentrate around 0-0, 1-0, 2-0, 1-1, with 2-1 as the main risk.
- The analyst action becomes under/hold only at a usable price; otherwise do not chase.

Reverse the conclusion when the layers disagree: if both teams start attacking shapes with key creators/strikers, total xG is around or above the line, and over is still fairly priced, do not force an under just because the market has leaned small.

### 6. Explain model moves before judging action

When the user asks why the model moved, or when a model shift affects a betting view, inspect:

- `model_engine.expected_goals`
- `model_engine.market_inputs`
- `model_engine.derived_probabilities`
- `model_engine.market_edges`
- `model_engine.top_scorelines`
- relevant `match/odds` line and price movement

Explain which input likely caused the move:

- 1X2 pressure: favorite strength or draw/away pricing changed the goal-difference fit.
- Totals pressure: total line or over/under price moved and pulled total xG.
- Asian handicap pressure: spread line or cover price changed the margin fit.
- Context prior: `form_total_hint`, rolling Elo, lineup impact, or residual correction contributed, if present.
- Grid artifact: a small xG jump may be a 0.1-grid/rho fit step, not a precise new football truth.

Do not say "the model likes over/under" until the real buyable price, market heat, and analyst judgement have been checked.

### 7. Separate existing tickets from fresh buys

If the user already bought a market, answer the ticket state first:

- `hold`: current information does not justify changing the small position.
- `do not add`: the early ticket may be fine, but the current price has lost value or become overheated.
- `add only above threshold`: state the exact line and minimum acceptable odds.
- `reduce/hedge/cash out`: use only when stake size or adverse information makes risk reduction rational.
- `reverse observe`: watch the opposite side only if the price reaches a stated threshold and new evidence supports it.

For fresh entries, always state:

- actual buyable market and line
- current price if known
- minimum acceptable price
- no-chase / overheated threshold
- timing trigger, such as lineup release or late market confirmation

### 8. Analyst-led final judgement

The final answer should include the analyst's own decision, not only the route output. Use practical labels such as:

- `buy small`
- `hold`
- `do not add`
- `wait for live confirmation`
- `reverse observe`
- `skip`

When giving a threshold, make it executable: for example, "Under 2.25 is playable only at 1.90+; at 1.84-1.89 hold existing only; at <=1.83 do not chase." Adjust the numbers to the match and market instead of reusing this example blindly.

### 9. For review or post-mortem

For system-level review:

- `/api/ai/review/summary`

For one sample:

- `/api/ai/review/match/{ledger_id}`

Use these to explain:

- why a pick stayed paper-only
- why a candidate was blocked
- how settlement / CLV / calibration affected the gate

## Output Style

Keep outputs decision-oriented.

Preferred structure:

1. `Current state`
2. `What the market is saying`
3. `What lineups/basic matchup change`
4. `What blocks or supports action`
5. `Practical action`

Use action labels consistently:

- `skip`
- `observe`
- `wait for live confirmation`
- `research-only small stake`

Avoid stronger labels unless the service itself opens the gate.

When the service gate is closed but analyst evidence supports a small action, explicitly frame it as `research-only small stake`, state the buyable line and minimum acceptable odds, and explain that it is outside formal production recommendation.

## Decision Rules

### Say `skip` when

- odds source quality is stale or degraded and no trustworthy fallback exists
- shortlist returns only hard blockers
- the actual target market or line is not buyable
- edge is absent or explicitly rejected as `no_positive_edge`
- the user asks for a formal recommendation while production / release gate is closed

### Say `observe` when

- the match is analyzable but current price does not justify action
- shortlist shows soft blockers such as `edge_below_threshold`
- the system is in paper-validation / watchlist mode
- your football judgement likes the direction, but the real line is too tight or the price has already moved

### Say `wait for live confirmation` when

- the main issue is timing or current price level
- you need lineup-independent market confirmation from later odds movement
- current odds are close but not good enough
- you need to confirm that an alternate line exists at a usable price

### Say `research-only small stake` only when

- the route output is structurally clean
- the source closure is at least usable
- there are no hard blockers
- the framing remains explicitly non-production and non-formal
- a real buyable market exists and the minimum acceptable price is stated

## Hard Constraints

- Do not overrule `production_ready=false`.
- Do not turn fallback-quality data into high-confidence language.
- Do not treat raw lineup availability as a decisive edge by itself.
- Do not invent EV or quote unavailable lines. If deriving your own view, separate it from MCP-calculated EV and show the assumptions.
- Do not let league/fixture labels alone block analysis; use them as liquidity and reliability risk factors.
- Prefer explaining "why not" over forcing an actionable pick, but if a real buyable edge appears outside shortlist, analyze it on its merits.

## Good Prompts This Skill Should Handle

- `看一下未来 6 小时哪些比赛值得研究`
- `为什么现在没有 open 预测`
- `分析这场盘口：泰国U19 vs 柬埔寨U19`
- `不限联赛和玩法，自己筛一下今晚能买的盘口`
- `复盘 recommendation:2978`
- `当前赔率源还能不能信`
- `今天为什么 shortlist 没出结果`

## Minimal Command Pattern

When calling routes from the shell, prefer:

```bash
curl -s 'http://127.0.0.1:8910/api/ai/review/summary'
curl -s 'http://127.0.0.1:8910/api/ai/matches/window?window_hours=6&limit=5'
curl -s 'http://127.0.0.1:8910/api/ai/shortlist?window_minutes=360&top_n=3&limit=12&mode=balanced&target_market=asian_handicap'
curl -s 'http://127.0.0.1:8910/api/ai/shortlist?window_minutes=360&top_n=3&limit=12&mode=balanced&target_market=over_under'
curl -s 'http://127.0.0.1:8910/api/ai/shortlist?window_minutes=360&top_n=3&limit=12&mode=balanced&target_market=1x2'
curl -s 'http://127.0.0.1:8910/api/ai/match/odds?query=泰国U19%20vs%20柬埔寨U19&window_hours=12'
```

Prefer summarizing key fields instead of dumping full JSON unless the user asked for raw output.

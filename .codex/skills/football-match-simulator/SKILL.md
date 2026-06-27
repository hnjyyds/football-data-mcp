---
name: football-match-simulator
description: Use when Codex needs football or soccer match simulation, Poisson/Dixon-Coles style scoreline modelling, Monte Carlo sanity checks, 1X2 probability estimates, handicap/total-goals probability checks, score-cluster analysis, model-vs-fundamentals comparison, or GitHub football prediction project selection. Trigger for requests like "模拟这场比赛", "跑一下比分分布", "用模型校验", "Poisson/蒙特卡洛预测", "找/用 GitHub 足球预测模型", "概率和竞彩结论冲突吗", or "帮我优化预测 skill". This is a quantitative sanity layer, not a betting instruction engine.
---

# Football Match Simulator

Use this skill as a quantitative challenge layer for football analysis. It converts explicit football assumptions into scoreline, 1X2, handicap, and total-goals distributions. It must not replace current web verification, team news, tactical analysis, or Jingcai odds-source audits.

## Core Rule

Start from stated assumptions, not invented certainty.

- Use current web sources or the caller's analysis to set expected goals, team-strength adjustments, lineup/rotation modifiers, tactical tempo, and motivation.
- If inputs are weak, output a sensitivity range rather than one precise number.
- Treat model output as `模型校验`, never as `真实概率` or a buying instruction.
- Do not output stake sizing, Kelly fractions, bankroll advice, or "place bet" language.
- Do not present GitHub stars, README claims, or model labels as proof of prediction accuracy.

## When To Read References

- Read [github-model-selection.md](references/github-model-selection.md) when choosing, installing, evaluating, or comparing GitHub football prediction projects.
- Read the script help before using the bundled simulator: `python3 scripts/poisson_simulator.py --help`.

## Workflow

1. Confirm the task type:
   - `single-match simulation`: use explicit lambda values or derive a conservative range from current data.
   - `analysis sanity check`: compare the model's score clusters with the football/Jingcai conclusion.
   - `GitHub model selection`: evaluate candidate repos by evidence quality, maintenance, testability, and calibration, not only stars.
2. Build an input ledger:
   - team names, neutral/home orientation, kickoff, source date
   - expected goals for each side and how they were derived
   - adjustments for lineup, motivation, tempo, travel, weather, red-card risk, or tactical mismatch
   - uncertainty range, such as low/base/high lambda scenarios
3. Run the simulator for each scenario:
   - Use `scripts/poisson_simulator.py` when explicit expected goals are available.
   - Use at least base and one stress scenario when the final view depends on exact margins or total goals.
4. Interpret the distribution:
   - Identify top scorelines, 1X2, goal bands, both-teams-score, and handicap outcomes.
   - For Jingcai HHAD, map the official home-team let number to score-difference bands.
   - Name the single score that most naturally kills the proposed stance.
5. Compare against fundamentals:
   - `模型支持`: model and football script point to the same score cluster.
   - `模型提醒`: model exposes a draw, exact-margin, or total-goals risk that the football read underweighted.
   - `模型失效风险`: inputs are stale, lineup-sensitive, tournament motivation-heavy, or the team data sample is too thin.
6. Output a bounded judgement:
   - Give the model table and a short explanation of what changed or did not change in the human analysis.
   - If used with `ai-odds-analyst`, feed the result back as `概率/模型校验`; do not make it the final Jingcai stance by itself.

## Input Guidance

Prefer expected-goals inputs from stable, current evidence:

- recent xG and shot quality, adjusted for opponent strength
- market-derived goal expectation only as a supporting estimate
- team attack/defense strength from a maintained model such as Club Elo plus scoring rates
- lineup absences that affect chance creation, finishing, ball progression, center-back speed, goalkeeper quality, or set-piece defense
- tactical tempo: low block, high press, must-win chase state, draw-acceptable caution

When data is sparse, use scenario bands:

- favorite narrow-control: favorite lambda 1.25-1.65, underdog 0.55-0.95
- open must-win game: raise both lambdas and tail risk
- draw-acceptable low tempo: lower both lambdas and upgrade 0-0/1-1
- underdog set-piece outlet: keep underdog lambda above zero even when side quality is low

These are starting ranges, not defaults. Explain why a range fits the match before using it.

## Script Usage

Run from the skill directory or pass the full script path:

```bash
python3 scripts/poisson_simulator.py \
  --home "Uruguay" \
  --away "Spain" \
  --home-xg 0.95 \
  --away-xg 1.45 \
  --handicap-home 1 \
  --simulations 50000 \
  --seed 26
```

Important options:

- `--home-xg`, `--away-xg`: expected goals/lambdas.
- `--handicap-home`: Jingcai-style home-team handicap; `1` means home +1, `-1` means home -1.
- `--max-goals`: exact Poisson grid cutoff; default is usually enough.
- `--simulations`: optional Monte Carlo sample for a second check and tail intuition.
- `--json`: machine-readable output for downstream analysis.

## Output Requirements

For each serious simulation, include:

- `输入假设`: lambdas, source/derivation, and uncertainty.
- `模型分布`: 1X2, top scores, total-goals bands, BTTS, and HHAD if relevant.
- `比分簇`: two to four scores that drive the market conclusion.
- `最怕比分`: the most natural score that kills the proposed stance.
- `敏感性`: how a 0.15-0.30 xG shift changes the stance when the edge is narrow.
- `裁断`: support, warning, or no-use, explicitly separated from betting advice.

## Validation Bar

Before trusting a repo or model:

- Check whether predictions are generated before matches, not fitted after results.
- Prefer Brier score, log loss, calibration curves, or long-run ROI/closing-line comparisons over hit rate.
- Verify data freshness, source legality, and whether international/tournament football is covered.
- Penalize projects with impressive README claims but no reproducible backtest.
- Penalize single-season or small-sample "accuracy" claims.

## Coordination With AI Odds Analyst

When the user asks for Jingcai analysis plus simulation, use `ai-odds-analyst` for source-led football and odds judgement, then use this skill only for `概率/模型校验`.

Do not let the simulator overrule:

- official or public Jingcai odds-source uncertainty
- late lineup/news
- tournament group incentives
- tactical matchups that the lambda inputs cannot represent

If the model conflicts with the football lane, downgrade confidence and identify the missing variable rather than averaging both views into fake precision.

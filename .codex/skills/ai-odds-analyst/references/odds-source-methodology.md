# Odds Source Methodology

Use this reference whenever current Jingcai odds, odds movement, heat, inducement, reverse-buy, draw protection, or source reliability matters.

## Source Tiers

Classify every odds source before using it:

1. Tier A: Sporttery official web/API or a user-provided screenshot from the official lottery app. Use this as the current-price authority when available.
2. Tier B: reputable public Jingcai pages that mirror lottery odds, such as 500.com, OKooo/澳客, 懂球帝, 雷速, or other pages with match number, pools, and timestamp.
3. Tier C: overseas bookmaker odds, exchange odds, Asian handicap, totals, and prediction-market prices. Use these only as supporting market signals, not as current Jingcai price authority.
4. Tier D: public sports-data or modelling tools such as ESPN-style match centres, xG/stat aggregators, Elo/Poisson models, or agent data skills. Use these for football or probability sanity checks only after match identity is reconciled.

## Identity Reconciliation

Before comparing odds, statistics, or model outputs, build a canonical event ledger:

- Jingcai match number and sales date when visible
- competition, round/group, kickoff time, venue, and neutral-site flag
- home/away order in the Jingcai market
- Chinese names, source-language names, common aliases, and any external event ids
- source-specific team order, kickoff time, and market orientation

Do not merge sources only because team names look similar. If a source flips home/away order, uses a different kickoff time, lists a reserve/youth team, or hides neutral-site status, state the conflict and downgrade until resolved.

## Minimum Evidence

For current Jingcai odds, collect and report:

- source name, URL, access time, and whether it is official, public mirror, or user screenshot
- match number, kickoff time, selling pools, HAD odds, HHAD line and odds, and total-goals/score/half-full odds when used
- opening odds and current odds separately; do not call movement unless both are visible
- source agreement: same match, same pool, same let-ball number, and close enough odds to trust the comparison
- whether external statistics, xG, injury feeds, or prediction-market prices point to the same canonical event

## Confidence Rules

- If Tier A is available, use it for current odds and cite it.
- If Tier A is blocked, use at least two Tier B sources when making heat, inducement, reverse-buy, or precise movement claims.
- If only one Tier B source is available, label the read `single-source public odds`; allow direction discussion, but do not claim precise heat/诱盘 or make a strong parlay recommendation from odds alone.
- If Tier B sources disagree on the let-ball number, selling pools, or material odds movement, state the conflict and downgrade the recommendation to `observe` unless the user provides official app odds.
- If only Tier C sources are available, say the Jingcai current price is unverified and translate cautiously from market structure only.
- If Tier C or D sources disagree with Tier A/B, do not override Jingcai. Treat the disagreement as a warning to inspect lineup, motivation, tactical matchup, or market identity.
- Do not treat "official page returned WAF/protection page" as solved by silently using 500.com. State the official-source failure and the resulting confidence downgrade.

## Odds Math Checks

Use odds math to understand burden and disagreement, not to generate betting instructions.

- Convert decimal odds to implied probability as `1 / odds`.
- When comparing 1X2 style markets, normalize the three implied probabilities by their sum to remove overround and label the result `no-vig market estimate`.
- Compare no-vig estimates across Jingcai HAD, overseas 1X2, exchange/prediction markets, and model outputs only when event identity and timestamps are aligned.
- For HHAD and total-goals, use normalized probabilities to see which margin or goal band is being emphasized; do not claim it as true team strength.
- If a public model or market estimate differs by a wide margin from the football lane, record the conflict as `模型/市场反证` and find the football reason before selecting.
- Do not output Kelly criterion, bankroll fraction, stake size, unit size, or an instruction to buy. Keep the result as source confidence, price burden, compensation, and Jingcai expression.

## Output Requirement

Include a compact source ledger before odds conclusions:

| Source | Tier | What it verified | Time | Reliability | Identity notes |
| --- | --- | --- | --- | --- | --- |

Then explain:

- which source controls current Jingcai price
- which source controls opening-to-current movement
- what cannot be verified
- how source quality changes the action label
- whether external odds/stat/model sources agree with the canonical event and Jingcai market orientation

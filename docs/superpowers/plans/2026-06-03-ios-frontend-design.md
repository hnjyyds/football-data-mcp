# iOS Frontend Design: Match Win Probability Explainer

**Date:** 2026-06-03

**Goal:** Design the first iOS frontend for a personal football intelligence app. The app starts from one user action: choose a match, then show how the win probabilities are calculated through a transparent, visual, evidence-based flow.

**Distribution assumption:** Personal use only. No App Store launch requirement.

**Plugin note:** The requested `build-ios-apps` plugin did not expose an installable or callable tool in this workspace. This document is written as a SwiftUI-ready product/frontend specification.

## Product Principle

The app must not feel like a betting tips app. It should feel like a match probability lab:

```text
Choose match -> inspect data -> calculate probabilities -> explain changes -> show confidence
```

Every number should answer four questions:

- Where did this data come from?
- How fresh is it?
- Did it affect the probability?
- Has this kind of probability been calibrated historically?

## Primary User Flow

```text
Open app
  -> Today
  -> Choose a match
  -> Probability Flow
      -> Data Sources
      -> Market Baseline
      -> Expected Goals
      -> Score Matrix
      -> Signal Adjustments
      -> Calibration
      -> Final Probability
```

The main screen is not a feed of tips. It is a list of matches with data-quality status and a clear "Analyze" entrypoint.

## Navigation

Use a bottom `TabView` with four stable tabs, following Apple's tab-bar guidance that tabs are for top-level navigation, not actions.

1. **Today**
   - Upcoming watched matches.
   - Quick probability cards.
   - Data-source health summary.

2. **Matches**
   - Full fixture browser.
   - League/time filters.
   - Saved/watched matches.

3. **News**
   - Team/league news stream.
   - AI-extracted signals preview.
   - Source and timestamp visible.

4. **Lab**
   - Model health.
   - Calibration summaries.
   - Explanation library.

References:

- Apple SwiftUI: https://developer.apple.com/documentation/swiftui
- Apple Human Interface Guidelines, Tab bars: https://developer.apple.com/design/Human-Interface-Guidelines/tab-bars
- Apple Human Interface Guidelines, Charts: https://developer.apple.com/design/human-interface-guidelines/charts

## Visual Direction

Tone: analytical, calm, dense enough for repeated use.

Avoid:

- Marketing hero screens.
- Giant decorative cards.
- Win/lose hype.
- One-color blue/purple dashboards.
- "Must win", "sure pick", or profit language.

Use:

- Native iOS materials sparingly.
- Compact probability bars.
- Scoreline heatmaps.
- Source confidence badges.
- Timeline/waterfall charts.
- SF Symbols for source, clock, alert, chart, team, and model states.

Color roles:

```text
Background: system background
Primary text: label
Secondary text: secondaryLabel
Positive probability: systemGreen
Negative/risk: systemRed
Neutral/market: systemBlue
Warning/stale: systemOrange
Model/calibration: systemTeal
Unavailable/ignored: systemGray
```

The color should encode role, not team preference. Team colors can appear only in crests/badges and small accents.

## Screen 1: Today

Purpose: show what matters now without forcing the user into every diagnostic detail.

Layout:

```text
Navigation title: Today

Data Health Strip
  Odds fresh | xG partial | News active | Model not validated for automation

Section: Next Matches
  MatchProbabilityRow
  MatchProbabilityRow
  MatchProbabilityRow

Section: Watched Signals
  Injury update
  Odds moved
  Lineup expected
```

`MatchProbabilityRow` content:

- Kickoff time.
- League.
- Home vs away.
- Three compact bars: Home / Draw / Away.
- Data confidence: High / Medium / Low.
- Status: Ready / Partial / Stale.

Tap opens `MatchDetailView`.

## Screen 2: Matches

Purpose: choose a match.

Controls:

- Segmented control: `Today`, `24h`, `7d`, `Watched`.
- League filter menu.
- Search field for teams, only inside Matches.

Rows must prioritize scan speed:

```text
20:45  Premier League
Arsenal vs Chelsea
Ready · odds 4m ago · xG available
Home 45% | Draw 27% | Away 28%
```

States:

- `ready`: enough data for full flow.
- `baselineOnly`: only market/historical baseline.
- `partial`: some enhancement sources missing.
- `stale`: source freshness warning.
- `blocked`: no valid match/odds baseline.

The app should rarely show `blocked`. If odds are missing, backend should fall back to historical/team baseline and mark confidence low.

## Screen 3: Match Detail

This is the core screen.

Top area:

```text
Home Team        Away Team
kickoff, league, venue

Final Probability
Home 45.6% | Draw 27.1% | Away 27.3%
Confidence: Medium
```

Below that, use a vertical calculation flow. Each step is a tappable disclosure row that expands into details.

### Step 1: Data Sources

Component: `SourceCoveragePanel`

Rows:

```text
Fixtures      openfootball / provider      fresh     used
Odds          Football-Data / OddsPortal    6m ago    used
xG            Understat / FBref             partial   used lightly
Lineups       provider                      stale     ignored
Injuries      Transfermarkt/RSS             conflict  ignored
News          RSSHub/articles               14m ago   extracted
```

Each row has:

- Source name.
- Freshness.
- Confidence.
- `used_in_probability`.
- Tap to inspect raw evidence summary.

### Step 2: Market Baseline

Component: `MarketBaselineCard`

Shows:

- Raw odds.
- Raw implied probabilities.
- Overround.
- De-vig probabilities.

Example:

```text
Raw odds
Home 2.10 | Draw 3.40 | Away 3.60

After bookmaker margin removal
Home 45.0% | Draw 27.8% | Away 27.2%
```

Visualization:

- Three horizontal bars.
- Small margin chip: `Overround 4.8%`.

### Step 3: Expected Goals

Component: `ExpectedGoalsPanel`

Shows:

```text
Home xG: 1.52
Away xG: 1.08
Total: 2.60
```

Visualization:

- Paired bars for home and away.
- Optional mini distribution for goals 0-5.

Disclosure explains:

- Market targets used.
- Form/xG signals used.
- Any lineup or residual adjustment.

### Step 4: Score Matrix

Component: `ScoreMatrixHeatmap`

Purpose: prove where win probability comes from.

Grid:

```text
      Away 0  1  2  3  4+
Home
0        7   8   4   1
1       11  12   6   2
2        8   9   5   2
3        4   4   2   1
4+       2   2   1   1
```

Interactions:

- Tap a cell to show score probability.
- Toggle: `All`, `Home win`, `Draw`, `Away win`.
- Home-win cells, draw diagonal, and away-win cells use subtle different roles.

Summary:

```text
Home win = all cells below the draw diagonal
Draw = diagonal cells
Away win = all cells above the draw diagonal
```

### Step 5: Signal Adjustments

Component: `AdjustmentWaterfall`

Shows how baseline probability changed.

Example:

```text
Market baseline         45.0%
xG advantage            +2.1%
Rest advantage          +0.8%
Home CB absence         -1.4%
Line movement           -0.7%
Calibration             -0.2%
Final                   45.6%
```

Rules:

- Only validated/allowed signals can move probability.
- Unvalidated signals appear under `Observed, not used`.
- Every adjustment row links to evidence.

### Step 6: Calibration

Component: `CalibrationPanel`

Shows:

```text
Similar historical predictions
Model said: 45%-50%
Actual home-win rate: 46.8%
Sample: 312
Calibration error: 1.4 pts
```

Visualization:

- Reliability mini chart.
- Sample-size badge.
- Warning if sample is too small.

### Step 7: Final Decision Card

Component: `FinalProbabilityCard`

It must avoid bet-language.

Content:

```text
Home win       45.6%
Draw           27.1%
Away win       27.3%

Confidence     Medium
Data quality   Good
Model status   Research / paper validation
```

Risk notes:

- `Lineup not confirmed`
- `Odds moved against home side`
- `xG source covers only recent matches`
- `League calibration sample small`

Primary actions:

- Save match.
- Set kickoff reminder.
- Refresh analysis.
- Export/share summary.

No primary action should imply placing a bet.

## Screen 4: News

Purpose: make non-structured information useful without polluting the model.

Layout:

```text
Team/League filter

Article cards:
  source
  title
  timestamp
  linked team/player/match
  extracted signal
  used / observed / ignored
```

Signal card example:

```text
Signal: Rotation risk
Team: Home
Confidence: 0.64
Used in model: No
Reason: unconfirmed press-conference language
```

The user can tap through to the article, but the App should show only the summary/evidence needed for the selected match.

## Screen 5: Lab

Purpose: make the math understandable and auditable.

Sections:

- Model health.
- Source coverage.
- Calibration by league.
- Explanation library.
- Recent backend runs.

Cards:

```text
Poisson score model
Dixon-Coles low-score correction
De-vig market probability
Expected goals
Brier score
Log loss
Closing line value
```

Lab should not be required for daily use. It is where the user goes when they want to understand or debug.

## SwiftUI Component Map

```text
FootballProbabilityApp
  AppRootView
    MainTabView
      TodayView
        DataHealthStrip
        MatchProbabilityRow
        WatchedSignalRow
      MatchesView
        MatchFilterBar
        MatchList
        MatchProbabilityRow
      MatchDetailView
        MatchHeader
        FinalProbabilityCard
        CalculationFlow
          SourceCoveragePanel
          MarketBaselineCard
          ExpectedGoalsPanel
          ScoreMatrixHeatmap
          AdjustmentWaterfall
          CalibrationPanel
      NewsView
        NewsFilterBar
        ArticleSignalCard
      LabView
        ModelHealthCard
        CalibrationSummaryCard
        ExplanationCard
```

## Data Models For Swift

```swift
struct MatchSummary: Identifiable, Decodable {
    let id: String
    let league: String
    let kickoffUTC: Date
    let homeTeam: TeamSummary
    let awayTeam: TeamSummary
    let probabilities: WinProbabilities?
    let readiness: AnalysisReadiness
    let sourceSummary: SourceSummary
}

struct WinProbabilities: Decodable {
    let homeWin: Double
    let draw: Double
    let awayWin: Double
    let confidence: ConfidenceLevel
}

struct ProbabilityExplanation: Decodable {
    let match: MatchSummary
    let final: WinProbabilities
    let marketBaseline: MarketBaseline
    let expectedGoals: ExpectedGoals
    let scoreMatrix: [ScoreCell]
    let adjustments: [ProbabilityAdjustment]
    let calibration: CalibrationEvidence
    let sources: [SourceEvidence]
    let risks: [RiskFlag]
}
```

## Mobile API Required By The Frontend

The frontend should not consume the large dashboard payload directly. It needs a compact mobile API.

```text
GET /api/mobile/home
GET /api/mobile/matches?window_hours=24&league=E0
GET /api/mobile/matches/{match_id}
GET /api/mobile/matches/{match_id}/probability-flow
GET /api/mobile/news?match_id=...
GET /api/mobile/lab/model-health
POST /api/mobile/matches/{match_id}/refresh
```

`/probability-flow` should return:

```json
{
  "match": {},
  "final_probabilities": {},
  "data_sources": [],
  "market_baseline": {},
  "expected_goals": {},
  "score_matrix": [],
  "adjustments": [],
  "calibration": {},
  "risk_flags": [],
  "explanation_version": "probability-flow-v1"
}
```

## Offline And Refresh States

The app should support:

- Cached last analysis.
- Pull to refresh.
- Manual refresh button on match detail.
- Clear stale indicators.
- No blank screen when backend is offline.

State labels:

```text
Fresh
Stale
Partial
Baseline only
Offline cached
Error
```

## Accessibility

- Every probability bar must expose an accessibility label, for example: `Home win probability, 45.6 percent`.
- Heatmap cells must be readable by VoiceOver: `Score 1-0, probability 10.8 percent`.
- Do not rely only on color for win/draw/away states.
- Dynamic Type should be supported; dense tables can switch to stacked rows.

## First Build Scope

Build these first:

1. `TodayView`
2. `MatchesView`
3. `MatchDetailView`
4. `ScoreMatrixHeatmap`
5. `AdjustmentWaterfall`
6. `SourceCoveragePanel`

Defer:

- Widgets.
- Live Activities.
- Push notifications.
- Full article reader.
- Advanced Lab charts.
- iPad split view.

## Design Acceptance Criteria

- The user can select one match and understand how Home/Draw/Away probabilities were produced.
- The app never hides source freshness or data confidence.
- Unavailable/unverified signals are shown as observed or ignored, not silently treated as neutral truth.
- The final probability can be traced back to market baseline, xG, score matrix, adjustments, and calibration.
- The interface does not imply guaranteed prediction or real-money action.

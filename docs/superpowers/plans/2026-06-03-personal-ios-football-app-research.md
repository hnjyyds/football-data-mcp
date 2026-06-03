# Personal iOS Football Intelligence App Research

**Date:** 2026-06-03

**User constraint:** Personal use only. No App Store launch required.

## Short Answer

Yes, this is practical. The fastest and most reliable path is not to rebuild the prediction engine inside the phone. Build a native SwiftUI iPhone app as a personal cockpit, and keep the existing Python backend as the data/model service.

This repository already has a strong backend foundation: fixture and odds ingestion, market-anchored Dixon-Coles/Poisson modelling, Asian handicap and totals probabilities, paper-learning records, holdout validation, calibration status, dashboard APIs, and a React dashboard. The iOS app should consume a smaller mobile API facade over those capabilities.

## Personal Distribution

Because the app is not going to the App Store, the practical install choices are:

- **Xcode direct install to your iPhone:** best for development and personal use. Apple documents running apps on devices from Xcode and using a personal Apple account/team for signing.
- **Registered-device/ad hoc distribution:** useful if you later want the app on a few known devices. Apple documents distributing to registered devices through developer account provisioning.
- **TestFlight private beta:** useful if you have a paid Apple Developer Program account and want easier updates, though it is probably overkill for one device.
- **PWA/Web shortcut fallback:** fastest if native notifications/offline cache are not important, but it will not feel as polished as a real iOS app.

Sources:

- Apple: running an app in Simulator or on a device: https://developer.apple.com/documentation/xcode/running-your-app-in-simulator-or-on-a-device
- Apple: signing and personal team workflow: https://help.apple.com/xcode/mac/current/en.lproj/dev60b6fbbc7.html
- Apple: distributing to registered devices: https://developer.apple.com/documentation/xcode/distributing-your-app-to-registered-devices

## Recommended Product Shape

Use five tabs:

1. **Today**
   - Upcoming matches
   - Current model picks
   - Data-source health
   - Important news affecting watched teams/leagues

2. **Matches**
   - Fixture list by league/time
   - Filters for watched leagues, kickoff window, confidence, market type
   - No real-money placement controls

3. **Match Detail**
   - 1X2, Asian handicap, totals, top scorelines
   - Odds movement and source freshness
   - Model-vs-market probability comparison
   - Explanation cards: expected goals, Poisson/Dixon-Coles assumptions, calibration bucket, backtest caveats

4. **News**
   - RSS/API aggregated football news
   - Club/league/source subscriptions
   - Saved articles
   - Optional article-to-match linking

5. **Model Lab**
   - Plain-language math explanations
   - Backtest summaries
   - Calibration/reliability diagrams
   - Glossary: implied probability, overround, Brier score, log loss, expected value, closing line value

## Architecture

```text
iPhone SwiftUI app
  -> Mobile API facade
      -> Existing football_data_mcp backend
          -> fixtures/results/odds/news sources
          -> prediction engine
          -> learning/calibration store
```

For personal network access:

- Same Wi-Fi/LAN during development.
- Tailscale or another private VPN for daily use outside home.
- Cloudflare Tunnel only if you want a public HTTPS endpoint with access controls.

The app should store a local cache using SwiftData or SQLite so the phone remains useful when the backend is temporarily unreachable.

## Current Repository Fit

Existing backend capabilities to reuse:

- `analyze_single_match`: single-match model output.
- `shortlist_value_matches`: ranked upcoming picks by confidence/value/balanced mode.
- `run_historical_backtest`, `run_holdout_validation`, `run_top_k_confidence_backtest`: model validation.
- `/api/dashboard`, `/api/dashboard/summary`, `/api/dashboard/match/{ledger_id}`: current read APIs.
- Learning store and strategy state: paper records, settlement evidence, calibration status.

Recommended mobile-specific API additions:

- `GET /api/mobile/home`
- `GET /api/mobile/matches?window_hours=...`
- `GET /api/mobile/matches/{id}`
- `GET /api/mobile/matches/{id}/explanation`
- `GET /api/mobile/news`
- `GET /api/mobile/model/status`
- `POST /api/mobile/preferences`

The mobile API should be intentionally smaller and more stable than the internal dashboard payload. The iOS app should not need to understand every backend diagnostic field.

## Data Sources

Start with the sources already represented in this repo, then add paid or richer feeds only when needed.

**Fixtures/results/odds**

- Football-Data.co.uk: strong for historical CSV match results and odds; already the repo's primary numeric source.
- football-data.org: useful API for fixtures, matches, standings, teams, and competitions.
- openfootball/football.json: public-domain JSON fixtures/results, good for fallback or demos.
- The Odds API: commercial odds API with historical odds endpoint.
- API-Football / SportMonks: broader fixture/stat/odds/prediction APIs if paid coverage is acceptable.

Sources:

- Football-Data.co.uk data: https://www.football-data.co.uk/data
- football-data.org API docs: https://www.football-data.org/documentation/api
- openfootball football.json: https://github.com/openfootball/football.json
- The Odds API docs: https://api.theoddsapi.com/docs
- API-Football docs: https://www.api-football.com/documentation
- SportMonks predictions docs: https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/predictions

**Advanced analytics / future xG layer**

- StatsBomb Open Data / statsbombpy: excellent open event data for learning, demos, and historical analytics, but not complete live coverage.
- socceraction: useful for SPADL/VAEP style possession value modelling.
- kloppy: useful if later ingesting event/tracking data from multiple providers.

Sources:

- statsbombpy: https://github.com/statsbomb/statsbombpy
- socceraction docs: https://socceraction.readthedocs.io/en/latest/documentation/faq.html
- kloppy: https://github.com/PySport/kloppy

**News**

- RSS first: official club sites, league sites, BBC/Sky/ESPN-style source feeds where available.
- RSSHub for feeds where sites do not provide clean RSS.
- NewsAPI, GNews, or SerpApi Google News as optional paid API layers.

Sources:

- RSSHub docs: https://docs.rsshub.app/
- NewsAPI docs: https://newsapi.org/docs/endpoints
- GNews docs: https://docs.gnews.io/
- SerpApi Google News API: https://serpapi.com/google-news-api

## Open-Source Projects Worth Studying

- NetNewsWire: native open-source RSS reader for iOS/macOS. Best reference for feed subscriptions, article reading, offline state, and iOS information architecture.
- FeedFlow: cross-platform RSS reader with iOS support; useful as a simpler feed-reader comparison.
- penaltyblog: Python football modelling library with Poisson, Dixon-Coles, bivariate Poisson, and market probability utilities. Good benchmark/reference for the backend model.
- openfootball/football.json: open public football fixtures/results datasets.
- statsbombpy, socceraction, kloppy: event-data analytics ecosystem.

Sources:

- NetNewsWire: https://github.com/Ranchero-Software/NetNewsWire
- FeedFlow: https://github.com/prof18/feed-flow
- penaltyblog docs: https://penaltyblog.readthedocs.io/en/latest/index.html
- penaltyblog Dixon-Coles: https://docs.pena.lt/y/models/dixon_coles.html

## Prediction And Math Layer

Keep the app honest and explanatory. It should show probabilities, not promises.

Core model display:

- Expected goals: home and away scoring intensity.
- Scoreline grid: Poisson/Dixon-Coles adjusted probability matrix.
- 1X2: home/draw/away probabilities.
- Asian handicap: settlement-aware probability by line.
- Over/under: probability by goals line.
- Market comparison: model probability vs normalized implied market probability.
- Confidence: calibrated probability bucket and sample count.
- Risk flags: stale odds, low sample size, source disagreement, overround, model not validated for this league.

Math explanation cards:

- **Poisson:** models goal count as a discrete random variable from expected goals.
- **Dixon-Coles:** adjusts low-score dependencies such as 0-0, 1-0, 0-1, 1-1.
- **Implied probability:** converts decimal odds into market probability before removing bookmaker margin.
- **Overround:** bookmaker margin embedded in raw odds.
- **Calibration:** checks whether historical events predicted at about 60% actually happened about 60% of the time.
- **Brier/log loss:** scoring rules for probability quality.

## MVP Plan

### Phase 1: Mobile API facade

- Add stable mobile endpoints over existing dashboard/model data.
- Add a small preference store for watched leagues/teams.
- Return compact JSON designed for Swift decoding.

### Phase 2: SwiftUI app shell

- Create a new `ios/` Xcode project.
- Build Today, Matches, Match Detail, News, Model Lab tabs.
- Use `URLSession` for API calls and SwiftData for cache.

### Phase 3: Match detail and model explanations

- Render scoreline matrix, probability bars, odds movement, and risk flags.
- Add explanation cards tied to actual model output.

### Phase 4: News ingestion

- Add backend RSS/news aggregator.
- Start with configured RSS feeds and RSSHub.
- Later add NewsAPI/GNews/SerpApi if needed.

### Phase 5: Alerts

- Local notifications for kickoff reminders and model-change alerts.
- Remote push only if later using a paid Apple Developer Program account and APNs.

## Main Risks

- **Data freshness:** odds and fixture feeds can be stale or blocked.
- **Provider terms:** scraping and WAF-protected sites need careful handling even for personal use.
- **False precision:** probability UIs can feel more certain than the model really is.
- **iOS background limits:** background refresh is not guaranteed; push requires more setup.
- **Model validation:** current repo README says the holdout gate is still `not_ready`; the app should display that honestly.

## Recommendation

Build it as:

- Native iOS app: SwiftUI.
- Backend: this repository, self-hosted.
- News: backend RSS/RSSHub aggregator first.
- Prediction: existing Dixon-Coles/Poisson engine first, with penaltyblog as a benchmark/reference.
- Install: Xcode direct install to your iPhone during MVP; consider paid developer account only if updates or push notifications become annoying.

This keeps the first version small enough to actually finish, while leaving room for richer data, xG, news-to-match linking, and better calibration later.

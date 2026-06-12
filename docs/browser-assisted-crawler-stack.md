# Browser-Assisted Crawler Stack

This repository now treats browser-assisted scraping as an explicit runtime layer instead of a one-off script.

## Current Stack

1. `Leisu` primary gated source
   - Browser-assisted via `scripts/leisu_browser_proxy.py`
   - Playwright persistent-context or CDP-attached real Chrome
   - Exposes:
     - `GET /health`
     - `GET /leisu/session`

2. `OddsPortal` fallback source
   - HTTP/HTML + encrypted payload decoding
   - Runs through the existing odds-source queue and sync state

3. `DataSourceService`
   - Reads fresh snapshot counts
   - Reads recent sync failures
   - Reads browser-session state from:
     - `LEISU_BROWSER_PROXY_STATUS_URL`, or
     - derived `LEISU_ODDS_PROXY_URL -> /leisu/session`, or
     - local session-status file
   - Exposes runtime support / bootstrap guidance for a future `Crawlee` browser runtime

## Why This Exists

The core production risk is not raw parsing logic. It is the gap between:

- browser session is healthy
- browser session needs manual verification
- scraper is running but snapshots are stale
- fallback source is carrying production availability

The browser-session layer closes that gap by making the operator state machine visible to the backend.

## Operational States

Leisu browser-session states:

- `starting`
- `ready`
- `auth_required`
- `error`
- `stopped`

These are surfaced inside `DataSourceService.odds_source_status()` as:

- `browser_session`
- `browser_session_status`
- `operational_status`
- `next_action`

## Recommended Next Step

If we later adopt a larger framework such as `Crawlee`, this browser-session contract should remain the integration point:

- browser runtime handles session / proxy / auth state
- repo services consume normalized session health + snapshot freshness
- model and dashboard stay decoupled from the crawler implementation details

This repository now includes a first bootstrap entrypoint for that path:

- `uv run --extra crawler-runtime python -m scripts.leisu_crawlee_session --match-id 4512919`
- `POST /api/sources/odds/leisu/session/refresh`

Use it to create or refresh a persistent Leisu browser profile under `Crawlee + Playwright`. The service layer does not depend on Crawlee directly; it only consumes the session-health contract.

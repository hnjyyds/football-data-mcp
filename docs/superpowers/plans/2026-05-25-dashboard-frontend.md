# Dashboard Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a containerized, read-only Football MCP Strategy Dashboard that automatically displays current recommendations, candidate filtering, learning state, settlement evidence, and system health without any search inputs.

**Architecture:** Add a lightweight `/api/dashboard` custom route to the existing FastMCP server. Create a new `frontend/` Vite React app that polls that endpoint and renders a dense operational dashboard. Docker Compose runs both the MCP backend and frontend containers.

**Tech Stack:** Python/FastMCP custom route, SQLite learning store, React 19, TypeScript, Vite, Vitest, CSS modules via plain CSS, Docker Compose.

---

### Task 1: Dashboard Snapshot API

**Files:**
- Modify: `football_data_mcp/learning_store.py`
- Modify: `football_data_mcp/sources.py`
- Modify: `football_data_mcp/server.py`
- Test: `tests/test_learning_store.py`
- Test: `tests/test_learning_cycle.py`

- [ ] Add tests for a dashboard snapshot that separates Asian picks, learning observations, recent settlements, strategy state, and record-count KPIs.
- [ ] Implement learning-store helpers that decode recent records into dashboard-friendly rows.
- [ ] Implement `sources.dashboard_snapshot()` as a read-only aggregation with no betting side effects.
- [ ] Add `@mcp.custom_route("/api/dashboard", ["GET", "OPTIONS"])` returning JSON with permissive local CORS headers.
- [ ] Run targeted tests and full Python tests.

### Task 2: Frontend Data Model

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/dashboardModel.ts`
- Create: `frontend/src/dashboardModel.test.ts`

- [ ] Write Vitest tests for KPI mapping, strategy-status labeling, and row formatting.
- [ ] Implement TypeScript types matching `/api/dashboard`.
- [ ] Implement pure formatting helpers for percentages, odds, status labels, and grouped candidate rejection counts.
- [ ] Run frontend tests.

### Task 3: Read-Only Dashboard UI

**Files:**
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles.css`

- [ ] Render a dashboard without search boxes or free-form inputs.
- [ ] Add panels for system KPIs, Asian handicap picks, candidate filter reasons, strategy state, recent learning events, and recent settlements.
- [ ] Poll `/api/dashboard` every 30 seconds and show stale/error states without clearing the last good snapshot.
- [ ] Keep the visual style dense, professional, restrained, and consistent with the approved mockups.
- [ ] Run frontend tests and production build.

### Task 4: Containerization

**Files:**
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`
- Modify: `docker-compose.yml`
- Modify: `README.md`

- [ ] Add frontend Docker build using Node for build and Nginx for serving static assets.
- [ ] Proxy `/api/*` from the frontend container to `football-data-mcp:8910`.
- [ ] Expose frontend on host port `8920`.
- [ ] Document how to open the dashboard and how it relates to the background learning loop.
- [ ] Rebuild containers and verify backend plus frontend are running.

### Task 5: Browser Verification

**Files:**
- No source files unless verification exposes a bug.

- [ ] Open `http://localhost:8920`.
- [ ] Verify the dashboard renders from `/api/dashboard`.
- [ ] Check desktop and mobile widths for text overlap.
- [ ] Confirm there are no search inputs and no betting/profit promises.
- [ ] Capture final status with tests, build, container state, and browser verification.

---

Self-review:

- Spec coverage: The plan covers read-only panels, no query inputs, automatic data refresh, backend aggregation, frontend container, and visual verification.
- Placeholder scan: No placeholder steps remain.
- Type consistency: The frontend reads `/api/dashboard`, which Task 1 defines as the backend route and Task 4 proxies through Nginx.

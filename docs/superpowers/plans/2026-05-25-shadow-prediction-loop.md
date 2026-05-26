# Shadow Prediction Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand paper learning from sparse final picks into a high-volume shadow prediction loop with configurable concurrent analysis, persisted analyzed samples, settlement metrics, and shortlist funnel diagnostics.

**Architecture:** Keep user-facing recommendations conservative while recording every analyzed match attempt as a separate shadow prediction. Reuse shortlist analysis output for shadow rows so no second model path is created. Settlement and metrics stay paper-only and separate from recommendation calibration.

**Tech Stack:** Python 3.12, SQLite, pytest, existing FastMCP tools.

---

### Task 1: Shortlist Funnel Diagnostics And Larger Bounded Concurrency

**Files:**
- Modify: `football_data_mcp/sources.py`
- Modify: `football_data_mcp/server.py`
- Test: `tests/test_learning_cycle.py`

- [ ] Add a test that calls `shortlist_value_matches` with `analysis_candidate_limit=60` and `analysis_concurrency=12` against fake matches, then asserts `analysis_candidate_limit == 60`, `analysis_concurrency == 12`, `analyzed_count == 60`, and `funnel_report.rejection_reasons` counts rejected reasons.
- [ ] Update `shortlist_value_matches` to clamp `analysis_candidate_limit` to `min(limit, requested, 100)` instead of 30 and `analysis_concurrency` to 16 instead of 8.
- [ ] Add `_shortlist_funnel_report(result pieces)` helper that returns candidate counts, reject reason counts, hard blocker counts, and missing/low-quality counts.
- [ ] Pass larger default arguments through `server.shortlist_value_matches` documentation without changing default user-facing `top_n`.

### Task 2: Shadow Prediction Store

**Files:**
- Modify: `football_data_mcp/learning_store.py`
- Test: `tests/test_learning_store.py`

- [ ] Add failing tests for `save_shadow_prediction_records`, `list_shadow_prediction_records`, `settle_shadow_predictions`, and `shadow_prediction_metrics`.
- [ ] Add a `shadow_prediction_records` SQLite table with unique `shadow_key`, match identity, selected market fields, decision state, rejection reason, JSON evidence, settlement fields, and timestamps.
- [ ] Implement `build_shadow_prediction_records_from_shortlist(result, run_id, limit)` that converts both `picks` and `rejected` shortlist rows into shadow rows.
- [ ] Implement settlement using the existing score matching and payout logic when the shadow row has a supported market/selection.
- [ ] Implement metrics grouped by `decision`, `market`, and settlement status, including settled count, hit rate, and ROI where available.

### Task 3: Auto-Learning Integration

**Files:**
- Modify: `football_data_mcp/sources.py`
- Modify: `football_data_mcp/server.py`
- Modify: `README.md`
- Test: `tests/test_learning_cycle.py`

- [ ] Add failing tests that `run_auto_learning_cycle` stores shadow predictions from both picks and rejected items and reports `shadow_prediction_record_count`.
- [ ] Add parameters `include_shadow_predictions=True`, `shadow_prediction_limit=100`, `analysis_candidate_limit=80`, and `analysis_concurrency=10` to `run_auto_learning_cycle`.
- [ ] During settlement, call `settle_shadow_predictions` with the same score rows and include `shadow_prediction_metrics` in the returned payload and calibration status.
- [ ] Update MCP tool signatures so users can request wider paper-learning samples explicitly.
- [ ] Update README paper-learning notes to distinguish shadow predictions from final recommendations.

### Self-Review

- Spec coverage: The plan covers multi-concurrency analysis, multi-sample storage, settlement, metrics, and diagnostics.
- Placeholder scan: No `TBD`, `TODO`, or unbounded future work.
- Type consistency: Shadow rows are separate from recommendation records and do not alter live recommendation calibration directly.

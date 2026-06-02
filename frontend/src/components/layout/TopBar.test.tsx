import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TopBar } from "./TopBar";
import type { DashboardSnapshot } from "../../types";

function snapshot(overrides: Partial<DashboardSnapshot> = {}): DashboardSnapshot {
  return {
    status: "ok",
    tool: "dashboard_snapshot",
    generated_at_utc: new Date().toISOString(),
    db_path: "/tmp/db.sqlite3",
    kpis: {
      open_records: 0,
      settled_records: 0,
      tracked_only_records: 0,
      duplicate_ignored_records: 0,
      asian_pick_count: 0,
      observation_count: 0,
      calibration_bucket_count: 0,
      strategy_sample_count: 0,
      live_calibration_active: true,
    },
    prediction_kpis: {
      total_count: 0,
      recommended_count: 0,
      observation_count: 0,
      open_count: 0,
      settled_count: 0,
      hit_count: 0,
      miss_count: 0,
      hit_rate: null,
      roi: null,
    },
    market_snapshot_summary: {
      db_path: "/tmp/snapshots.sqlite3",
      total_snapshot_count: 0,
      event_count: 0,
      bookmaker_count: 0,
      latest_fetched_at_utc: null,
      provider_count: 0,
      providers: [],
      market_type_counts: [],
      latest_events: [],
    },
    strategy_state: {
      key: "asian_handicap",
      market: "asian_handicap",
      mode: "paper",
      status: "live_calibration_active",
      active: true,
      sample_count: 0,
      hit_rate: null,
      roi: null,
      avg_model_probability: null,
      min_live_sample_count: 30,
      prior_strength: 30,
      min_calibrated_probability: 0.58,
      min_decimal_odds: 1.55,
      max_decimal_odds: 2,
      min_value_edge: 0.02,
      updated_at_utc: null,
      raw: {},
    },
    asian_picks: [],
    candidate_filters: [],
    recent_settlements: [],
    prediction_ledger: [],
    learning_events: [],
    buckets: [],
    policy: {
      read_only: true,
      no_search_inputs: true,
      data_rule: "test",
    },
    auto_learning_state: {
      enabled: true,
      run_count: 0,
      last_error: null,
      consecutive_empty_cycles: 0,
    },
    ...overrides,
  };
}

describe("TopBar", () => {
  it("shows stale-refreshing dashboard cache status", () => {
    render(
      <TopBar
        snapshot={snapshot({ dashboard_cache: { status: "stale_refreshing", age_seconds: 42 } })}
        darkMode={false}
        onToggleDark={() => {}}
        refreshing={false}
        lastRefreshError={null}
      />,
    );

    expect(screen.getByText("快照刷新中")).toBeInTheDocument();
  });

  it("exposes a manual force-refresh action", () => {
    const onRefresh = vi.fn();
    render(
      <TopBar
        snapshot={snapshot()}
        darkMode={false}
        onToggleDark={() => {}}
        onRefresh={onRefresh}
        refreshing={false}
        lastRefreshError={null}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "强制刷新看板" }));

    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it("disables force refresh while a refresh is already running", () => {
    const onRefresh = vi.fn();
    render(
      <TopBar
        snapshot={snapshot()}
        darkMode={false}
        onToggleDark={() => {}}
        onRefresh={onRefresh}
        refreshing
        lastRefreshError={null}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "强制刷新看板" }));

    expect(onRefresh).not.toHaveBeenCalled();
  });
});

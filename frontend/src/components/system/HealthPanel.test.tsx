import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HealthPanel } from "./HealthPanel";
import type { DashboardSnapshot } from "../../types";

function snapshot(overrides: Partial<DashboardSnapshot> = {}): DashboardSnapshot {
  return {
    status: "ok",
    tool: "dashboard_snapshot",
    generated_at_utc: "2026-06-02T05:00:00+00:00",
    db_path: "/tmp/learning.sqlite3",
    kpis: {
      open_records: 0,
      settled_records: 0,
      tracked_only_records: 0,
      duplicate_ignored_records: 0,
      asian_pick_count: 0,
      observation_count: 0,
      calibration_bucket_count: 0,
      strategy_sample_count: 0,
      live_calibration_active: false,
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
      total_snapshot_count: 8,
      event_count: 1,
      bookmaker_count: 4,
      latest_fetched_at_utc: "2026-06-02T04:50:00+00:00",
      provider_count: 1,
      providers: [],
      market_type_counts: [],
      latest_events: [],
    },
    strategy_state: {
      key: "asian_handicap",
      market: "asian_handicap",
      mode: "balanced",
      status: "collecting",
      active: false,
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
    auto_learning_state: {
      enabled: true,
      run_count: 0,
      last_error: null,
      consecutive_empty_cycles: 0,
    },
    buckets: [],
    source_health: {
      leisu: { status: "blocked", error: "雷速访问受限" },
    },
    odds_source_status: {
      status: "ok",
      closure: {
        active_source: "analysis_odds",
        production_ready: false,
        reason: "主赔率源已过期，当前只能使用分析过程沉淀的快照兜底。",
        checked_at_utc: "2026-06-02T05:00:00+00:00",
        fresh_after_hours: 6,
        ordered_sources: [
          {
            source: "leisu",
            operational_status: "stale",
            freshness_status: "stale",
            snapshot_count: 20,
            latest_fetched_at_utc: "2026-05-29T04:38:30+00:00",
            usable_for_analysis: false,
          },
          {
            source: "analysis_odds",
            operational_status: "derived_fallback",
            freshness_status: "fresh",
            snapshot_count: 8,
            latest_fetched_at_utc: "2026-06-02T04:51:00+00:00",
            usable_for_analysis: true,
          },
        ],
      },
      sources: {
        oddsportal_scraper: {
          status: "failed",
          role: "experimental fallback odds crawler for 1X2/AH/O-U snapshots",
          snapshot_count: 8,
          operational_status: "retryable",
          latest_fetched_at_utc: "2026-06-02T04:51:00+00:00",
          fresh_after_hours: 6,
          freshness_status: "fresh",
          age_hours: 0.15,
          age_seconds: 540,
          usable_for_analysis: true,
          retryable_url_count: 1,
          failed_count: 1,
          empty_count: 0,
          queued_count: 0,
          running_count: 0,
          scraper_enabled: true,
          auto_sync_enabled: true,
          discovery_ready: true,
          configured_discovery_url_count: 1,
          suggested_discovery_url_count: 1,
          effective_discovery_url_count: 1,
          discovery_urls: ["https://www.oddsportal.com/football/japan/j1-league/"],
          suggested_discovery_urls: ["https://www.oddsportal.com/football/japan/j1-league/"],
          effective_discovery_urls: ["https://www.oddsportal.com/football/japan/j1-league/"],
          open_target_count: 2,
          analysis_target_count: 2,
          discovery_target_count: 2,
          discovery_target_source: "analysis_odds",
          last_error: "timeout",
          next_action: "调用 /api/sources/odds/oddsportal/sync resume_failed=true 续跑失败/空结果 URL。",
          sync: {
            latest_status: "failed",
            snapshot_count: 8,
            latest_finished_at_utc: "2026-06-02T04:51:00+00:00",
          },
        },
      },
      policy: {
        fallback_rule: "Leisu 赔率不可用时，可用 oddsportal_scraper 补充赔率快照。",
        resume_rule: "按 odds_source_sync_state 续跑失败或未完成项。",
      },
    },
    policy: {
      read_only: true,
      no_search_inputs: true,
      data_rule: "test",
    },
    ...overrides,
  };
}

describe("HealthPanel", () => {
  it("shows fallback odds crawler state instead of hiding odds source status", () => {
    render(<HealthPanel snapshot={snapshot()} />);

    expect(screen.getByText("雷速")).toBeInTheDocument();
    expect(screen.getByText(/当前：分析快照/)).toBeInTheDocument();
    expect(screen.getByText(/仅观察\/兜底/)).toBeInTheDocument();
    expect(screen.getByText(/主赔率源已过期/)).toBeInTheDocument();
    expect(screen.getByText("OddsPortal 爬虫")).toBeInTheDocument();
    expect(screen.getByText(/8 条亚盘快照/)).toBeInTheDocument();
    expect(screen.getByText(/1 个可续跑/)).toBeInTheDocument();
    expect(screen.getByText(/发现页 1/)).toBeInTheDocument();
    expect(screen.getByText(/分析种子 2/)).toBeInTheDocument();
    expect(screen.getByText(/自动开/)).toBeInTheDocument();
    expect(screen.getByText(/resume_failed=true/)).toBeInTheDocument();
  });
});

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { DashboardSnapshot, ValidationJob } from "./types";

vi.mock("./api/dashboardClient", () => {
  class HttpError extends Error {
    readonly status: number;
    readonly bodyExcerpt: string;
    constructor(status: number, message: string, bodyExcerpt = "") {
      super(message);
      this.status = status;
      this.bodyExcerpt = bodyExcerpt;
    }
  }
  return {
    HttpError,
    fetchDashboardSnapshot: vi.fn(),
    fetchMatchDetail: vi.fn(),
    startHoldoutValidationJob: vi.fn(),
    retryHoldoutValidationJob: vi.fn(),
    cancelHoldoutValidationJob: vi.fn(),
  };
});

import { App } from "./App";
import {
  fetchDashboardSnapshot,
  retryHoldoutValidationJob,
  startHoldoutValidationJob,
} from "./api/dashboardClient";

const fetchDashboardSnapshotMock = vi.mocked(fetchDashboardSnapshot);
const startHoldoutValidationJobMock = vi.mocked(startHoldoutValidationJob);
const retryHoldoutValidationJobMock = vi.mocked(retryHoldoutValidationJob);

function validationJob(overrides: Partial<ValidationJob> = {}): ValidationJob {
  const status = overrides.status ?? "pending";
  return {
    job_id: "holdout-1",
    method: "holdout_validation_job_v1",
    status,
    divisions: ["E0", "SP1"],
    training_seasons: ["2122"],
    validation_seasons: ["2223"],
    progress: {
      total_leagues: 2,
      completed_leagues: status === "completed" ? 2 : 0,
      failed_leagues: status === "failed" ? 1 : 0,
      running_leagues: status === "running" ? 1 : 0,
      pending_leagues: status === "pending" ? 2 : status === "running" ? 1 : 0,
      cancelled_leagues: 0,
      processed_leagues: status === "failed" ? 1 : status === "completed" ? 2 : 0,
      progress_ratio: status === "completed" ? 1 : status === "failed" ? 0.5 : 0,
      success_ratio: status === "completed" ? 1 : 0,
    },
    league_results: [
      {
        division: "E0",
        league: "英超",
        status: status === "failed" ? "failed" : status === "running" ? "running" : status === "completed" ? "succeeded" : "pending",
        cache_hit: false,
        error: status === "failed" ? "temporary source failure" : null,
      },
      {
        division: "SP1",
        league: "西甲",
        status: status === "completed" ? "succeeded" : "pending",
        cache_hit: false,
      },
    ],
    result_summary: status === "completed"
      ? { completed_leagues: 2, failed_leagues: 0, log_loss_diff: -0.02, roi: 0.04 }
      : {},
    attempt_count: status === "pending" ? 0 : 1,
    retry_count: status === "running" ? 1 : 0,
    last_claim_reason: status === "running" ? "claimed" : null,
    last_retry_at_utc: status === "running" ? "2026-06-02T05:45:00+00:00" : null,
    runner_heartbeat_at_utc: status === "running" ? "2026-06-02T05:50:00+00:00" : null,
    failure_summary: {
      failed_count: status === "failed" ? 1 : 0,
      recoverable: status !== "completed",
      recoverable_count: status === "completed" ? 0 : status === "failed" ? 2 : 2,
      latest_error: status === "failed" ? "temporary source failure" : null,
      category: status === "failed" ? "data_source" : status === "completed" ? "none" : "pending",
      stage: status === "failed" ? "league_validation" : status === "completed" ? "none" : "queue_wait",
      severity: status === "failed" ? "error" : "info",
      title: status === "failed" ? "数据源或样本读取失败" : status === "completed" ? "暂无失败" : "仍有联赛待执行",
      detail: status === "failed" ? "验证阶段无法稳定读取比赛、赔率或样本数据。" : "",
      next_action: status === "failed" ? "检查数据源健康、赔率/赛程快照和缓存；修复后点重试，已成功联赛会保留结果。" : "等待 worker 执行；若长期不动，检查队列健康和 runner 心跳。",
      failed_leagues: status === "failed"
        ? [{ division: "E0", league: "英超", status: "failed", error: "temporary source failure" }]
        : [],
    },
    events: [
      {
        id: 1,
        event_type: "job_created",
        severity: "info",
        message: "Created holdout validation job for 2 leagues.",
        metadata: {},
        created_at_utc: "2026-06-02T05:40:00+00:00",
      },
      {
        id: 2,
        event_type: status === "failed" ? "league_failed" : status === "completed" ? "job_completed" : "job_queued",
        severity: status === "failed" ? "error" : "info",
        message: status === "failed" ? "英超 failed: temporary source failure" : "Holdout validation was queued in ARQ and will be executed by the worker.",
        division: status === "failed" ? "E0" : null,
        metadata: {},
        created_at_utc: "2026-06-02T05:41:00+00:00",
      },
    ],
    queue_backend: "arq",
    queue_job_id: "holdout-validation:holdout-1",
    queued_at_utc: "2026-06-02T05:41:35+00:00",
    queue_status_message: "Holdout validation was queued in ARQ and will be executed by the worker.",
    current_runner_id: status === "running" ? "runnerabcdef123456" : null,
    ...overrides,
  };
}

function dashboardSnapshot(overrides: Partial<DashboardSnapshot> = {}): DashboardSnapshot {
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
    buckets: [],
    auto_learning_state: {
      enabled: true,
      run_count: 0,
      last_error: null,
      consecutive_empty_cycles: 0,
    },
    task_queue: {
      backend: "arq",
      status: "ok",
      redis_reachable: true,
      queue_name: "football-data-mcp",
      queued_jobs: 0,
      worker_healthy: true,
      worker_health_ttl_seconds: 300,
      detail: "ARQ worker 已上报健康检查。",
    },
    policy: {
      read_only: true,
      no_search_inputs: true,
      data_rule: "test",
    },
    validation_job: null,
    ...overrides,
  };
}

function renderModelPageWithSnapshot(initialSnapshot: DashboardSnapshot) {
  let currentSnapshot = initialSnapshot;
  fetchDashboardSnapshotMock.mockImplementation(async () => currentSnapshot);

  window.history.pushState(null, "", "/model");
  render(<App />);

  return {
    setSnapshot(next: DashboardSnapshot) {
      currentSnapshot = next;
    },
  };
}

describe("App holdout validation flow", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.history.pushState(null, "", "/model");
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("starts a holdout validation job and refreshes the model page into pending progress", async () => {
    const pendingJob = validationJob({ status: "pending" });
    const { setSnapshot } = renderModelPageWithSnapshot(dashboardSnapshot());
    startHoldoutValidationJobMock.mockImplementation(async () => {
      setSnapshot(dashboardSnapshot({ validation_job: pendingJob }));
      return pendingJob;
    });

    fireEvent.click(await screen.findByRole("button", { name: "启动验证" }));

    await waitFor(() => expect(startHoldoutValidationJobMock).toHaveBeenCalledWith({ resume: true, start: true }));
    await waitFor(() => expect(screen.getAllByText("等待中").length).toBeGreaterThan(0));

    expect(fetchDashboardSnapshotMock).toHaveBeenCalledWith(expect.objectContaining({ forceRefresh: true }));
    expect(screen.getByText("已处理 0/2 联赛")).toBeInTheDocument();
    expect(screen.getByText(/ARQ worker 队列/)).toBeInTheDocument();
    expect(screen.getByText("执行时间线")).toBeInTheDocument();
    expect(screen.getByText(/holdout-validation:holdout-1/)).toBeInTheDocument();
    expect(screen.getByText(/等待 worker 接管/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "取消" })).toBeInTheDocument();
    expect(screen.getByText("Holdout 验证已入队")).toBeInTheDocument();
  });

  it("retries a failed validation job and refreshes the model page into running progress", async () => {
    const failedJob = validationJob({ status: "failed" });
    const runningJob = validationJob({ status: "running" });
    const { setSnapshot } = renderModelPageWithSnapshot(dashboardSnapshot({ validation_job: failedJob }));
    retryHoldoutValidationJobMock.mockImplementation(async () => {
      setSnapshot(dashboardSnapshot({ validation_job: runningJob }));
      return runningJob;
    });

    fireEvent.click(await screen.findByRole("button", { name: "重试" }));

    await waitFor(() => expect(retryHoldoutValidationJobMock).toHaveBeenCalledWith("holdout-1"));
    await waitFor(() => expect(screen.getAllByText("运行中").length).toBeGreaterThan(0));

    expect(fetchDashboardSnapshotMock).toHaveBeenCalledWith(expect.objectContaining({ forceRefresh: true }));
    expect(screen.getByText("已处理 0/2 联赛")).toBeInTheDocument();
    expect(screen.getByText(/ARQ worker 队列/)).toBeInTheDocument();
    expect(screen.getByText(/第 1 次执行/)).toBeInTheDocument();
    expect(screen.getByText(/runner runnerabcdef/)).toBeInTheDocument();
    expect(screen.getByText(/已重试 1 次/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "取消" })).toBeInTheDocument();
    expect(screen.getByText("Holdout 验证已重新入队")).toBeInTheDocument();
  });
});

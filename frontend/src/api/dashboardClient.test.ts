import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import {
  cancelHoldoutValidationJob,
  fetchDashboardSnapshot,
  fetchMatchDetail,
  retryHoldoutValidationJob,
  sendPredictionToLark,
  startHoldoutValidationJob,
} from "./dashboardClient";

function mockFetchOnce(response: { ok: boolean; status: number; body: any; bodyKind?: "json" | "text" }) {
  globalThis.fetch = vi.fn(async () => {
    const headers = new Headers({ "Content-Type": response.bodyKind === "text" ? "text/html" : "application/json" });
    return {
      ok: response.ok,
      status: response.status,
      headers,
      json: async () => (response.bodyKind === "text" ? Promise.reject(new SyntaxError("Unexpected token")) : response.body),
      text: async () => (typeof response.body === "string" ? response.body : JSON.stringify(response.body)),
    } as unknown as Response;
  }) as any;
}

const validSnapshot = {
  status: "ok",
  tool: "dashboard_snapshot",
  generated_at_utc: "2026-05-25T05:30:00+00:00",
  db_path: "/data/db.sqlite",
  kpis: {
    open_records: 1,
    settled_records: 1,
    tracked_only_records: 0,
    duplicate_ignored_records: 0,
    asian_pick_count: 0,
    observation_count: 0,
    calibration_bucket_count: 0,
    strategy_sample_count: 0,
    live_calibration_active: false,
  },
  prediction_kpis: {
    total_count: 1,
    recommended_count: 0,
    observation_count: 1,
    open_count: 1,
    settled_count: 0,
    hit_count: 0,
    miss_count: 0,
    hit_rate: null,
    roi: null,
  },
};

const validValidationJob = {
  job_id: "holdout-1",
  method: "holdout_validation_job_v1",
  status: "cancelled",
  current_runner_id: "runner-a",
  attempt_count: 1,
  retry_count: 0,
  last_claim_reason: "claimed",
  last_retry_at_utc: null,
  runner_heartbeat_at_utc: "2026-06-02T05:50:00+00:00",
  recovered_at_utc: null,
  queue_backend: "arq",
  queue_job_id: "holdout-validation:holdout-1",
  queued_at_utc: "2026-06-02T05:41:35+00:00",
  queue_status_message: "Holdout validation was queued in ARQ and will be executed by the worker.",
  failure_summary: {
    failed_count: 0,
    recoverable: true,
    recoverable_count: 2,
    latest_error: "Cancelled by user.",
    category: "cancelled",
    stage: "user_control",
    severity: "warning",
    title: "任务已取消",
    detail: "验证任务被用户或控制流程取消。",
    next_action: "需要继续验证时点击重试；系统会从未成功联赛继续。",
    failed_leagues: [],
  },
  events: [
    {
      id: 1,
      event_type: "job_cancelled",
      severity: "warning",
      message: "Cancelled by user.",
      metadata: {},
      created_at_utc: "2026-06-02T05:50:00+00:00",
    },
  ],
  progress: {
    total_leagues: 2,
    completed_leagues: 0,
    failed_leagues: 0,
    running_leagues: 0,
    pending_leagues: 0,
    cancelled_leagues: 2,
    processed_leagues: 2,
    progress_ratio: 1,
    success_ratio: 0,
  },
  league_results: [
    { division: "E0", league: "England Premier League", status: "cancelled", cache_hit: false },
    { division: "SP1", league: "Spain La Liga", status: "cancelled", cache_hit: false },
  ],
};

describe("fetchDashboardSnapshot", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns parsed snapshot on 200", async () => {
    mockFetchOnce({ ok: true, status: 200, body: validSnapshot });
    const data = await fetchDashboardSnapshot();
    expect(data.generated_at_utc).toBe(validSnapshot.generated_at_utc);
  });

  it("requests a fresh dashboard snapshot when forceRefresh is set", async () => {
    mockFetchOnce({ ok: true, status: 200, body: validSnapshot });
    await fetchDashboardSnapshot({ forceRefresh: true });
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/dashboard?refresh=true",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("throws HTTP error before parsing on 5xx HTML body", async () => {
    mockFetchOnce({ ok: false, status: 502, body: "<html>bad gateway</html>", bodyKind: "text" });
    await expect(fetchDashboardSnapshot()).rejects.toThrow(/HTTP 502/);
  });

  it("throws schema error when required fields are missing", async () => {
    const broken = { ...validSnapshot, kpis: undefined as any };
    mockFetchOnce({ ok: true, status: 200, body: broken });
    await expect(fetchDashboardSnapshot()).rejects.toThrow(/schema|kpis/i);
  });

  it("accepts the normalized contract sub-shapes from the backend", async () => {
    const enriched = {
      ...validSnapshot,
      auto_learning_state: {
        enabled: true,
        run_count: 12,
        last_error: null,
        last_finished_at_utc: "2026-05-28T07:00:00+00:00",
        consecutive_empty_cycles: 0,
        last_result_summary: { asian_total_candidates: 6 },
      },
      latest_validation: {
        method: "holdout_v2",
        automation_readiness: "not_ready",
        beats_market: false,
        bet_count: 0,
        evaluated_count: 84,
      },
      buckets: [
        { band: "0.40-0.45", market: "asian_handicap", sample_count: 206, hit_count: 98, hit_rate: 0.476, roi: -0.0286 },
      ],
      learning_events: [
        { kind: "strategy", severity: "ok", title: "策略状态刷新", detail: "live_calibration_active", at_utc: "2026-05-28T07:00:54+00:00" },
      ],
      backtest_curve: { points: [{ label: "0", roi: 0.0 }, { label: "5", roi: -0.03 }] },
      source_health: { football_data: { status: "ok" } },
      program_capabilities: {
        status: "limited",
        operating_mode: "paper_learning",
        summary: { total_count: 2, ready_count: 1, warning_count: 0, blocked_count: 1 },
        capabilities: [
          {
            key: "continuous_prediction",
            title: "持续预测与观察入库",
            status: "ok",
            available: true,
            current: 12,
            target: 20,
            ratio: 0.6,
            detail: "已有预测样本。",
            next_action: "继续采样。",
          },
          {
            key: "production_release_gate",
            title: "正式推荐发布门禁",
            status: "blocked",
            available: false,
            current: 0,
            target: 1,
            ratio: 0,
            detail: "正式推荐仍受质量门禁控制。",
          },
        ],
      },
      task_queue: {
        backend: "arq",
        status: "ok",
        redis_reachable: true,
        queue_name: "football-data-mcp",
        queued_jobs: 0,
        worker_healthy: true,
        worker_health_ttl_seconds: 300,
        validation_job_stale_after_seconds: 3900,
        detail: "ARQ worker 已上报健康检查。",
      },
      odds_source_status: {
        status: "ok",
        closure: {
          active_source: "oddsportal_scraper",
          production_ready: true,
          reason: "雷速不可用或过期，当前使用独立爬虫赔率源兜底。",
          checked_at_utc: "2026-06-02T05:50:00+00:00",
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
              source: "oddsportal_scraper",
              operational_status: "available",
              freshness_status: "fresh",
              snapshot_count: 8,
              latest_fetched_at_utc: "2026-06-02T05:30:00+00:00",
              usable_for_analysis: true,
            },
          ],
        },
        sources: {
          oddsportal_scraper: {
            status: "succeeded",
            role: "fallback crawler",
            snapshot_count: 8,
            operational_status: "available",
            latest_fetched_at_utc: "2026-06-02T05:30:00+00:00",
            fresh_after_hours: 6,
            freshness_status: "fresh",
            age_hours: 0.333,
            age_seconds: 1200,
            usable_for_analysis: true,
            retryable_url_count: 0,
            queued_count: 0,
            running_count: 0,
            failed_count: 0,
            empty_count: 0,
            scraper_enabled: true,
            auto_sync_enabled: true,
            discovery_ready: true,
            configured_discovery_url_count: 1,
            suggested_discovery_url_count: 1,
            effective_discovery_url_count: 1,
            discovery_urls: ["https://www.oddsportal.com/football/japan/j1-league/"],
            suggested_discovery_urls: ["https://www.oddsportal.com/football/japan/j1-league/"],
            effective_discovery_urls: ["https://www.oddsportal.com/football/japan/j1-league/"],
            open_target_count: 3,
            analysis_target_count: 0,
            discovery_target_count: 3,
            discovery_target_source: "open_prediction",
            last_error: null,
            next_action: "已有 fallback 快照；继续按需补充新比赛 URL。",
            sync: {
              latest_status: "succeeded",
              attempt_count: 2,
              snapshot_count: 8,
              latest_finished_at_utc: "2026-06-02T05:30:00+00:00",
            },
          },
        },
      },
      validation_job: {
        job_id: "holdout-1",
        method: "holdout_validation_job_v1",
        status: "running",
        current_runner_id: "runner-a",
        attempt_count: 2,
        retry_count: 1,
        last_claim_reason: "recovered_stale_runner",
        last_retry_at_utc: "2026-06-02T05:45:00+00:00",
        runner_heartbeat_at_utc: "2026-06-02T05:50:00+00:00",
        recovered_at_utc: "2026-06-02T05:49:00+00:00",
        failure_summary: {
          failed_count: 0,
          recoverable: true,
          recoverable_count: 1,
          latest_error: null,
          category: "pending",
          stage: "queue_wait",
          severity: "info",
          title: "仍有联赛待执行",
          detail: "任务还有未完成联赛，但暂未发现明确失败。",
          next_action: "等待 worker 执行；若长期不动，检查队列健康和 runner 心跳。",
          failed_leagues: [],
        },
        events: [
          {
            id: 1,
            event_type: "job_claimed",
            severity: "info",
            message: "Worker claimed the validation job.",
            runner_id: "runner-a",
            metadata: { claim_reason: "claimed" },
            created_at_utc: "2026-06-02T05:50:00+00:00",
          },
        ],
        queue_backend: "arq",
        queue_job_id: "holdout-validation:holdout-1",
        queued_at_utc: "2026-06-02T05:41:35+00:00",
        queue_status_message: "Holdout validation was queued in ARQ and will be executed by the worker.",
        progress: {
          total_leagues: 2,
          completed_leagues: 1,
          failed_leagues: 0,
          running_leagues: 1,
          pending_leagues: 0,
          cancelled_leagues: 0,
          processed_leagues: 1,
          progress_ratio: 0.5,
          success_ratio: 0.5,
        },
        league_results: [
          { division: "E0", league: "England Premier League", status: "succeeded", cache_hit: true },
          { division: "SP1", league: "Spain La Liga", status: "running", cache_hit: false },
        ],
      },
    };
    mockFetchOnce({ ok: true, status: 200, body: enriched });
    const data = await fetchDashboardSnapshot();
    expect(data.auto_learning_state?.run_count).toBe(12);
    expect(data.latest_validation?.method).toBe("holdout_v2");
    expect(data.buckets?.[0].band).toBe("0.40-0.45");
    expect(data.learning_events?.[0].kind).toBe("strategy");
    expect(data.backtest_curve?.points[0].roi).toBe(0);
    expect(data.source_health?.football_data.status).toBe("ok");
    expect(data.program_capabilities?.summary.ready_count).toBe(1);
    expect(data.program_capabilities?.capabilities[0].key).toBe("continuous_prediction");
    expect(data.task_queue?.backend).toBe("arq");
    expect(data.odds_source_status?.sources.oddsportal_scraper.retryable_url_count).toBe(0);
    expect(data.odds_source_status?.sources.oddsportal_scraper.discovery_ready).toBe(true);
    expect(data.odds_source_status?.sources.oddsportal_scraper.open_target_count).toBe(3);
    expect(data.odds_source_status?.sources.oddsportal_scraper.discovery_target_source).toBe("open_prediction");
    expect(data.odds_source_status?.closure?.active_source).toBe("oddsportal_scraper");
    expect(data.odds_source_status?.closure?.production_ready).toBe(true);
    expect(data.validation_job?.progress.completed_leagues).toBe(1);
    expect(data.validation_job?.queue_backend).toBe("arq");
    expect(data.validation_job?.queue_job_id).toBe("holdout-validation:holdout-1");
    expect(data.validation_job?.current_runner_id).toBe("runner-a");
    expect(data.validation_job?.attempt_count).toBe(2);
    expect(data.validation_job?.failure_summary?.recoverable_count).toBe(1);
    expect(data.validation_job?.events[0].event_type).toBe("job_claimed");
  });

  it("rejects malformed odds source operational fields", async () => {
    const bad = {
      ...validSnapshot,
      odds_source_status: {
        status: "ok",
        sources: {
          oddsportal_scraper: {
            status: "failed",
            role: "fallback crawler",
            snapshot_count: 8,
            operational_status: "retryable",
            retryable_url_count: "1",
            discovery_ready: "true",
            next_action: "调用 resume_failed=true 续跑。",
          },
        },
      },
    };
    mockFetchOnce({ ok: true, status: 200, body: bad });
    await expect(fetchDashboardSnapshot()).rejects.toThrow(/retryable_url_count/);
  });

  it("rejects malformed auto_learning_state (must be object)", async () => {
    const bad = { ...validSnapshot, auto_learning_state: "boom" };
    mockFetchOnce({ ok: true, status: 200, body: bad });
    await expect(fetchDashboardSnapshot()).rejects.toThrow(/auto_learning_state/);
  });

  it("rejects buckets where an entry is missing band", async () => {
    const bad = { ...validSnapshot, buckets: [{ sample_count: 1 }] };
    mockFetchOnce({ ok: true, status: 200, body: bad });
    await expect(fetchDashboardSnapshot()).rejects.toThrow(/band/);
  });

  it("rejects malformed program capability matrix", async () => {
    const bad = { ...validSnapshot, program_capabilities: { status: "limited", capabilities: "bad" } };
    mockFetchOnce({ ok: true, status: 200, body: bad });
    await expect(fetchDashboardSnapshot()).rejects.toThrow(/program_capabilities/);
  });

  it("rejects malformed validation job progress", async () => {
    const bad = { ...validSnapshot, validation_job: { job_id: "x", status: "running", league_results: [] } };
    mockFetchOnce({ ok: true, status: 200, body: bad });
    await expect(fetchDashboardSnapshot()).rejects.toThrow(/validation_job/);
  });

  it("rejects malformed validation job league results", async () => {
    const existingValidationJob = (validSnapshot as Record<string, unknown>).validation_job as Record<string, unknown>;
    const bad = {
      ...validSnapshot,
      validation_job: {
        ...existingValidationJob,
        league_results: [{ division: "E0", status: 200, cache_hit: false }],
      },
    };
    mockFetchOnce({ ok: true, status: 200, body: bad });
    await expect(fetchDashboardSnapshot()).rejects.toThrow(/league_results/);
  });

  it("rejects malformed validation league runtime diagnostics", async () => {
    const existingValidationJob = (validSnapshot as Record<string, unknown>).validation_job as Record<string, unknown>;
    const bad = {
      ...validSnapshot,
      validation_job: {
        ...existingValidationJob,
        league_results: [{ division: "E0", status: "running", cache_hit: false, runtime: "running" }],
      },
    };
    mockFetchOnce({ ok: true, status: 200, body: bad });
    await expect(fetchDashboardSnapshot()).rejects.toThrow(/runtime/);
  });

  it("rejects malformed validation job failure summary", async () => {
    const bad = {
      ...validSnapshot,
      validation_job: {
        ...validValidationJob,
        failure_summary: {
          failed_count: "1",
          recoverable: true,
          recoverable_count: 1,
          latest_error: null,
          category: "data_source",
          stage: "league_validation",
          severity: "error",
          title: "数据源或样本读取失败",
          detail: "bad",
          next_action: "bad",
          failed_leagues: [],
        },
      },
    };
    mockFetchOnce({ ok: true, status: 200, body: bad });
    await expect(fetchDashboardSnapshot()).rejects.toThrow(/failure_summary/);
  });

  it("rejects malformed validation job event timeline", async () => {
    const bad = {
      ...validSnapshot,
      validation_job: {
        ...validValidationJob,
        events: [{ event_type: "job_created", severity: "info", message: 123 }],
      },
    };
    mockFetchOnce({ ok: true, status: 200, body: bad });
    await expect(fetchDashboardSnapshot()).rejects.toThrow(/events/);
  });

  it("rejects malformed task queue health", async () => {
    const bad = { ...validSnapshot, task_queue: { backend: "arq", status: 200 } };
    mockFetchOnce({ ok: true, status: 200, body: bad });
    await expect(fetchDashboardSnapshot()).rejects.toThrow(/task_queue/);
  });

  it("rejects malformed dashboard policy enrichment flag", async () => {
    const bad = {
      ...validSnapshot,
      policy: {
        read_only: true,
        no_search_inputs: true,
        background_enrichment_refresh: "false",
        data_rule: "Dashboard reads persisted state",
      },
    };
    mockFetchOnce({ ok: true, status: 200, body: bad });
    await expect(fetchDashboardSnapshot()).rejects.toThrow(/background_enrichment_refresh/);
  });

  it("rejects malformed model failure diagnostics", async () => {
    const bad = {
      ...validSnapshot,
      model_failure_diagnostics: {
        status: "losing_model",
        severity: "error",
        title: "模型当前亏损",
        detail: "bad",
        summary: { settled_count: 6, negative_driver_count: 1 },
        drivers: [{ category: "reason", key: "x", title: "x", sample_count: "6", loss_units: 1 }],
      },
    };
    mockFetchOnce({ ok: true, status: 200, body: bad });
    await expect(fetchDashboardSnapshot()).rejects.toThrow(/model_failure_diagnostics/);
  });

  it("rejects malformed model failure policy rules", async () => {
    const bad = {
      ...validSnapshot,
      model_failure_diagnostics: {
        status: "losing_model",
        severity: "error",
        title: "模型当前亏损",
        detail: "bad",
        summary: { settled_count: 6, negative_driver_count: 1 },
        drivers: [],
        policy: {
          formal_recommendation_enabled: false,
          reason: "model_failure_diagnostics",
          rules: [
            {
              key: "suppress_reason:x",
              type: "suppress_reason",
              status: "blocked",
              title: "阻断",
              detail: "bad",
              action: 42,
              target: "prediction_diagnostic.primary_reason",
              target_key: "x",
              sample_count: 6,
              roi: -0.2,
              loss_units: 1.2,
            },
          ],
        },
      },
    };
    mockFetchOnce({ ok: true, status: 200, body: bad });
    await expect(fetchDashboardSnapshot()).rejects.toThrow(/model_failure_diagnostics/);
  });

  it("respects AbortSignal", async () => {
    globalThis.fetch = vi.fn(async (_url, init?: RequestInit) => {
      return await new Promise((_, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      });
    }) as any;
    const controller = new AbortController();
    const p = fetchDashboardSnapshot({ signal: controller.signal });
    controller.abort();
    await expect(p).rejects.toThrow(/abort/i);
  });
});

describe("fetchMatchDetail", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("returns parsed detail on 200", async () => {
    mockFetchOnce({
      ok: true,
      status: 200,
      body: { status: "ok", tool: "dashboard_match_detail", record: { ledger_id: "x:1" } },
    });
    const data = await fetchMatchDetail("x:1");
    expect(data.record.ledger_id).toBe("x:1");
  });

  it("turns 404 into a human message before parsing", async () => {
    mockFetchOnce({ ok: false, status: 404, body: "<html>not found</html>", bodyKind: "text" });
    await expect(fetchMatchDetail("x:1")).rejects.toThrow(/不存在|HTTP 404/);
  });

  it("throws schema error on missing record field", async () => {
    mockFetchOnce({ ok: true, status: 200, body: { status: "ok", tool: "dashboard_match_detail" } });
    await expect(fetchMatchDetail("x:1")).rejects.toThrow(/schema|record/i);
  });
});

describe("sendPredictionToLark", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("posts the prediction sample to the match Lark endpoint", async () => {
    mockFetchOnce({
      ok: true,
      status: 200,
      body: {
        status: "ok",
        tool: "lark_prediction_notification",
        sent: true,
        channel: "lark",
        ledger_id: "recommendation:2726",
      },
    });

    const data = await sendPredictionToLark("recommendation:2726");

    expect(data.sent).toBe(true);
    expect(data.ledger_id).toBe("recommendation:2726");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/dashboard/match/recommendation%3A2726/lark",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("rejects malformed Lark send responses", async () => {
    mockFetchOnce({
      ok: true,
      status: 200,
      body: { status: "ok", tool: "lark_prediction_notification", sent: "yes" },
    });

    await expect(sendPredictionToLark("recommendation:2726")).rejects.toThrow(/sent/);
  });
});

describe("holdout validation job controls", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("cancels a holdout validation job with POST", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => validValidationJob,
      text: async () => JSON.stringify(validValidationJob),
    } as unknown as Response));
    globalThis.fetch = fetchMock as any;

    const data = await cancelHoldoutValidationJob("holdout/unsafe id");

    expect(data.status).toBe("cancelled");
    expect(data.progress.cancelled_leagues).toBe(2);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/validation/holdout/jobs/holdout%2Funsafe%20id/cancel",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("retries a holdout validation job with POST", async () => {
    const retryingJob = { ...validValidationJob, status: "pending" };
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => retryingJob,
      text: async () => JSON.stringify(retryingJob),
    } as unknown as Response));
    globalThis.fetch = fetchMock as any;

    const data = await retryHoldoutValidationJob("holdout-1");

    expect(data.status).toBe("pending");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/validation/holdout/jobs/holdout-1/retry",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("starts or resumes a holdout validation job with POST body", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => validValidationJob,
      text: async () => JSON.stringify(validValidationJob),
    } as unknown as Response));
    globalThis.fetch = fetchMock as any;

    const data = await startHoldoutValidationJob({ resume: true, start: true });

    expect(data.job_id).toBe(validValidationJob.job_id);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/validation/holdout/jobs",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ resume: true, start: true }),
      }),
    );
  });
});

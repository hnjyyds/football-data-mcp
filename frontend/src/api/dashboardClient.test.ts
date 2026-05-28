import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { fetchDashboardSnapshot, fetchMatchDetail } from "./dashboardClient";

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
    };
    mockFetchOnce({ ok: true, status: 200, body: enriched });
    const data = await fetchDashboardSnapshot();
    expect(data.auto_learning_state?.run_count).toBe(12);
    expect(data.latest_validation?.method).toBe("holdout_v2");
    expect(data.buckets?.[0].band).toBe("0.40-0.45");
    expect(data.learning_events?.[0].kind).toBe("strategy");
    expect(data.backtest_curve?.points[0].roi).toBe(0);
    expect(data.source_health?.football_data.status).toBe("ok");
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

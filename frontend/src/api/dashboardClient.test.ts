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

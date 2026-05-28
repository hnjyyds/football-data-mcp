import type { DashboardMatchDetail, DashboardSnapshot } from "../types";

export class HttpError extends Error {
  readonly status: number;
  readonly bodyExcerpt: string;
  constructor(status: number, message: string, bodyExcerpt = "") {
    super(message);
    this.name = "HttpError";
    this.status = status;
    this.bodyExcerpt = bodyExcerpt;
  }
}

export class SchemaError extends Error {
  readonly path: string;
  constructor(path: string, message: string) {
    super(`schema error at ${path}: ${message}`);
    this.name = "SchemaError";
    this.path = path;
  }
}

type Issues = string[];

function expectObject(value: unknown, path: string, issues: Issues): value is Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) return true;
  issues.push(`${path} must be an object, got ${value === null ? "null" : typeof value}`);
  return false;
}

function expectField(obj: Record<string, unknown>, key: string, kind: "string" | "number" | "boolean", path: string, issues: Issues, opts: { nullable?: boolean } = {}) {
  const v = obj[key];
  if (v === undefined) {
    issues.push(`${path}.${key} is required`);
    return;
  }
  if (opts.nullable && v === null) return;
  if (typeof v !== kind) issues.push(`${path}.${key} must be ${kind}, got ${v === null ? "null" : typeof v}`);
}

function validateSnapshot(value: unknown): asserts value is DashboardSnapshot {
  const issues: Issues = [];
  if (!expectObject(value, "root", issues)) throw new SchemaError("root", issues.join("; "));
  const root = value;
  expectField(root, "status", "string", "root", issues);
  expectField(root, "generated_at_utc", "string", "root", issues);

  if (!("kpis" in root)) {
    issues.push("root.kpis is required");
  } else if (expectObject(root.kpis, "root.kpis", issues)) {
    const kpis = root.kpis;
    for (const numField of [
      "open_records",
      "settled_records",
      "tracked_only_records",
      "duplicate_ignored_records",
      "asian_pick_count",
      "observation_count",
      "calibration_bucket_count",
      "strategy_sample_count",
    ]) {
      expectField(kpis, numField, "number", "root.kpis", issues);
    }
    expectField(kpis, "live_calibration_active", "boolean", "root.kpis", issues);
  }

  if (!("prediction_kpis" in root)) {
    issues.push("root.prediction_kpis is required");
  } else if (expectObject(root.prediction_kpis, "root.prediction_kpis", issues)) {
    const k = root.prediction_kpis;
    for (const numField of ["total_count", "recommended_count", "observation_count", "open_count", "settled_count", "hit_count", "miss_count"]) {
      expectField(k, numField, "number", "root.prediction_kpis", issues);
    }
    expectField(k, "hit_rate", "number", "root.prediction_kpis", issues, { nullable: true });
    expectField(k, "roi", "number", "root.prediction_kpis", issues, { nullable: true });
  }

  // Normalized sub-shapes (added by backend dashboard_contract.normalize_dashboard_snapshot)
  if ("auto_learning_state" in root && root.auto_learning_state !== undefined) {
    if (!expectObject(root.auto_learning_state, "root.auto_learning_state", issues)) {
      // expectObject already pushed an issue
    }
  }

  if ("buckets" in root && root.buckets !== undefined) {
    if (!Array.isArray(root.buckets)) {
      issues.push("root.buckets must be an array");
    } else {
      root.buckets.forEach((b, i) => {
        if (!b || typeof b !== "object") {
          issues.push(`root.buckets[${i}] must be an object`);
          return;
        }
        const bucket = b as Record<string, unknown>;
        if (typeof bucket.band !== "string" || !bucket.band) {
          issues.push(`root.buckets[${i}].band must be a non-empty string`);
        }
      });
    }
  }

  if (issues.length) throw new SchemaError("root", issues.join("; "));
}

function validateMatchDetail(value: unknown): asserts value is DashboardMatchDetail {
  const issues: Issues = [];
  if (!expectObject(value, "root", issues)) throw new SchemaError("root", issues.join("; "));
  const root = value;
  expectField(root, "status", "string", "root", issues);
  if (!("record" in root)) {
    issues.push("root.record is required");
  } else if (expectObject(root.record, "root.record", issues)) {
    expectField(root.record, "ledger_id", "string", "root.record", issues);
  }
  if (issues.length) throw new SchemaError("root", issues.join("; "));
}

async function readExcerpt(response: Response): Promise<string> {
  try {
    const text = await response.text();
    return text.slice(0, 200);
  } catch {
    return "";
  }
}

async function httpJson<T>(
  url: string,
  validator: (v: unknown) => asserts v is T,
  opts: { signal?: AbortSignal; notFoundMessage?: string } = {}
): Promise<T> {
  const response = await fetch(url, { cache: "no-store", signal: opts.signal });
  if (!response.ok) {
    const excerpt = await readExcerpt(response);
    if (response.status === 404 && opts.notFoundMessage) {
      throw new HttpError(404, opts.notFoundMessage, excerpt);
    }
    throw new HttpError(response.status, `HTTP ${response.status}`, excerpt);
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch (err) {
    throw new HttpError(response.status, `invalid JSON body: ${(err as Error).message}`);
  }
  validator(body);
  return body;
}

export function fetchDashboardSnapshot(opts: { signal?: AbortSignal } = {}): Promise<DashboardSnapshot> {
  return httpJson<DashboardSnapshot>("/api/dashboard", validateSnapshot, opts);
}

export function fetchMatchDetail(ledgerId: string, opts: { signal?: AbortSignal } = {}): Promise<DashboardMatchDetail> {
  return httpJson<DashboardMatchDetail>(
    `/api/dashboard/match/${encodeURIComponent(ledgerId)}`,
    validateMatchDetail,
    { ...opts, notFoundMessage: "当前台账中不存在这场预测" }
  );
}

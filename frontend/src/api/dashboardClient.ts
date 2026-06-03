import type { DashboardMatchDetail, DashboardSnapshot, LarkPredictionSendResult, ValidationJob } from "../types";

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

function expectOptionalField(obj: Record<string, unknown>, key: string, kind: "string" | "number" | "boolean", path: string, issues: Issues, opts: { nullable?: boolean } = {}) {
  if (!(key in obj)) return;
  const v = obj[key];
  if (opts.nullable && v === null) return;
  if (typeof v !== kind) issues.push(`${path}.${key} must be ${kind}, got ${v === null ? "null" : typeof v}`);
}

function expectValidationLeagueResults(value: unknown, path: string, issues: Issues): void {
  if (!Array.isArray(value)) {
    issues.push(`${path} must be an array`);
    return;
  }
  value.forEach((entry, index) => {
    const itemPath = `${path}[${index}]`;
    if (!expectObject(entry, itemPath, issues)) return;
    expectField(entry, "division", "string", itemPath, issues);
    expectField(entry, "status", "string", itemPath, issues);
    expectOptionalField(entry, "league", "string", itemPath, issues, { nullable: true });
    expectOptionalField(entry, "cache_key", "string", itemPath, issues, { nullable: true });
    expectOptionalField(entry, "cache_hit", "boolean", itemPath, issues);
    expectOptionalField(entry, "error", "string", itemPath, issues, { nullable: true });
    expectOptionalField(entry, "started_at_utc", "string", itemPath, issues, { nullable: true });
    expectOptionalField(entry, "updated_at_utc", "string", itemPath, issues, { nullable: true });
    expectOptionalField(entry, "finished_at_utc", "string", itemPath, issues, { nullable: true });
    if ("runtime" in entry && entry.runtime !== undefined && entry.runtime !== null) {
      if (expectObject(entry.runtime, `${itemPath}.runtime`, issues)) {
        expectOptionalField(entry.runtime, "state", "string", `${itemPath}.runtime`, issues, { nullable: true });
        expectOptionalField(entry.runtime, "is_running", "boolean", `${itemPath}.runtime`, issues, { nullable: true });
        for (const key of ["run_seconds", "updated_age_seconds", "heartbeat_age_seconds"]) {
          expectOptionalField(entry.runtime, key, "number", `${itemPath}.runtime`, issues, { nullable: true });
        }
        for (const key of ["started_at_utc", "updated_at_utc", "finished_at_utc"]) {
          expectOptionalField(entry.runtime, key, "string", `${itemPath}.runtime`, issues, { nullable: true });
        }
      }
    }
    if ("result" in entry && entry.result !== undefined) {
      expectObject(entry.result, `${itemPath}.result`, issues);
    }
  });
}

function expectValidationFailureSummary(value: unknown, path: string, issues: Issues): void {
  if (!expectObject(value, path, issues)) return;
  expectField(value, "failed_count", "number", path, issues);
  expectField(value, "recoverable", "boolean", path, issues);
  expectField(value, "recoverable_count", "number", path, issues);
  expectOptionalField(value, "latest_error", "string", path, issues, { nullable: true });
  expectField(value, "category", "string", path, issues);
  expectField(value, "stage", "string", path, issues);
  expectField(value, "severity", "string", path, issues);
  expectField(value, "title", "string", path, issues);
  expectField(value, "detail", "string", path, issues);
  expectField(value, "next_action", "string", path, issues);
  if (!Array.isArray(value.failed_leagues)) {
    issues.push(`${path}.failed_leagues must be an array`);
    return;
  }
  value.failed_leagues.forEach((entry, index) => {
    const itemPath = `${path}.failed_leagues[${index}]`;
    if (!expectObject(entry, itemPath, issues)) return;
    expectOptionalField(entry, "division", "string", itemPath, issues, { nullable: true });
    expectOptionalField(entry, "league", "string", itemPath, issues, { nullable: true });
    expectOptionalField(entry, "status", "string", itemPath, issues, { nullable: true });
    expectOptionalField(entry, "error", "string", itemPath, issues, { nullable: true });
  });
}

function expectValidationJobEvents(value: unknown, path: string, issues: Issues): void {
  if (!Array.isArray(value)) {
    issues.push(`${path} must be an array`);
    return;
  }
  value.forEach((entry, index) => {
    const itemPath = `${path}[${index}]`;
    if (!expectObject(entry, itemPath, issues)) return;
    expectOptionalField(entry, "id", "number", itemPath, issues, { nullable: true });
    expectField(entry, "event_type", "string", itemPath, issues);
    expectField(entry, "severity", "string", itemPath, issues);
    expectField(entry, "message", "string", itemPath, issues);
    expectOptionalField(entry, "division", "string", itemPath, issues, { nullable: true });
    expectOptionalField(entry, "runner_id", "string", itemPath, issues, { nullable: true });
    expectOptionalField(entry, "created_at_utc", "string", itemPath, issues, { nullable: true });
    if ("metadata" in entry && entry.metadata !== undefined) {
      expectObject(entry.metadata, `${itemPath}.metadata`, issues);
    }
  });
}

function expectValidationExecutionHealth(value: unknown, path: string, issues: Issues): void {
  if (!expectObject(value, path, issues)) return;
  expectField(value, "state", "string", path, issues);
  expectField(value, "severity", "string", path, issues);
  expectField(value, "title", "string", path, issues);
  expectField(value, "detail", "string", path, issues);
  expectField(value, "next_action", "string", path, issues);
  expectField(value, "is_stale", "boolean", path, issues);
  for (const key of ["age_seconds", "queue_wait_seconds", "run_seconds", "updated_age_seconds", "heartbeat_age_seconds", "stale_after_seconds"]) {
    expectOptionalField(value, key, "number", path, issues, { nullable: true });
  }
}

function expectOddsSourceStatus(value: unknown, path: string, issues: Issues): void {
  if (!expectObject(value, path, issues)) return;
  expectField(value, "status", "string", path, issues);
  if ("closure" in value && value.closure !== undefined && value.closure !== null) {
    if (expectObject(value.closure, `${path}.closure`, issues)) {
      expectOptionalField(value.closure, "active_source", "string", `${path}.closure`, issues, { nullable: true });
      expectField(value.closure, "production_ready", "boolean", `${path}.closure`, issues);
      expectField(value.closure, "reason", "string", `${path}.closure`, issues);
      expectField(value.closure, "checked_at_utc", "string", `${path}.closure`, issues);
      expectField(value.closure, "fresh_after_hours", "number", `${path}.closure`, issues);
      if (!Array.isArray(value.closure.ordered_sources)) {
        issues.push(`${path}.closure.ordered_sources must be an array`);
      } else {
        value.closure.ordered_sources.forEach((entry, index) => {
          const entryPath = `${path}.closure.ordered_sources[${index}]`;
          if (!expectObject(entry, entryPath, issues)) return;
          expectField(entry, "source", "string", entryPath, issues);
          expectField(entry, "snapshot_count", "number", entryPath, issues);
          expectField(entry, "usable_for_analysis", "boolean", entryPath, issues);
          expectOptionalField(entry, "operational_status", "string", entryPath, issues, { nullable: true });
          expectOptionalField(entry, "freshness_status", "string", entryPath, issues, { nullable: true });
          expectOptionalField(entry, "latest_fetched_at_utc", "string", entryPath, issues, { nullable: true });
        });
      }
    }
  }
  if (!("sources" in value)) {
    issues.push(`${path}.sources is required`);
    return;
  }
  if (!expectObject(value.sources, `${path}.sources`, issues)) return;
  Object.entries(value.sources).forEach(([sourceKey, sourceValue]) => {
    const sourcePath = `${path}.sources.${sourceKey}`;
    if (!expectObject(sourceValue, sourcePath, issues)) return;
    expectField(sourceValue, "status", "string", sourcePath, issues);
    expectField(sourceValue, "snapshot_count", "number", sourcePath, issues);
    expectOptionalField(sourceValue, "role", "string", sourcePath, issues);
    expectOptionalField(sourceValue, "operational_status", "string", sourcePath, issues);
    expectOptionalField(sourceValue, "latest_fetched_at_utc", "string", sourcePath, issues, { nullable: true });
    expectOptionalField(sourceValue, "fresh_after_hours", "number", sourcePath, issues, { nullable: true });
    expectOptionalField(sourceValue, "freshness_status", "string", sourcePath, issues, { nullable: true });
    expectOptionalField(sourceValue, "age_hours", "number", sourcePath, issues, { nullable: true });
    expectOptionalField(sourceValue, "age_seconds", "number", sourcePath, issues, { nullable: true });
    expectOptionalField(sourceValue, "usable_for_analysis", "boolean", sourcePath, issues);
    expectOptionalField(sourceValue, "retryable_url_count", "number", sourcePath, issues);
    expectOptionalField(sourceValue, "queued_count", "number", sourcePath, issues);
    expectOptionalField(sourceValue, "running_count", "number", sourcePath, issues);
    expectOptionalField(sourceValue, "failed_count", "number", sourcePath, issues);
    expectOptionalField(sourceValue, "empty_count", "number", sourcePath, issues);
    expectOptionalField(sourceValue, "scraper_enabled", "boolean", sourcePath, issues);
    expectOptionalField(sourceValue, "auto_sync_enabled", "boolean", sourcePath, issues);
    expectOptionalField(sourceValue, "discovery_ready", "boolean", sourcePath, issues);
    expectOptionalField(sourceValue, "configured_discovery_url_count", "number", sourcePath, issues);
    expectOptionalField(sourceValue, "suggested_discovery_url_count", "number", sourcePath, issues);
    expectOptionalField(sourceValue, "effective_discovery_url_count", "number", sourcePath, issues);
    expectOptionalField(sourceValue, "open_target_count", "number", sourcePath, issues);
    expectOptionalField(sourceValue, "analysis_target_count", "number", sourcePath, issues);
    expectOptionalField(sourceValue, "discovery_target_count", "number", sourcePath, issues);
    expectOptionalField(sourceValue, "discovery_target_source", "string", sourcePath, issues);
    for (const urlField of ["discovery_urls", "suggested_discovery_urls", "effective_discovery_urls"]) {
      const urls = sourceValue[urlField];
      if (urls === undefined) continue;
      if (!Array.isArray(urls)) {
        issues.push(`${sourcePath}.${urlField} must be an array`);
      } else {
        urls.forEach((url, i) => {
          if (typeof url !== "string") issues.push(`${sourcePath}.${urlField}[${i}] must be string, got ${typeof url}`);
        });
      }
    }
    expectOptionalField(sourceValue, "last_error", "string", sourcePath, issues, { nullable: true });
    expectOptionalField(sourceValue, "next_action", "string", sourcePath, issues);
    if ("sync" in sourceValue && sourceValue.sync !== undefined && sourceValue.sync !== null) {
      if (expectObject(sourceValue.sync, `${sourcePath}.sync`, issues)) {
        expectOptionalField(sourceValue.sync, "latest_status", "string", `${sourcePath}.sync`, issues, { nullable: true });
        expectOptionalField(sourceValue.sync, "attempt_count", "number", `${sourcePath}.sync`, issues);
        expectOptionalField(sourceValue.sync, "snapshot_count", "number", `${sourcePath}.sync`, issues);
        expectOptionalField(sourceValue.sync, "latest_started_at_utc", "string", `${sourcePath}.sync`, issues, { nullable: true });
        expectOptionalField(sourceValue.sync, "latest_finished_at_utc", "string", `${sourcePath}.sync`, issues, { nullable: true });
        expectOptionalField(sourceValue.sync, "latest_error", "string", `${sourcePath}.sync`, issues, { nullable: true });
      }
    }
  });
}

function validateSnapshot(value: unknown): asserts value is DashboardSnapshot {
  const issues: Issues = [];
  if (!expectObject(value, "root", issues)) throw new SchemaError("root", issues.join("; "));
  const root = value;
  expectField(root, "status", "string", "root", issues);
  expectField(root, "generated_at_utc", "string", "root", issues);
  if ("policy" in root && root.policy !== undefined) {
    if (expectObject(root.policy, "root.policy", issues)) {
      expectField(root.policy, "read_only", "boolean", "root.policy", issues);
      expectField(root.policy, "no_search_inputs", "boolean", "root.policy", issues);
      expectOptionalField(root.policy, "background_enrichment_refresh", "boolean", "root.policy", issues);
      expectField(root.policy, "data_rule", "string", "root.policy", issues);
    }
  }

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

  if ("program_capabilities" in root && root.program_capabilities !== undefined) {
    if (expectObject(root.program_capabilities, "root.program_capabilities", issues)) {
      const matrix = root.program_capabilities;
      expectField(matrix, "status", "string", "root.program_capabilities", issues);
      expectField(matrix, "operating_mode", "string", "root.program_capabilities", issues);
      if (!("summary" in matrix)) {
        issues.push("root.program_capabilities.summary is required");
      } else if (expectObject(matrix.summary, "root.program_capabilities.summary", issues)) {
        for (const numField of ["total_count", "ready_count", "warning_count", "blocked_count"]) {
          expectField(matrix.summary, numField, "number", "root.program_capabilities.summary", issues);
        }
      }
      if (!Array.isArray(matrix.capabilities)) {
        issues.push("root.program_capabilities.capabilities must be an array");
      } else {
        matrix.capabilities.forEach((entry, i) => {
          if (!expectObject(entry, `root.program_capabilities.capabilities[${i}]`, issues)) return;
          expectField(entry, "key", "string", `root.program_capabilities.capabilities[${i}]`, issues);
          expectField(entry, "title", "string", `root.program_capabilities.capabilities[${i}]`, issues);
          expectField(entry, "status", "string", `root.program_capabilities.capabilities[${i}]`, issues);
          expectField(entry, "available", "boolean", `root.program_capabilities.capabilities[${i}]`, issues);
          expectField(entry, "detail", "string", `root.program_capabilities.capabilities[${i}]`, issues);
          expectOptionalField(entry, "current", "number", `root.program_capabilities.capabilities[${i}]`, issues, { nullable: true });
          expectOptionalField(entry, "target", "number", `root.program_capabilities.capabilities[${i}]`, issues, { nullable: true });
          expectOptionalField(entry, "ratio", "number", `root.program_capabilities.capabilities[${i}]`, issues, { nullable: true });
          expectOptionalField(entry, "next_action", "string", `root.program_capabilities.capabilities[${i}]`, issues);
        });
      }
    }
  }

  if ("task_queue" in root && root.task_queue !== undefined) {
    if (expectObject(root.task_queue, "root.task_queue", issues)) {
      expectField(root.task_queue, "backend", "string", "root.task_queue", issues);
      expectField(root.task_queue, "status", "string", "root.task_queue", issues);
      expectOptionalField(root.task_queue, "redis_reachable", "boolean", "root.task_queue", issues, { nullable: true });
      expectOptionalField(root.task_queue, "queue_name", "string", "root.task_queue", issues, { nullable: true });
      expectOptionalField(root.task_queue, "queued_jobs", "number", "root.task_queue", issues, { nullable: true });
      expectOptionalField(root.task_queue, "worker_healthy", "boolean", "root.task_queue", issues, { nullable: true });
      expectOptionalField(root.task_queue, "worker_health_ttl_seconds", "number", "root.task_queue", issues, { nullable: true });
      expectOptionalField(root.task_queue, "detail", "string", "root.task_queue", issues);
      expectOptionalField(root.task_queue, "validation_job_stale_after_seconds", "number", "root.task_queue", issues);
    }
  }

  if ("odds_source_status" in root && root.odds_source_status !== undefined) {
    expectOddsSourceStatus(root.odds_source_status, "root.odds_source_status", issues);
  }

  if ("dashboard_cache" in root && root.dashboard_cache !== undefined) {
    if (expectObject(root.dashboard_cache, "root.dashboard_cache", issues)) {
      expectOptionalField(root.dashboard_cache, "status", "string", "root.dashboard_cache", issues);
      expectOptionalField(root.dashboard_cache, "age_seconds", "number", "root.dashboard_cache", issues);
      expectOptionalField(root.dashboard_cache, "ttl_seconds", "number", "root.dashboard_cache", issues);
      expectOptionalField(root.dashboard_cache, "stale_seconds", "number", "root.dashboard_cache", issues);
    }
  }

  if ("model_failure_diagnostics" in root && root.model_failure_diagnostics !== undefined) {
    if (expectObject(root.model_failure_diagnostics, "root.model_failure_diagnostics", issues)) {
      const diagnostics = root.model_failure_diagnostics;
      expectField(diagnostics, "status", "string", "root.model_failure_diagnostics", issues);
      expectField(diagnostics, "severity", "string", "root.model_failure_diagnostics", issues);
      expectField(diagnostics, "title", "string", "root.model_failure_diagnostics", issues);
      expectField(diagnostics, "detail", "string", "root.model_failure_diagnostics", issues);
      if (!("summary" in diagnostics)) {
        issues.push("root.model_failure_diagnostics.summary is required");
      } else if (expectObject(diagnostics.summary, "root.model_failure_diagnostics.summary", issues)) {
        expectField(diagnostics.summary, "settled_count", "number", "root.model_failure_diagnostics.summary", issues);
        expectField(diagnostics.summary, "negative_driver_count", "number", "root.model_failure_diagnostics.summary", issues);
        expectOptionalField(diagnostics.summary, "roi", "number", "root.model_failure_diagnostics.summary", issues, { nullable: true });
        expectOptionalField(diagnostics.summary, "odds_coverage_ratio", "number", "root.model_failure_diagnostics.summary", issues, { nullable: true });
      }
      if (!Array.isArray(diagnostics.drivers)) {
        issues.push("root.model_failure_diagnostics.drivers must be an array");
      } else {
        diagnostics.drivers.forEach((driver, i) => {
          if (!expectObject(driver, `root.model_failure_diagnostics.drivers[${i}]`, issues)) return;
          expectField(driver, "category", "string", `root.model_failure_diagnostics.drivers[${i}]`, issues);
          expectField(driver, "key", "string", `root.model_failure_diagnostics.drivers[${i}]`, issues);
          expectField(driver, "title", "string", `root.model_failure_diagnostics.drivers[${i}]`, issues);
          expectField(driver, "sample_count", "number", `root.model_failure_diagnostics.drivers[${i}]`, issues);
          expectOptionalField(driver, "roi", "number", `root.model_failure_diagnostics.drivers[${i}]`, issues, { nullable: true });
          expectField(driver, "loss_units", "number", `root.model_failure_diagnostics.drivers[${i}]`, issues);
        });
      }
      if ("policy" in diagnostics && diagnostics.policy !== undefined) {
        if (expectObject(diagnostics.policy, "root.model_failure_diagnostics.policy", issues)) {
          expectField(diagnostics.policy, "formal_recommendation_enabled", "boolean", "root.model_failure_diagnostics.policy", issues);
          expectField(diagnostics.policy, "reason", "string", "root.model_failure_diagnostics.policy", issues);
          expectOptionalField(diagnostics.policy, "rule_count", "number", "root.model_failure_diagnostics.policy", issues);
          expectOptionalField(diagnostics.policy, "blocked_rule_count", "number", "root.model_failure_diagnostics.policy", issues);
          if ("rules" in diagnostics.policy && diagnostics.policy.rules !== undefined) {
            if (!Array.isArray(diagnostics.policy.rules)) {
              issues.push("root.model_failure_diagnostics.policy.rules must be an array");
            } else {
              diagnostics.policy.rules.forEach((rule, i) => {
                if (!expectObject(rule, `root.model_failure_diagnostics.policy.rules[${i}]`, issues)) return;
                expectField(rule, "key", "string", `root.model_failure_diagnostics.policy.rules[${i}]`, issues);
                expectField(rule, "type", "string", `root.model_failure_diagnostics.policy.rules[${i}]`, issues);
                expectField(rule, "status", "string", `root.model_failure_diagnostics.policy.rules[${i}]`, issues);
                expectField(rule, "title", "string", `root.model_failure_diagnostics.policy.rules[${i}]`, issues);
                expectField(rule, "detail", "string", `root.model_failure_diagnostics.policy.rules[${i}]`, issues);
                expectField(rule, "action", "string", `root.model_failure_diagnostics.policy.rules[${i}]`, issues);
                expectField(rule, "target", "string", `root.model_failure_diagnostics.policy.rules[${i}]`, issues);
                expectField(rule, "target_key", "string", `root.model_failure_diagnostics.policy.rules[${i}]`, issues);
                expectField(rule, "sample_count", "number", `root.model_failure_diagnostics.policy.rules[${i}]`, issues);
                expectOptionalField(rule, "roi", "number", `root.model_failure_diagnostics.policy.rules[${i}]`, issues, { nullable: true });
                expectField(rule, "loss_units", "number", `root.model_failure_diagnostics.policy.rules[${i}]`, issues);
              });
            }
          }
        }
      }
    }
  }

  if ("validation_job" in root && root.validation_job !== undefined && root.validation_job !== null) {
    if (expectObject(root.validation_job, "root.validation_job", issues)) {
      const job = root.validation_job;
      expectField(job, "job_id", "string", "root.validation_job", issues);
      expectField(job, "status", "string", "root.validation_job", issues);
      expectOptionalField(job, "current_runner_id", "string", "root.validation_job", issues, { nullable: true });
      expectOptionalField(job, "attempt_count", "number", "root.validation_job", issues);
      expectOptionalField(job, "retry_count", "number", "root.validation_job", issues);
      expectOptionalField(job, "last_claim_reason", "string", "root.validation_job", issues, { nullable: true });
      expectOptionalField(job, "last_retry_at_utc", "string", "root.validation_job", issues, { nullable: true });
      expectOptionalField(job, "runner_heartbeat_at_utc", "string", "root.validation_job", issues, { nullable: true });
      expectOptionalField(job, "recovered_at_utc", "string", "root.validation_job", issues, { nullable: true });
      if ("failure_summary" in job && job.failure_summary !== undefined && job.failure_summary !== null) {
        expectValidationFailureSummary(job.failure_summary, "root.validation_job.failure_summary", issues);
      }
      if ("execution_health" in job && job.execution_health !== undefined && job.execution_health !== null) {
        expectValidationExecutionHealth(job.execution_health, "root.validation_job.execution_health", issues);
      }
      expectOptionalField(job, "queue_backend", "string", "root.validation_job", issues, { nullable: true });
      expectOptionalField(job, "queue_job_id", "string", "root.validation_job", issues, { nullable: true });
      expectOptionalField(job, "queued_at_utc", "string", "root.validation_job", issues, { nullable: true });
      expectOptionalField(job, "queue_status_message", "string", "root.validation_job", issues, { nullable: true });
      if (!("progress" in job)) {
        issues.push("root.validation_job.progress is required");
      } else if (expectObject(job.progress, "root.validation_job.progress", issues)) {
        for (const numField of ["total_leagues", "completed_leagues", "failed_leagues", "running_leagues", "pending_leagues", "progress_ratio"]) {
          expectField(job.progress, numField, "number", "root.validation_job.progress", issues);
        }
        expectOptionalField(job.progress, "cancelled_leagues", "number", "root.validation_job.progress", issues);
        expectOptionalField(job.progress, "processed_leagues", "number", "root.validation_job.progress", issues);
        expectOptionalField(job.progress, "success_ratio", "number", "root.validation_job.progress", issues);
      }
      expectValidationLeagueResults(job.league_results, "root.validation_job.league_results", issues);
      expectValidationJobEvents(job.events, "root.validation_job.events", issues);
    }
  }

  if (issues.length) throw new SchemaError("root", issues.join("; "));
}

function validateValidationJob(value: unknown): asserts value is ValidationJob {
  const issues: Issues = [];
  if (!expectObject(value, "root", issues)) throw new SchemaError("root", issues.join("; "));
  const root = value;
  expectField(root, "job_id", "string", "root", issues);
  expectField(root, "status", "string", "root", issues);
  expectOptionalField(root, "current_runner_id", "string", "root", issues, { nullable: true });
  expectOptionalField(root, "attempt_count", "number", "root", issues);
  expectOptionalField(root, "retry_count", "number", "root", issues);
  expectOptionalField(root, "last_claim_reason", "string", "root", issues, { nullable: true });
  expectOptionalField(root, "last_retry_at_utc", "string", "root", issues, { nullable: true });
  expectOptionalField(root, "runner_heartbeat_at_utc", "string", "root", issues, { nullable: true });
  expectOptionalField(root, "recovered_at_utc", "string", "root", issues, { nullable: true });
  expectOptionalField(root, "queue_backend", "string", "root", issues, { nullable: true });
  expectOptionalField(root, "queue_job_id", "string", "root", issues, { nullable: true });
  expectOptionalField(root, "queued_at_utc", "string", "root", issues, { nullable: true });
  expectOptionalField(root, "queue_status_message", "string", "root", issues, { nullable: true });
  if ("failure_summary" in root && root.failure_summary !== undefined && root.failure_summary !== null) {
    expectValidationFailureSummary(root.failure_summary, "root.failure_summary", issues);
  }
  if ("execution_health" in root && root.execution_health !== undefined && root.execution_health !== null) {
    expectValidationExecutionHealth(root.execution_health, "root.execution_health", issues);
  }
  if (!("progress" in root)) {
    issues.push("root.progress is required");
  } else if (expectObject(root.progress, "root.progress", issues)) {
    for (const numField of ["total_leagues", "completed_leagues", "failed_leagues", "running_leagues", "pending_leagues", "progress_ratio"]) {
      expectField(root.progress, numField, "number", "root.progress", issues);
    }
    expectOptionalField(root.progress, "cancelled_leagues", "number", "root.progress", issues);
    expectOptionalField(root.progress, "processed_leagues", "number", "root.progress", issues);
    expectOptionalField(root.progress, "success_ratio", "number", "root.progress", issues);
  }
  expectValidationLeagueResults(root.league_results, "root.league_results", issues);
  expectValidationJobEvents(root.events, "root.events", issues);
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
  opts: { signal?: AbortSignal; notFoundMessage?: string; method?: string; body?: unknown } = {}
): Promise<T> {
  const response = await fetch(url, {
    cache: "no-store",
    signal: opts.signal,
    method: opts.method ?? "GET",
    headers: opts.body === undefined ? undefined : { "Content-Type": "application/json" },
    body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
  });
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

function validateLarkPredictionSendResult(value: unknown): asserts value is LarkPredictionSendResult {
  const issues: Issues = [];
  if (!expectObject(value, "root", issues)) throw new SchemaError("root", issues.join("; "));
  const root = value;
  expectField(root, "status", "string", "root", issues);
  expectField(root, "tool", "string", "root", issues);
  expectField(root, "sent", "boolean", "root", issues);
  expectField(root, "channel", "string", "root", issues);
  expectField(root, "ledger_id", "string", "root", issues);
  expectOptionalField(root, "message_title", "string", "root", issues, { nullable: true });
  if ("policy" in root && root.policy !== undefined && root.policy !== null) {
    expectObject(root.policy, "root.policy", issues);
  }
  if ("lark_response" in root && root.lark_response !== undefined && root.lark_response !== null) {
    expectObject(root.lark_response, "root.lark_response", issues);
  }
  if (issues.length) throw new SchemaError("root", issues.join("; "));
}

export function fetchDashboardSnapshot(opts: { signal?: AbortSignal; forceRefresh?: boolean } = {}): Promise<DashboardSnapshot> {
  const { forceRefresh: _forceRefresh, ...requestOpts } = opts;
  return httpJson<DashboardSnapshot>(
    _forceRefresh ? "/api/dashboard?refresh=true" : "/api/dashboard",
    validateSnapshot,
    requestOpts,
  );
}

export function fetchMatchDetail(ledgerId: string, opts: { signal?: AbortSignal } = {}): Promise<DashboardMatchDetail> {
  return httpJson<DashboardMatchDetail>(
    `/api/dashboard/match/${encodeURIComponent(ledgerId)}`,
    validateMatchDetail,
    { ...opts, notFoundMessage: "当前台账中不存在这场预测" }
  );
}

export function sendPredictionToLark(
  ledgerId: string,
  opts: { signal?: AbortSignal } = {},
): Promise<LarkPredictionSendResult> {
  return httpJson<LarkPredictionSendResult>(
    `/api/dashboard/match/${encodeURIComponent(ledgerId)}/lark`,
    validateLarkPredictionSendResult,
    { ...opts, method: "POST" },
  );
}

export function cancelHoldoutValidationJob(jobId: string, opts: { signal?: AbortSignal } = {}): Promise<ValidationJob> {
  return httpJson<ValidationJob>(
    `/api/validation/holdout/jobs/${encodeURIComponent(jobId)}/cancel`,
    validateValidationJob,
    { ...opts, method: "POST" },
  );
}

export type StartHoldoutValidationJobRequest = {
  resume?: boolean;
  start?: boolean;
  divisions?: string[];
  training_seasons?: string[];
  validation_seasons?: string[];
  edge_thresholds?: number[];
  min_training_samples_options?: number[];
  max_samples?: number | null;
  min_selection_bets?: number;
  min_selection_evaluated?: number;
  min_validation_bets?: number;
  min_validation_evaluated?: number;
  historical_rho_min_samples?: number;
  use_cache?: boolean;
};

export function startHoldoutValidationJob(
  body: StartHoldoutValidationJobRequest = { resume: true, start: true },
  opts: { signal?: AbortSignal } = {},
): Promise<ValidationJob> {
  return httpJson<ValidationJob>(
    "/api/validation/holdout/jobs",
    validateValidationJob,
    { ...opts, method: "POST", body },
  );
}

export function retryHoldoutValidationJob(jobId: string, opts: { signal?: AbortSignal } = {}): Promise<ValidationJob> {
  return httpJson<ValidationJob>(
    `/api/validation/holdout/jobs/${encodeURIComponent(jobId)}/retry`,
    validateValidationJob,
    { ...opts, method: "POST" },
  );
}

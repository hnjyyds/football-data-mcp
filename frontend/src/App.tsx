import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "./components/shared/Icon";
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis
} from "recharts";
import {
  buildDashboardView, buildMatchDetailView, customerCopy, formatOdds, formatPercent,
  formatSignedPercent, marketLabel, reasonLabel, strategyStatusLabel
} from "./dashboardModel";
import { dashboardPath, matchDetailPath, parseDashboardRoute, type DashboardRoute } from "./appRouting";
import {
  cancelHoldoutValidationJob,
  fetchDashboardSnapshot,
  fetchMatchDetail,
  HttpError,
  retryHoldoutValidationJob,
  startHoldoutValidationJob,
  type StartHoldoutValidationJobRequest,
} from "./api/dashboardClient";
import { createPoller, withRetry } from "./api/poller";
import { reportError } from "./errorReporter";
import { useDarkMode } from "./useDarkMode";
import { formatBeijingShort, formatBeijingFull } from "./formatTime";
import type {
  DashboardMatchDetail, DashboardRecord, DashboardSectionKey, DashboardSnapshot,
  KpiCard, LearningEvent, PredictionLedgerRow, ProbabilityRow, ProgramCapabilityItem,
  TaskQueueHealth, ValidationJob, ValidationJobVerdict, ValidationLeagueResult
} from "./types";

// --- Layout components ---
import { TopBar } from "./components/layout/TopBar";
import { Sidebar, BottomNav } from "./components/layout/Sidebar";
// --- Dashboard components ---
import { KpiCards } from "./components/dashboard/KpiCards";
import { PickGrid } from "./components/dashboard/PickCard";
import { LedgerTable, type LedgerReasonFilter } from "./components/dashboard/LedgerTable";
import { SettlementFeed } from "./components/dashboard/SettlementFeed";
// --- System components ---
import { StrategyStateCard } from "./components/system/StrategyState";
import { HealthPanel } from "./components/system/HealthPanel";
import { ProductionGates } from "./components/system/ProductionGates";
import { ValidationJobActionBar } from "./components/system/ValidationJobActionBar";
// --- Shared components ---
import { Badge, toneVariant } from "./components/shared/Badge";
import { LoadingSpinner, SkeletonCard } from "./components/shared/LoadingSpinner";
import { ToastContainer, useToasts } from "./components/shared/Toast";
import { OddsChart } from "./components/detail/OddsChart";
import { TeamMatchup, TeamLogo } from "./components/shared/TeamLogo";
import { Panel, Metric } from "./components/shared/Panel";
import { ProfitabilityHeroBar } from "./components/dashboard/ProfitabilityHeroBar";
import { ProfitabilityPanel } from "./components/dashboard/ProfitabilityPanel";
import { HeatMap } from "./components/charts/HeatMap";
import { ReliabilityDiagram } from "./components/charts/ReliabilityDiagram";

type DashboardViewModel = ReturnType<typeof buildDashboardView>;

export const DASHBOARD_POLL_IDLE_MS = 30000;
export const DASHBOARD_POLL_ACTIVE_VALIDATION_MS = 5000;

type DashboardPollSnapshot = { validation_job?: { status?: string | null } | null } | null | undefined;

export function hasActiveValidationJob(snapshot: DashboardPollSnapshot): boolean {
  const status = String(snapshot?.validation_job?.status ?? "");
  return status === "pending" || status === "running";
}

export function dashboardPollIntervalMs(snapshot: DashboardPollSnapshot): number {
  return hasActiveValidationJob(snapshot) ? DASHBOARD_POLL_ACTIVE_VALIDATION_MS : DASHBOARD_POLL_IDLE_MS;
}

export function nextRefreshActivityCount(current: number, delta: 1 | -1): number {
  return Math.max(0, current + delta);
}

export function formatProductionGatesForDisplay(gates: DashboardViewModel["productionReadiness"]["gateRows"]) {
  return gates.map((gate) => {
    const title = gate.title && gate.title !== gate.label ? gate.title : "";
    const detail = [title, gate.detail].filter(Boolean).join("：");
    return {
      name: gate.label || gate.title || "上线检查",
      status: gate.statusText || "待确认",
      tone: gate.tone,
      detail,
      required: false,
    };
  });
}

export function formatRecommendationGateRowsForDisplay(
  releaseGate: DashboardViewModel["recommendationOpportunity"]["releaseGate"],
) {
  return (releaseGate?.gateRows ?? []).map((gate) => {
    const title = gate.title && gate.title !== gate.label ? gate.title : "";
    const detail = [title, gate.detail].filter(Boolean).join("：");
    return {
      key: gate.key,
      name: gate.label || gate.title || "发布闸门",
      status: gate.statusText || "待确认",
      tone: gate.tone,
      detail,
      progressText: gate.progressText || "—",
      width: gate.width || "0%",
    };
  });
}

export function formatSignalWorkbenchForDisplay(
  opportunity: DashboardViewModel["recommendationOpportunity"],
) {
  const candidateCount = opportunity.candidates?.length ?? 0;
  const blockerCount = opportunity.blockers?.length ?? 0;
  const counterSignalCount = opportunity.counterSignal?.candidates?.length ?? 0;
  const headline = candidateCount > 0
    ? "候选池有可跟踪信号"
    : blockerCount > 0
      ? "暂无候选，先看阻断原因"
      : counterSignalCount > 0
        ? "仅有反向校准观察"
        : "持续监控，当前没有可跟踪信号";
  return {
    candidateCount,
    blockerCount,
    counterSignalCount,
    headline,
    badge: `${candidateCount} 候选 · ${blockerCount} 阻断`,
    monitoringText: candidateCount === 0 && blockerCount === 0 && counterSignalCount === 0
      ? "链路正常监控中：没有候选或阻断不代表任务停止，台账仍会接收后续赔率、赛果和复算结果。"
      : "候选、阻断和反向观察会同步进入台账筛选，方便从发布闸门追到具体样本。",
    emptyCandidateText: candidateCount > 0
      ? "点击候选查看详情。"
      : blockerCount > 0
        ? "当前没有过线候选，优先处理右侧阻断原因。"
        : counterSignalCount > 0
          ? "当前没有正向候选，先把反向观察留在复盘样本里。"
          : "当前没有达到概率、边际和赔率门槛的候选；系统仍在采样、回测和等待盘口更新。",
    emptyBlockerText: blockerCount > 0
      ? "点击阻断分组筛选台账。"
      : candidateCount > 0
        ? "当前候选没有命中主要阻断分组，可以继续查看发布闸门。"
        : "当前没有命中主要阻断分组，这代表漏斗没有拦截到可归因样本，不是任务停止。",
    emptyCounterSignalText: counterSignalCount > 0 ? "反向样本用于校准风险。" : "当前没有反向校准观察。",
  };
}

export function formatTaskQueueForDisplay(queue: TaskQueueHealth | null | undefined) {
  const backend = String(queue?.backend || "thread");
  const status = String(queue?.status || (backend === "thread" ? "ok" : "degraded"));
  const isArq = backend === "arq";
  const redisReachable = queue?.redis_reachable ?? null;
  const workerHealthy = queue?.worker_healthy ?? null;
  const queuedJobs = queue?.queued_jobs ?? null;
  const tone: KpiCard["tone"] = status === "ok"
    ? "good"
    : status === "error"
      ? "bad"
      : "caution";
  const redisText = isArq
    ? redisReachable === false
      ? "Redis 不可达"
      : queue?.redis_host
        ? `${queue.redis_host}:${queue.redis_port ?? 6379} / DB ${queue.redis_database ?? 0}`
        : "Redis 已配置"
    : "未使用 Redis";
  const workerText = isArq
    ? workerHealthy === true
      ? typeof queue?.worker_health_ttl_seconds === "number" && queue.worker_health_ttl_seconds > 0
        ? `worker 在线 · 心跳剩余 ${secondsText(queue.worker_health_ttl_seconds)}`
        : "worker 在线"
      : workerHealthy === false
        ? typeof queue?.worker_health_ttl_seconds === "number" && queue.worker_health_ttl_seconds === -1
          ? "worker 未确认 · 心跳无过期时间"
          : "worker 未确认"
        : "worker 状态待确认"
    : "本进程线程执行";
  const queuedJobsText = typeof queuedJobs === "number"
    ? `${queuedJobs} 个任务`
    : "暂无队列数据";
  const timeoutMinutes = typeof queue?.job_timeout_seconds === "number"
    ? Math.max(1, Math.round(queue.job_timeout_seconds / 60))
    : null;
  const staleRecoveryMinutes = typeof queue?.validation_job_stale_after_seconds === "number"
    ? Math.max(1, Math.round(queue.validation_job_stale_after_seconds / 60))
    : null;
  const concurrencyText = isArq
    ? `并发 ${queue?.max_jobs ?? "—"} · 超时 ${timeoutMinutes ? `${timeoutMinutes} 分钟` : "—"} · 恢复 ${staleRecoveryMinutes ? `${staleRecoveryMinutes} 分钟` : "—"}`
    : "随 API 进程生命周期运行";
  const badge = isArq
    ? status === "ok"
      ? "ARQ 正常"
      : status === "error"
        ? "ARQ 异常"
        : "ARQ 需关注"
    : "线程模式";
  const nextAction = !isArq
    ? "当前使用线程兜底模式；长任务量变大后建议切换到 ARQ。"
    : redisReachable === false
      ? "Redis 不可达，后台验证无法可靠入队，请先恢复 Redis。"
      : workerHealthy === false
        ? "Redis 可达但 worker 未确认，请优先恢复 worker，否则任务会积压。"
        : "后台验证、续跑和重试会进入 Redis 队列，由 worker 异步执行。";

  return {
    badge,
    tone,
    backendText: isArq ? "ARQ 异步队列" : "本进程线程",
    redisText,
    workerText,
    queuedJobsText,
    concurrencyText,
    detail: queue?.detail || "后台任务队列状态待确认。",
    nextAction,
  };
}

function secondsText(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  const rounded = Math.max(0, Math.round(value));
  if (rounded < 60) return `${rounded} 秒`;
  const minutes = Math.floor(rounded / 60);
  const seconds = rounded % 60;
  return seconds > 0 ? `${minutes} 分 ${seconds} 秒` : `${minutes} 分钟`;
}

export function formatDashboardCacheForDisplay(cache: DashboardSnapshot["dashboard_cache"] | null | undefined) {
  const status = String(cache?.status || "");
  const ageText = typeof cache?.age_seconds === "number" ? `${secondsText(cache.age_seconds)}前生成` : "—";
  const ttlText = typeof cache?.ttl_seconds === "number" || typeof cache?.stale_seconds === "number"
    ? `新鲜期 ${secondsText(cache?.ttl_seconds)} · 后台保底 ${secondsText(cache?.stale_seconds)}`
    : "缓存窗口待确认";
  if (status === "stale_refreshing") {
    return {
      badge: "后台刷新中",
      tone: "caution" as KpiCard["tone"],
      statusText: "先展示旧快照，同时后台刷新",
      ageText,
      ttlText,
      detail: "看板读取走短缓存，过期后仍会先返回可用旧快照，避免页面等待慢查询。",
      nextAction: "页面不是卡住：当前先返回旧快照，刷新完成后下一次轮询会自动换成新快照。",
    };
  }
  if (status === "fresh" || status === "refreshed") {
    return {
      badge: status === "refreshed" ? "已强制刷新" : "缓存命中",
      tone: "good" as KpiCard["tone"],
      statusText: status === "refreshed" ? "刚刚强制生成新快照" : "直接使用新鲜快照",
      ageText,
      ttlText,
      detail: "看板读取走短缓存，避免每次切页都重新扫描数据库和模型指标。",
      nextAction: "需要立刻复算时使用刷新动作；普通浏览会复用缓存以保持页面响应。",
    };
  }
  return {
    badge: "缓存待确认",
    tone: "neutral" as KpiCard["tone"],
    statusText: "等待缓存状态",
    ageText: "—",
    ttlText: "缓存窗口待确认",
    detail: "后端会在返回看板时附带缓存状态，用来解释页面是新快照、旧快照还是后台刷新中。",
    nextAction: "如果长期缺少缓存状态，需要检查 /api/dashboard 契约是否被旧服务覆盖。",
  };
}

function validationLeagueName(item: { league?: string | null; division?: string | null }): string {
  return item.league || item.division || "未知联赛";
}

function shortLeagueList(names: string[]): string {
  if (names.length === 0) return "无";
  const head = names.slice(0, 4).join("、");
  return names.length > 4 ? `${head} 等 ${names.length} 个` : head;
}

function validationClaimReasonText(reason: string | null | undefined): string {
  if (reason === "claimed") return "worker 已接管";
  if (reason === "recovered_stale_runner") return "已从断联 worker 接管续跑";
  if (reason === "already_running") return "已有 worker 正在执行";
  if (reason === "completed") return "任务已完成";
  if (reason === "cancelled") return "任务已取消";
  return "等待 worker 接管";
}

function validationFailureSummaryText(job: ValidationJob): string {
  const summary = job.failure_summary;
  if (!summary) return "暂无失败摘要";
  const nextAction = summary.next_action ? ` · ${summary.next_action}` : "";
  if (summary.failed_count > 0) {
    const names = summary.failed_leagues
      .map((item) => item.league || item.division || "未知联赛")
      .filter(Boolean);
    const latestError = summary.latest_error ? ` · ${summary.latest_error}` : "";
    return `${summary.title || "失败诊断"}：${shortLeagueList(names)}${latestError}${nextAction}`;
  }
  if (summary.latest_error) return `${summary.title || "失败诊断"} · ${summary.latest_error}${nextAction}`;
  if (summary.recoverable_count > 0) return `${summary.recoverable_count} 个联赛等待执行或可续跑`;
  return "暂无失败摘要";
}

function validationEventTone(severity: string | null | undefined): KpiCard["tone"] {
  if (severity === "error") return "bad";
  if (severity === "warning") return "caution";
  return "neutral";
}

function validationEventTitle(event: ValidationJob["events"][number]): string {
  const division = event.division || "";
  const type = event.event_type;
  if (type === "job_created") return "创建验证任务";
  if (type === "job_queued") return "任务入队";
  if (type === "job_claimed") return "Worker 接管";
  if (type === "stale_runner_recovered") return "接管断联任务";
  if (type === "job_retry_requested") return "请求重试";
  if (type === "job_completed") return "任务完成";
  if (type === "job_failed") return "任务失败";
  if (type === "job_cancelled") return "任务取消";
  if (type === "league_started") return `${division || "联赛"} 开始验证`;
  if (type === "league_succeeded") return `${division || "联赛"} 验证完成`;
  if (type === "league_failed") return `${division || "联赛"} 验证失败`;
  if (type === "league_cancelled") return `${division || "联赛"} 已取消`;
  if (type === "league_skipped") return `${division || "联赛"} 已跳过`;
  return "执行事件";
}

export function formatValidationJobTimeline(job: ValidationJob) {
  const events = Array.isArray(job.events) ? job.events : [];
  const rows = events.slice(-8).reverse().map((event) => {
    const runnerText = event.runner_id ? `runner ${event.runner_id.slice(0, 8)}` : "";
    const divisionText = event.division ? `联赛 ${event.division}` : "";
    const detailParts = [divisionText, runnerText].filter(Boolean);
    return {
      key: `${event.id ?? event.created_at_utc ?? event.event_type}-${event.event_type}`,
      title: validationEventTitle(event),
      message: event.message || "事件详情待确认",
      timeText: event.created_at_utc ? formatBeijingFull(event.created_at_utc) : "时间待确认",
      detailText: detailParts.length > 0 ? detailParts.join(" · ") : "任务级事件",
      tone: validationEventTone(event.severity),
    };
  });
  return {
    badge: events.length > 0 ? `${events.length} 条事件` : "暂无事件",
    rows,
    emptyText: "暂无执行事件；新任务入队后会自动记录关键步骤。",
  };
}

export function formatValidationJobRunSummary(job: ValidationJob) {
  const progress = job.progress;
  const total = progress.total_leagues || job.league_results.length || job.divisions.length || 0;
  const completed = progress.completed_leagues ?? 0;
  const failed = progress.failed_leagues ?? 0;
  const cancelled = progress.cancelled_leagues ?? 0;
  const processed = progress.processed_leagues ?? completed + failed + cancelled;
  const ratio = typeof progress.progress_ratio === "number" ? progress.progress_ratio : total > 0 ? processed / total : 0;
  const cacheHits = job.league_results.filter((item) => item.cache_hit).length;
  const runningNames = job.league_results
    .filter((item) => item.status === "running")
    .map(validationLeagueName);
  const resumableNames = job.league_results
    .filter((item) => ["failed", "cancelled", "pending", "skipped"].includes(String(item.status)))
    .map(validationLeagueName);
  const status = String(job.status || "");
  const isCompleted = status === "completed";
  const isFailed = status === "failed";
  const isCancelled = status === "cancelled";
  const isTerminal = isCompleted || isFailed || isCancelled;
  const tone: KpiCard["tone"] = status === "completed" && failed === 0
    ? "good"
    : status === "failed" || failed > 0
      ? "caution"
      : status === "cancelled"
        ? "caution"
        : "caution";
  const activeText = runningNames.length > 0
    ? `正在运行：${shortLeagueList(runningNames)}`
    : progress.pending_leagues > 0
      ? `等待执行：${progress.pending_leagues} 个联赛`
      : "当前没有运行中的联赛";
  const resumeText = resumableNames.length > 0
    ? `可从未成功联赛继续：${shortLeagueList(resumableNames)}`
    : "全部联赛已有结果；重跑会复用缓存并只补缺失部分。";
  const detail = resumableNames.length > 0 || runningNames.length > 0
    ? "验证任务没有卡住；成功联赛会保留结果，失败和待跑联赛可由继续/重试动作续跑。"
    : "验证任务已形成完整结果；缓存会避免重复计算已经成功的联赛。";
  const queueBackend = String(job.queue_backend || "").trim();
  const runningQueueBackendText = queueBackend === "arq"
    ? "ARQ worker 队列"
    : queueBackend === "thread"
      ? "本地后台线程"
      : queueBackend
        ? `${queueBackend} 队列`
        : "等待入队信息";
  const terminalQueueText = isCompleted ? "验证已完成" : isFailed ? "验证已失败" : "验证已取消";
  const queueBackendText = isTerminal ? terminalQueueText : runningQueueBackendText;
  const queuedText = isTerminal
    ? "无需等待队列"
    : job.queued_at_utc
      ? `${formatBeijingFull(job.queued_at_utc)} 入队`
      : "入队时间待确认";
  const queueText = `${queueBackendText} · ${queuedText}`;
  const queueDetail = isTerminal
    ? "任务已结束；队列只负责启动执行，不影响当前结论。"
    : job.queue_status_message || "后端尚未返回队列执行说明。";
  const queueJobText = job.queue_job_id || (isTerminal ? "无队列任务 id" : "队列任务 id 待确认");
  const health = job.execution_health;
  const healthText = health
    ? `${health.title}${health.detail ? ` · ${health.detail}` : ""}`
    : "执行健康状态待确认";
  const healthNextAction = health?.next_action || "等待后端返回执行健康诊断。";
  const attemptCount = typeof job.attempt_count === "number" && Number.isFinite(job.attempt_count) ? job.attempt_count : 0;
  const retryCount = typeof job.retry_count === "number" && Number.isFinite(job.retry_count) ? job.retry_count : 0;
  const claimText = validationClaimReasonText(job.last_claim_reason);
  const runnerText = isCompleted
    ? "执行已结束"
    : isFailed
      ? "执行已停止"
      : isCancelled
        ? "执行已取消"
        : job.current_runner_id
          ? `runner ${job.current_runner_id.slice(0, 12)}`
          : "runner 待接管";
  const terminalAttemptText = isCompleted
    ? (attemptCount > 0 ? `任务已完成 · 共执行 ${attemptCount} 次` : "任务已完成")
    : isFailed
      ? (attemptCount > 0 ? `任务失败 · 已尝试 ${attemptCount} 次` : "任务失败")
      : isCancelled
        ? "任务已取消"
        : "";
  const attemptText = isTerminal
    ? terminalAttemptText
    : attemptCount > 0
      ? `第 ${attemptCount} 次执行 · ${claimText}`
      : claimText;
  const heartbeatText = isTerminal
    ? "无需 worker 心跳"
    : job.runner_heartbeat_at_utc
      ? `最近心跳 ${formatBeijingFull(job.runner_heartbeat_at_utc)}`
      : job.recovered_at_utc
        ? `最近接管 ${formatBeijingFull(job.recovered_at_utc)}`
        : "worker 心跳待确认";
  const retryText = retryCount > 0
    ? `已重试 ${retryCount} 次${job.last_retry_at_utc ? ` · ${formatBeijingFull(job.last_retry_at_utc)}` : ""}`
    : "尚未触发重试";
  const failureText = validationFailureSummaryText(job);

  return {
    tone,
    headline: `已处理 ${processed}/${total} 联赛，成功 ${completed}，失败 ${failed}`,
    progressText: `${Math.round(Math.max(0, Math.min(ratio, 1)) * 100)}% 处理进度`,
    cacheText: `${cacheHits} 个联赛复用缓存`,
    activeText,
    resumeText,
    queueText,
    queueDetail,
    queueJobText,
    runnerText,
    healthText,
    healthNextAction,
    attemptText,
    heartbeatText,
    retryText,
    failureText,
    detail,
  };
}

function validationLeagueRunPriority(status: string | null | undefined): number {
  const order: Record<string, number> = {
    failed: 0,
    cancelled: 1,
    running: 2,
    pending: 3,
    skipped: 4,
    succeeded: 5,
  };
  return order[String(status || "")] ?? 6;
}

function signedFixed(value: number | null, digits: number): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}`;
}

function signedPercentText(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
}

function validationLeagueErrorText(status: string, error: string | null | undefined): string {
  const message = String(error || "").trim();
  if (message.includes("Previous validation runner exceeded heartbeat window")) {
    return "上次运行超过恢复窗口，已释放给队列续跑。";
  }
  if (message) return message;
  if (status === "failed") return "该联赛执行失败，但后端没有返回具体错误。";
  if (status === "cancelled") return "该联赛已取消，继续验证会从未成功联赛重跑。";
  return "";
}

function validationLeagueActionText(status: string, cacheHit: boolean): string {
  if (status === "failed") return "修复数据源或参数后点重试；已成功联赛会保留结果。";
  if (status === "cancelled") return "点继续验证可从该联赛重新执行。";
  if (status === "running") return "等待 worker 完成；超出恢复窗口后会自动释放续跑。";
  if (status === "pending") return "等待队列调度；无需人工处理。";
  if (status === "skipped") return "被样本或配置门槛跳过，先检查验证范围。";
  if (status === "succeeded" && cacheHit) return "已复用缓存，重跑时不会重复计算。";
  if (status === "succeeded") return "已完成，结果会进入汇总指标。";
  return "继续观察该联赛执行状态。";
}

function validationLeagueRuntimeText(item: ValidationLeagueResult): string {
  const runtime = objectRecord(item.runtime);
  const runSeconds = numericValue(runtime.run_seconds);
  const updatedAgeSeconds = numericValue(runtime.updated_age_seconds);
  const heartbeatAgeSeconds = numericValue(runtime.heartbeat_age_seconds);
  if (String(item.status || "") === "running") {
    const parts = [
      `已运行 ${secondsText(runSeconds)}`,
      `最近更新 ${secondsText(updatedAgeSeconds)}前`,
      `心跳 ${secondsText(heartbeatAgeSeconds)}前`,
    ];
    return parts.join(" · ");
  }
  if (runSeconds !== null && ["succeeded", "failed", "cancelled"].includes(String(item.status || ""))) {
    return `耗时 ${secondsText(runSeconds)}`;
  }
  return "运行时长待确认";
}

export function formatValidationLeagueRunDiagnostics(job: ValidationJob) {
  const rows = (job.league_results ?? []).map((item) => {
    const status = String(item.status || "pending");
    const result = objectRecord(item.result);
    const calibrated = objectRecord(result.calibrated_validation_result);
    const llDiff = validationLeagueLogLossDiff(result);
    const roi = validationResultMetric(calibrated, "roi");
    const cacheHit = Boolean(item.cache_hit);
    return {
      division: item.division,
      name: item.league || item.division || "未知联赛",
      status,
      statusText: validationJobStatusLabel(status),
      tone: validationStatusTone(status),
      cacheText: cacheHit ? "命中缓存" : "实时计算",
      logLossText: signedFixed(llDiff, 4),
      roiText: signedPercentText(roi),
      errorText: validationLeagueErrorText(status, item.error),
      actionText: validationLeagueActionText(status, cacheHit),
      runtimeText: validationLeagueRuntimeText(item),
      updatedAt: item.updated_at_utc ?? null,
      finishedAt: item.finished_at_utc ?? null,
    };
  }).sort((a, b) => {
    const priorityDiff = validationLeagueRunPriority(a.status) - validationLeagueRunPriority(b.status);
    if (priorityDiff !== 0) return priorityDiff;
    return a.name.localeCompare(b.name, "zh-CN");
  });

  const failedCount = rows.filter((row) => row.status === "failed").length;
  const runningCount = rows.filter((row) => row.status === "running").length;
  const pendingCount = rows.filter((row) => row.status === "pending").length;
  const cancelledCount = rows.filter((row) => row.status === "cancelled").length;
  const cacheHitCount = rows.filter((row) => row.cacheText === "命中缓存").length;
  const succeededCount = rows.filter((row) => row.status === "succeeded").length;
  const headline = failedCount > 0
    ? `${failedCount} 个联赛失败，优先查看错误原因`
    : runningCount > 0
      ? `${runningCount} 个联赛运行中，worker 正在处理`
      : pendingCount > 0
        ? `${pendingCount} 个联赛等待调度`
        : cancelledCount > 0
          ? `${cancelledCount} 个联赛已取消，可继续验证`
          : "所有联赛已有执行结果";
  const detail = failedCount > 0
    ? "失败联赛会排在最前，成功联赛和缓存结果不会被重复计算。"
    : runningCount > 0 || pendingCount > 0
      ? "运行、等待和恢复中的联赛会排在前面，方便判断任务是否真的卡住。"
      : "当前没有未完成联赛；可结合 Log Loss、ROI 和缓存命中判断验证质量。";

  return {
    headline,
    badge: `${failedCount} 失败 · ${runningCount} 运行 · ${pendingCount} 等待`,
    detail,
    counts: {
      failed: failedCount,
      running: runningCount,
      pending: pendingCount,
      cancelled: cancelledCount,
      succeeded: succeededCount,
      cacheHit: cacheHitCount,
    },
    rows,
  };
}

type MatchDetailViewModel = ReturnType<typeof buildMatchDetailView>;

type LineupPlayer = { number?: number | string | null; name?: string; position?: string };
type LineupSide = { formation?: string; starterCountText?: string; players?: LineupPlayer[] };

// ─── Utility helpers ─────────────────────────────────────────────────────────

function currentDashboardRoute(): DashboardRoute {
  return parseDashboardRoute(`${window.location.pathname}${window.location.search}`);
}

const localTime = formatBeijingShort;
const fullLocalTime = formatBeijingFull;

const QUICK_HOLDOUT_VALIDATION_REQUEST: StartHoldoutValidationJobRequest = {
  resume: false,
  start: true,
  divisions: ["D1"],
  training_seasons: ["2122"],
  validation_seasons: ["2223"],
  edge_thresholds: [0.03],
  min_training_samples_options: [20],
  max_samples: 25,
  min_selection_bets: 1,
  min_selection_evaluated: 1,
  min_validation_bets: 1,
  min_validation_evaluated: 1,
  historical_rho_min_samples: 1,
};

const MatchDetailPage = lazy(() => import("./pages/MatchDetailPage"));

function numericValue(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim()) { const p = Number(v); return Number.isFinite(p) ? p : null; }
  return null;
}

function boolValue(v: unknown): boolean {
  if (typeof v === "boolean") return v;
  if (typeof v === "string") return ["1","true","yes","on"].includes(v.trim().toLowerCase());
  return false;
}

function objectRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" && !Array.isArray(v) ? v as Record<string, unknown> : {};
}

function isAfterTime(a: unknown, b: unknown): boolean {
  const da = new Date(typeof a === "string" ? a : ""), db = new Date(typeof b === "string" ? b : "");
  if (Number.isNaN(da.getTime())) return false;
  if (Number.isNaN(db.getTime())) return true;
  return da.getTime() > db.getTime();
}

function latestTime(rows: PredictionLedgerRow[], key: "created_at_utc" | "settled_at_utc"): string | null {
  let latest: string | null = null, latestMs = Number.NEGATIVE_INFINITY;
  for (const row of rows) {
    const v = row[key]; if (!v) continue;
    const ms = new Date(v).getTime();
    if (!Number.isNaN(ms) && ms > latestMs) { latest = v; latestMs = ms; }
  }
  return latest;
}

function displayMatchup(v: string | null | undefined): string {
  return (v || "—").replace(/\s+vs\s+/gi, " 对 ");
}

function readableEventDetail(detail: string): string {
  return customerCopy(detail
    .replaceAll("asian_handicap", "亚盘").replaceAll("over_under", "大小球")
    .replaceAll("moneyline_1x2", "胜平负").replaceAll("collecting_samples", "样本收集中")
    .replaceAll("live_calibration_active", "实时校准已启用")
    .replaceAll("no_positive_edge", "无正向边际").replaceAll("core_market_missing", "核心盘口缺失")
    .replaceAll("calibrated_probability_below_threshold", "概率不足")
    .replaceAll("value_edge_below_threshold", "价值边际不足")
  );
}

function capabilityTone(status: ProgramCapabilityItem["status"] | null | undefined): KpiCard["tone"] {
  if (status === "ok" || status === "ready") return "good";
  if (status === "warning" || status === "learning" || status === "limited") return "caution";
  if (status === "blocked" || status === "missing" || status === "error") return "bad";
  return "neutral";
}

function capabilityStatusLabel(status: ProgramCapabilityItem["status"] | null | undefined): string {
  const labels: Record<string, string> = {
    ok: "可用",
    ready: "已就绪",
    warning: "学习中",
    learning: "学习中",
    limited: "受限",
    blocked: "阻塞",
    missing: "缺数据",
    error: "异常",
    info: "观察",
  };
  return labels[String(status || "")] ?? "未知";
}

function capabilityModeLabel(mode: string | null | undefined): string {
  if (mode === "production_ready") return "生产候选";
  if (mode === "paper_learning") return "纸面学习";
  return mode || "未知";
}

function capabilityNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  if (Number.isInteger(value)) return value.toLocaleString("zh-CN");
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

function capabilityProgress(item: ProgramCapabilityItem): number | null {
  if (typeof item.target !== "number" || item.target <= 0) return null;
  if (typeof item.ratio === "number" && Number.isFinite(item.ratio)) {
    return Math.max(0, Math.min(item.ratio, 1));
  }
  if (typeof item.current === "number" && Number.isFinite(item.current)) {
    return Math.max(0, Math.min(item.current / item.target, 1));
  }
  return null;
}

function capabilityGapText(item: ProgramCapabilityItem): string {
  if (typeof item.target !== "number" || typeof item.current !== "number") return "持续观察";
  const gap = Math.max(0, item.target - item.current);
  return gap > 0 ? `还差 ${capabilityNumber(gap)}` : "已达标";
}

function capabilityProgressText(item: ProgramCapabilityItem): string {
  if (typeof item.target === "number" && typeof item.current === "number") {
    return `${capabilityNumber(item.current)}/${capabilityNumber(item.target)}`;
  }
  if (typeof item.current === "number") return capabilityNumber(item.current);
  return "持续监控";
}

export function formatProgramCapabilityActionPlan(capabilities: ProgramCapabilityItem[]) {
  const actionable = capabilities
    .filter((item) => !["ok", "ready"].includes(String(item.status)))
    .sort((a, b) => {
      const rank = (item: ProgramCapabilityItem) => {
        const status = String(item.status || "");
        if (["blocked", "missing", "error"].includes(status)) return 0;
        if (["warning", "learning", "limited"].includes(status)) return 1;
        return 2;
      };
      const rankDiff = rank(a) - rank(b);
      if (rankDiff !== 0) return rankDiff;
      const aProgress = capabilityProgress(a) ?? 0;
      const bProgress = capabilityProgress(b) ?? 0;
      return aProgress - bProgress;
    });
  const blockedCount = actionable.filter((item) => ["blocked", "missing", "error"].includes(String(item.status))).length;
  const learningCount = actionable.filter((item) => ["warning", "learning", "limited"].includes(String(item.status))).length;

  return {
    headline: actionable.length > 0 ? `优先处理 ${actionable.length} 个产品短板` : "核心能力已就绪",
    badge: actionable.length > 0 ? `${blockedCount} 阻断 · ${learningCount} 学习` : "无阻断",
    items: actionable.slice(0, 3).map((item) => {
      const tone = capabilityTone(item.status);
      return {
        title: item.title,
        statusText: capabilityStatusLabel(item.status),
        tone,
        progressText: capabilityProgressText(item),
        gapText: capabilityGapText(item),
        nextAction: item.next_action || "继续观察当前能力状态。",
      };
    }),
  };
}

function validationJobStatusLabel(status: string | null | undefined): string {
  const labels: Record<string, string> = {
    pending: "等待中",
    running: "运行中",
    completed: "已完成",
    failed: "失败",
    cancelled: "已取消",
    succeeded: "完成",
    skipped: "跳过",
  };
  return labels[String(status || "")] ?? (status || "未知");
}

function validationStatusTone(status: string | null | undefined): KpiCard["tone"] {
  if (status === "completed" || status === "succeeded") return "good";
  if (status === "running" || status === "pending" || status === "skipped") return "caution";
  if (status === "failed" || status === "cancelled") return "bad";
  return "neutral";
}

export function validationVerdictTone(verdict: ValidationJobVerdict | null | undefined): KpiCard["tone"] {
  if (verdict?.tone === "good" || verdict?.tone === "bad" || verdict?.tone === "caution") {
    return verdict.tone;
  }
  if (verdict?.status === "watchlist_candidate") return "good";
  if (verdict?.status === "model_underperforms_market" || verdict?.status === "league_validation_failed") return "bad";
  if (verdict?.status) return "caution";
  return "neutral";
}

export function formatValidationMetricScope(summary: ValidationJob["result_summary"] | null | undefined) {
  const scope = objectRecord(summary?.metric_scope);
  const probabilityMarket = String(scope.probability_market || "");
  const marketLabelText = String(scope.probability_market_label || (probabilityMarket === "moneyline_1x2" ? "胜平负/1X2" : "概率指标"));
  const asianSpecific = boolValue(scope.asian_handicap_specific);
  const evaluatedCount = numericValue(summary?.evaluated_count) ?? 0;
  const betCount = numericValue(summary?.bet_count) ?? 0;
  const warning = String(scope.warning || "");

  if (asianSpecific) {
    return {
      tone: "good" as KpiCard["tone"],
      badge: "亚盘口径",
      title: "亚盘专属验证",
      detail: `当前 Holdout 指标针对亚盘样本，可用于评估 asian_handicap 的概率和收益稳定性。${warning ? ` ${warning}` : ""}`,
      sampleText: `${evaluatedCount} 场可评估 · ${betCount} 条下注样本`,
    };
  }

  return {
    tone: "caution" as KpiCard["tone"],
    badge: probabilityMarket === "moneyline_1x2" ? "1X2 口径" : "非亚盘口径",
    title: "不是亚盘专属验证",
    detail: `当前 Log Loss / Brier 是${marketLabelText}概率校验，不能证明亚盘模型已准确；亚盘仍要单独看 asian_handicap 结算样本、CLV 和盘口盈亏。${warning ? ` ${warning}` : ""}`,
    sampleText: `${evaluatedCount} 场可评估 · ${betCount} 条下注样本`,
  };
}

export function formatAsianHandicapValidation(summary: ValidationJob["result_summary"] | null | undefined) {
  const validation = objectRecord(summary?.asian_handicap_validation);
  const status = String(validation.status || "missing");
  const availableCount = numericValue(validation.available_count) ?? 0;
  const evaluatedCount = numericValue(validation.evaluated_count) ?? availableCount;
  const betCount = numericValue(validation.bet_count) ?? 0;
  const roi = numericValue(validation.roi);
  const profit = numericValue(validation.profit);
  const hitCount = numericValue(validation.hit_count) ?? 0;
  const pushCount = numericValue(validation.push_count) ?? 0;
  const lossCount = numericValue(validation.loss_count) ?? 0;
  const sampleGate = objectRecord(validation.sample_gate);
  const minBets = numericValue(sampleGate.min_bets_for_validation) ?? 50;
  const passed = boolValue(sampleGate.passed);

  if (status === "sample_ready" || passed) {
    return {
      tone: (roi !== null && roi > 0 ? "good" : roi !== null && roi < 0 ? "bad" : "caution") as KpiCard["tone"],
      badge: "亚盘样本可评估",
      title: "亚盘专属验证已形成",
      detail: `已用 asian_handicap 盘口独立结算，和 1X2 Log Loss/Brier 分开判断；继续观察 CLV 和分联赛稳定性。`,
      sampleText: `${betCount}/${evaluatedCount} 下注/可评估`,
      resultText: `命中 ${hitCount} · 走水 ${pushCount} · 亏损 ${lossCount}`,
      roiText: roi !== null ? formatSignedPercent(roi) : "—",
      profitText: profit !== null ? `${profit > 0 ? "+" : ""}${profit.toFixed(2)}` : "—",
    };
  }

  if (betCount > 0 || availableCount > 0) {
    return {
      tone: "caution" as KpiCard["tone"],
      badge: betCount > 0 ? "亚盘样本不足" : "亚盘待触发",
      title: betCount > 0 ? "亚盘验证样本不足" : "亚盘有盘口但未形成下注样本",
      detail: `当前亚盘验证还没达到 ${minBets} 条下注样本；只能用于诊断，不能证明 asian_handicap 模型已准确。`,
      sampleText: `${betCount}/${evaluatedCount} 下注/可评估`,
      resultText: `命中 ${hitCount} · 走水 ${pushCount} · 亏损 ${lossCount}`,
      roiText: roi !== null ? formatSignedPercent(roi) : "—",
      profitText: profit !== null ? `${profit > 0 ? "+" : ""}${profit.toFixed(2)}` : "—",
    };
  }

  return {
    tone: "bad" as KpiCard["tone"],
    badge: "亚盘样本缺失",
    title: "亚盘未形成验证样本",
    detail: "当前 Holdout 没有可独立结算的 asian_handicap 样本；必须补盘口、赔率和赛果闭环后才能评估亚盘准确性。",
    sampleText: "0/0 下注/可评估",
    resultText: "命中 0 · 走水 0 · 亏损 0",
    roiText: "—",
    profitText: "—",
  };
}

function validationResultMetric(result: Record<string, unknown> | null | undefined, key: string): number | null {
  const row = objectRecord(result);
  return numericValue(row[key]);
}

export function validationLeagueLogLossDiff(result: Record<string, unknown> | null | undefined): number | null {
  const row = objectRecord(result);
  const calibrated = objectRecord(row.calibrated_validation_result);
  const validation = objectRecord(row.validation_result);
  const explicit = numericValue(calibrated.log_loss_model_minus_market)
    ?? numericValue(calibrated.log_loss_diff)
    ?? numericValue(validation.log_loss_model_minus_market)
    ?? numericValue(validation.log_loss_diff);
  if (explicit !== null) return explicit;

  const model = numericValue(calibrated.model_log_loss_1x2)
    ?? numericValue(calibrated.log_loss_model)
    ?? numericValue(validation.model_log_loss_1x2)
    ?? numericValue(validation.log_loss_model);
  const market = numericValue(calibrated.market_log_loss_1x2)
    ?? numericValue(calibrated.log_loss_market)
    ?? numericValue(validation.market_log_loss_1x2)
    ?? numericValue(validation.log_loss_market);
  return model !== null && market !== null ? model - market : null;
}

function readableError(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

// ─── Overview section ────────────────────────────────────────────────────────

function OverviewSection({ snapshot, view, onSelectRecommendation }: {
  snapshot: DashboardSnapshot;
  view: DashboardViewModel;
  onSelectRecommendation: (r: DashboardRecord) => void;
}) {
  const accountability = view.predictionAccountability;
  const hitRate = snapshot.prediction_kpis.hit_rate;
  const roi = snapshot.prediction_kpis.roi;
  const accentTone = toneVariant(accountability.tone);

  // Top stat row data
  const topStats = [
    {
      label: "当前推荐",
      value: snapshot.kpis.asian_pick_count,
      caption: "可发布",
      tone: snapshot.kpis.asian_pick_count > 0 ? "good" : "neutral",
    },
    {
      label: "未结算",
      value: snapshot.prediction_kpis.open_count,
      caption: "等待结算",
      tone: "info",
    },
    {
      label: "命中率",
      value: hitRate != null ? `${Math.round(hitRate * 100)}%` : "—",
      caption: `${snapshot.prediction_kpis.settled_count ?? 0} 场已结算`,
      tone: hitRate != null && hitRate >= 0.55 ? "good" : "neutral",
    },
    {
      label: "ROI",
      value: roi != null ? `${roi >= 0 ? "+" : ""}${(roi * 100).toFixed(1)}%` : "—",
      caption: "纸面收益",
      tone: roi != null && roi > 0 ? "good" : roi != null && roi < 0 ? "bad" : "neutral",
    },
  ];

  return (
    <div className="flex flex-col gap-3">
      {/* Profitability hero bar - 最显眼位置 */}
      <ProfitabilityHeroBar forecast={snapshot.profitability_forecast} />

      {/* Status bar - 单行，紧凑 */}
      <div className="flex flex-col md:flex-row md:items-center gap-2 md:gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <Badge variant={accentTone}>{accountability.policyText}</Badge>
            <Badge variant={toneVariant(view.productionReadiness.tone)}>{view.productionReadiness.actionText}</Badge>
            <Badge variant="neutral">{view.strategyLabel}</Badge>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-400 truncate">{accountability.detail}</p>
        </div>
      </div>

      {/* Top stat row - 4 columns always */}
      <div className="grid grid-cols-4 gap-2 md:gap-3">
        {topStats.map((s) => {
          const toneTextMap: Record<string, string> = {
            good: "text-emerald-600 dark:text-emerald-400",
            bad: "text-red-600 dark:text-red-400",
            info: "text-sky-600 dark:text-sky-400",
            neutral: "text-slate-900 dark:text-white",
          };
          return (
            <div key={s.label} className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-3 shadow-sm">
              <div className="text-[11px] text-slate-500 dark:text-slate-400 mb-0.5">{s.label}</div>
              <div className={`text-xl md:text-2xl font-bold tabular-nums ${toneTextMap[s.tone] ?? toneTextMap.neutral}`}>
                {s.value}
              </div>
              <div className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">{s.caption}</div>
            </div>
          );
        })}
      </div>

      {/* Main grid: picks (2/3) + side column (1/3) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {/* Picks column */}
        <div className="lg:col-span-2 flex flex-col gap-3">
          <Panel title="当前推荐" icon="trendUp" badge={`${snapshot.asian_picks?.length ?? 0} 条·亚盘`} dense>
            <PickGrid
              records={snapshot.asian_picks}
              onSelect={onSelectRecommendation}
              emptyMessage="暂无可发布推荐信号"
            />
          </Panel>
          <SettlementFeed records={snapshot.recent_settlements ?? []} />
        </div>

        {/* Side column */}
        <div className="flex flex-col gap-3">
          <StrategyStateCard snapshot={snapshot} />
          <KpiCards cards={view.kpiCards} compact />
        </div>
      </div>
    </div>
  );
}

function RecommendationOpportunityPanel({
  opportunity,
}: {
  opportunity: DashboardViewModel["recommendationOpportunity"];
}) {
  const releaseGate = opportunity.releaseGate;
  const gateRows = formatRecommendationGateRowsForDisplay(releaseGate);
  const headline = releaseGate?.title || opportunity.title || "推荐发布机会";
  const detail = releaseGate?.detail || opportunity.detail || "暂无分析";

  return (
    <Panel
      title="推荐发布机会"
      icon="production"
      badge={releaseGate?.title ? releaseGate.title : opportunity.title}
    >
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={toneVariant(releaseGate?.tone ?? opportunity.tone)}>{headline}</Badge>
            <span className="text-xs text-slate-500 dark:text-slate-400">{opportunity.thresholdText}</span>
          </div>
          <div className="mt-1 text-sm leading-relaxed text-slate-700 dark:text-slate-300">{detail}</div>
        </div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {(opportunity.metrics ?? []).map((item) => (
          <Metric key={item.label} label={item.label} value={String(item.value ?? "—")} />
        ))}
      </div>
      {gateRows.length > 0 && (
        <div className="mt-3 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="flex items-center justify-between gap-2 bg-slate-50 dark:bg-slate-900/40 px-3 py-2">
            <div className="text-xs font-semibold text-slate-900 dark:text-white">发布闸门</div>
            <Badge variant={toneVariant(releaseGate?.tone ?? opportunity.tone)}>{gateRows.length} 项</Badge>
          </div>
          <div className="divide-y divide-slate-100 dark:divide-slate-700/60">
            {gateRows.map((gate) => (
              <div key={gate.key} className="grid grid-cols-1 md:grid-cols-12 gap-3 px-3 py-3 text-xs">
                <div className="md:col-span-4 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={toneVariant(gate.tone)}>{gate.status}</Badge>
                    <span className="font-semibold text-slate-900 dark:text-white">{gate.name}</span>
                  </div>
                </div>
                <div className="md:col-span-6 leading-relaxed text-slate-600 dark:text-slate-300">
                  {gate.detail || "暂无说明"}
                </div>
                <div className="md:col-span-2">
                  <div className="flex items-center justify-between gap-2 text-slate-500 dark:text-slate-400">
                    <span>进度</span>
                    <span className="font-semibold tabular-nums text-slate-900 dark:text-white">{gate.progressText}</span>
                  </div>
                  <div className="mt-1 h-1.5 rounded-full bg-slate-100 dark:bg-slate-700 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        gate.tone === "good"
                          ? "bg-emerald-500"
                          : gate.tone === "bad"
                            ? "bg-red-500"
                            : gate.tone === "caution"
                              ? "bg-amber-500"
                              : "bg-sky-500"
                      }`}
                      style={{ width: gate.width }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </Panel>
  );
}

function SignalWorkbenchPanel({
  opportunity,
  onSelectLedger,
  onSelectBlocker,
}: {
  opportunity: DashboardViewModel["recommendationOpportunity"];
  onSelectLedger: (id: string) => void;
  onSelectBlocker: (filter: LedgerReasonFilter) => void;
}) {
  const summary = formatSignalWorkbenchForDisplay(opportunity);
  const candidates = opportunity.candidates ?? [];
  const blockers = opportunity.blockers ?? [];
  const counterCandidates = opportunity.counterSignal?.candidates ?? [];

  return (
    <Panel title="候选与阻断工作台" icon="eye" badge={summary.badge}>
      <div className="mb-3 flex flex-col gap-1">
        <div className="text-sm font-semibold text-slate-900 dark:text-white">{summary.headline}</div>
        <div className="text-xs text-slate-500 dark:text-slate-400">
          {summary.monitoringText}
        </div>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="flex items-center justify-between gap-2 bg-slate-50 dark:bg-slate-900/40 px-3 py-2">
            <div className="text-xs font-semibold text-slate-900 dark:text-white">候选池</div>
            <Badge variant={candidates.length ? "info" : "neutral"}>{candidates.length} 条</Badge>
          </div>
          <div className="divide-y divide-slate-100 dark:divide-slate-700/60">
            {candidates.length > 0 ? (
              candidates.slice(0, 5).map((candidate) => (
                <button
                  type="button"
                  key={candidate.ledgerId}
                  onClick={() => onSelectLedger(candidate.ledgerId)}
                  className="w-full text-left px-3 py-3 hover:bg-slate-50 dark:hover:bg-slate-900/40 transition-colors"
                >
                  <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 text-xs">
                    <div className="sm:col-span-5 min-w-0">
                      {candidate.homeTeam && candidate.awayTeam ? (
                        <TeamMatchup
                          home={candidate.homeTeam}
                          away={candidate.awayTeam}
                          homeLogo={candidate.homeTeamLogoUrl}
                          awayLogo={candidate.awayTeamLogoUrl}
                          meta={candidate.league}
                          size="xs"
                        />
                      ) : (
                        <>
                          <div className="font-semibold text-slate-900 dark:text-white truncate">{candidate.matchup}</div>
                          <div className="mt-1 text-slate-500 dark:text-slate-400 truncate">{candidate.league}</div>
                        </>
                      )}
                    </div>
                    <div className="sm:col-span-4 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={candidate.thresholdReady ? "good" : "caution"}>{candidate.actionLabel}</Badge>
                        <span className="font-semibold text-slate-900 dark:text-white truncate">{candidate.selection}</span>
                      </div>
                      <div className="mt-1 text-slate-500 dark:text-slate-400 truncate">{candidate.blockerLabel}</div>
                    </div>
                    <div className="sm:col-span-3 grid grid-cols-2 gap-2 tabular-nums">
                      <div>
                        <div className="text-slate-500 dark:text-slate-400">概率</div>
                        <div className="font-semibold text-slate-900 dark:text-white">{candidate.probabilityText}</div>
                        <div className="text-slate-500 dark:text-slate-400">{candidate.probabilityGapText}</div>
                      </div>
                      <div>
                        <div className="text-slate-500 dark:text-slate-400">边际</div>
                        <div className="font-semibold text-slate-900 dark:text-white">{candidate.edgeText}</div>
                        <div className="text-slate-500 dark:text-slate-400">{candidate.oddsText} · {candidate.snapshotText}</div>
                      </div>
                    </div>
                  </div>
                </button>
              ))
            ) : (
              <div className="px-3 py-4 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                {summary.emptyCandidateText}
              </div>
            )}
          </div>
          {counterCandidates.length > 0 && (
            <div className="border-t border-slate-200 dark:border-slate-700 bg-amber-50/60 dark:bg-amber-950/20 px-3 py-3">
              <div className="mb-2 flex items-center gap-2">
                <Badge variant="caution">反向观察</Badge>
                <span className="text-xs font-semibold text-slate-900 dark:text-white">{opportunity.counterSignal?.title}</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {counterCandidates.slice(0, 2).map((candidate) => (
                  <button
                    key={candidate.ledgerId}
                    type="button"
                    onClick={() => onSelectLedger(candidate.ledgerId)}
                    className="rounded-lg border border-amber-200 dark:border-amber-800 bg-white/80 dark:bg-slate-950/70 px-3 py-2 text-left text-xs"
                  >
                    <div className="font-semibold text-slate-900 dark:text-white truncate">{candidate.matchup}</div>
                    <div className="mt-1 text-slate-600 dark:text-slate-300 truncate">{candidate.signalLabel} · {candidate.metaProbabilityText}</div>
                    <div className="mt-1 text-slate-500 dark:text-slate-400">{candidate.confidenceText}</div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="flex items-center justify-between gap-2 bg-slate-50 dark:bg-slate-900/40 px-3 py-2">
            <div className="text-xs font-semibold text-slate-900 dark:text-white">阻断漏斗</div>
            <Badge variant={blockers.length ? "caution" : "good"}>{blockers.length} 类</Badge>
          </div>
          <div className="divide-y divide-slate-100 dark:divide-slate-700/60">
            {blockers.length > 0 ? (
              blockers.slice(0, 6).map((blocker) => (
                <button
                  key={blocker.key}
                  type="button"
                  onClick={() => onSelectBlocker({ label: blocker.label })}
                  className="block w-full px-3 py-3 text-left text-xs hover:bg-slate-50 dark:hover:bg-slate-900/40 transition-colors"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-semibold text-slate-900 dark:text-white truncate">{blocker.label}</div>
                      <div className="mt-1 text-slate-500 dark:text-slate-400">{blocker.countText}</div>
                    </div>
                    <div className="font-semibold tabular-nums text-slate-900 dark:text-white">{blocker.count}</div>
                  </div>
                  <div className="mt-2 h-1.5 rounded-full bg-slate-100 dark:bg-slate-700 overflow-hidden">
                    <div className="h-full rounded-full bg-amber-500" style={{ width: blocker.width }} />
                  </div>
                </button>
              ))
            ) : (
              <div className="px-3 py-4 text-xs text-slate-600 dark:text-slate-300">
                {summary.emptyBlockerText}
              </div>
            )}
          </div>
        </div>
      </div>
    </Panel>
  );
}

// ─── Signals section ─────────────────────────────────────────────────────────

function SignalsSection({ snapshot, view, onSelectLedger, onSelectRecommendation }: {
  snapshot: DashboardSnapshot;
  view: DashboardViewModel;
  onSelectLedger: (id: string) => void;
  onSelectRecommendation: (r: DashboardRecord) => void;
}) {
  const mb = snapshot.market_breakdown;
  const [ledgerReasonFilter, setLedgerReasonFilter] = useState<LedgerReasonFilter | null>(null);
  // Build heatmap cells from market_breakdown (league × market)
  const heatmapCells = (mb?.heatmap_cells ?? [])
    .filter((c) => c.hit_rate != null && c.sample_count >= 1)
    .map((c) => ({
      x: c.league,
      y: c.market,
      value: c.hit_rate ?? 0,
      sampleSize: c.sample_count,
      tooltip: `${c.league} × ${c.market}: 命中 ${((c.hit_rate ?? 0) * 100).toFixed(1)}% · ROI ${(((c.roi ?? 0) * 100)).toFixed(1)}% · n=${c.sample_count}`,
    }));
  const roiCells = (mb?.heatmap_cells ?? [])
    .filter((c) => c.roi != null && c.sample_count >= 1)
    .map((c) => ({
      x: c.league,
      y: c.market,
      value: c.roi ?? 0,
      sampleSize: c.sample_count,
      tooltip: `${c.league} × ${c.market}: ROI ${((c.roi ?? 0) * 100).toFixed(1)}% (n=${c.sample_count})`,
    }));

  return (
    <div className="flex flex-col gap-4">
      <RecommendationOpportunityPanel opportunity={view.recommendationOpportunity} />
      <SignalWorkbenchPanel
        opportunity={view.recommendationOpportunity}
        onSelectLedger={onSelectLedger}
        onSelectBlocker={setLedgerReasonFilter}
      />

      {/* Heatmaps - 联赛 × 市场命中率 / ROI */}
      {(mb?.heatmap_cells?.length ?? 0) > 0 && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <HeatMap
            cells={heatmapCells}
            xLabels={mb?.leagues ?? []}
            yLabels={mb?.markets ?? []}
            title="命中率热力图（联赛 × 市场）"
            subtitle={`总结算样本 ${mb?.total_settled ?? 0}，颜色越深命中率越高，透明度反映样本量`}
            domain={[0, 1]}
            scale="sequential"
            formatValue={(v) => `${(v * 100).toFixed(0)}%`}
          />
          <HeatMap
            cells={roiCells}
            xLabels={mb?.leagues ?? []}
            yLabels={mb?.markets ?? []}
            title="ROI 热力图（联赛 × 市场）"
            subtitle="红=亏损 / 灰=平 / 绿=盈利，可识别强势赛事"
            domain={[-0.30, 0.30]}
            scale="diverging"
            formatValue={(v) => `${v > 0 ? "+" : ""}${(v * 100).toFixed(0)}%`}
          />
        </div>
      )}

      {/* Candidate funnel */}
      <Panel title="候选分析漏斗" icon="eye">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {view.filterGroups.map((f) => (
            <div key={f.reason} className="text-center p-3 rounded-lg bg-slate-50 dark:bg-slate-700/40">
              <div className="text-lg font-bold text-slate-900 dark:text-white tabular-nums">{f.count}</div>
              <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 truncate">{f.label || reasonLabel(f.reason)}</div>
            </div>
          ))}
        </div>
      </Panel>

      {/* Prediction ledger */}
      <LedgerTable
        rows={snapshot.prediction_ledger ?? []}
        selectedId={null}
        onSelect={onSelectLedger}
        reasonFilter={ledgerReasonFilter}
        onReasonFilterClear={() => setLedgerReasonFilter(null)}
      />
    </div>
  );
}

// ─── Production section ───────────────────────────────────────────────────────

function ProductionSection({ view }: { view: DashboardViewModel }) {
  const gates = view.productionReadiness.gateRows ?? [];
  const formattedGates = formatProductionGatesForDisplay(gates);
  return (
    <div className="flex flex-col gap-4">
      <ProductionGates
        gates={formattedGates}
        overallTone={view.productionReadiness.tone ?? "neutral"}
        overallLabel={view.productionReadiness.actionText ?? "—"}
      />
      <RecommendationOpportunityPanel opportunity={view.recommendationOpportunity} />
    </div>
  );
}

// ─── Model section ────────────────────────────────────────────────────────────

function ModelSection({
  view,
  snapshot,
  validationActionJobId,
  onCancelValidationJob,
  onRetryValidationJob,
  onStartValidationJob,
  onStartQuickValidationJob,
}: {
  view: DashboardViewModel;
  snapshot: DashboardSnapshot;
  validationActionJobId: string | null;
  onCancelValidationJob: (jobId: string) => void;
  onRetryValidationJob: (jobId: string) => void;
  onStartValidationJob: () => void;
  onStartQuickValidationJob: () => void;
}) {
  const backtestCurve = view.backtestCurve;
  const buckets = snapshot.buckets ?? [];

  // Build reliability points from market-global buckets.
  // The dashboard contract normalizes to {band, sample_count, hit_rate, avg_model_probability}.
  const reliabilityPoints = buckets
    .filter((b) => b.sample_count >= 3 && b.avg_model_probability != null && b.hit_rate != null)
    .map((b) => ({
      predicted: Number(b.avg_model_probability),
      actual: Number(b.hit_rate),
      samples: Number(b.sample_count),
      bucket: String(b.band || "").replace("prob:", ""),
    }));

  const latestValidation = snapshot.latest_validation ?? null;
  const validationJob = snapshot.validation_job ?? null;
  const validationProgress = validationJob?.progress;
  const validationSummary = validationJob?.result_summary ?? {};
  const validationRunSummary = validationJob ? formatValidationJobRunSummary(validationJob) : null;
  const validationLeagueDiagnostics = validationJob ? formatValidationLeagueRunDiagnostics(validationJob) : null;
  const validationTimeline = validationJob ? formatValidationJobTimeline(validationJob) : null;
  const validationVerdict = validationSummary.verdict ?? null;
  const validationVerdictDisplayTone = validationVerdictTone(validationVerdict);
  const validationMetricScope = formatValidationMetricScope(validationSummary);
  const asianHandicapValidation = formatAsianHandicapValidation(validationSummary);
  const validationStartBusy = validationActionJobId === "holdout-new" || validationActionJobId === "holdout-quick";
  const validationActionBusy = validationStartBusy || (!!validationJob && validationActionJobId === validationJob.job_id);
  const canCancelValidationJob = !!validationJob && ["pending", "running"].includes(String(validationJob.status));
  const canRetryValidationJob = !!validationJob && ["failed", "cancelled"].includes(String(validationJob.status));
  const canStartValidationJob = !validationJob || !["pending", "running"].includes(String(validationJob.status));
  const startValidationLabel = !validationJob
    ? "启动验证"
    : validationJob.status === "completed"
      ? "重跑验证"
      : "继续验证";

  return (
    <div className="flex flex-col gap-4">
      {/* Profitability forecast - top of model section */}
      <ProfitabilityPanel forecast={snapshot.profitability_forecast} />

      <Panel
        title="模型失利归因"
        icon="alert"
        badge={view.modelFailureDiagnostics.policyText}
      >
        <div className="mb-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/40 px-3 py-3">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={toneVariant(view.modelFailureDiagnostics.tone)}>
                  {view.modelFailureDiagnostics.primaryText}
                </Badge>
                <span className="text-sm font-semibold text-slate-900 dark:text-white">
                  {view.modelFailureDiagnostics.title}
                </span>
              </div>
              <div className="mt-1 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                {view.modelFailureDiagnostics.detail}
              </div>
            </div>
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
          {view.modelFailureDiagnostics.metrics.map((metric) => (
            <div key={metric.label} className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2">
              <div className="text-xs text-slate-500 dark:text-slate-400">{metric.label}</div>
              <div className={`mt-0.5 text-sm font-semibold tabular-nums ${
                metric.tone === "good"
                  ? "text-emerald-600 dark:text-emerald-400"
                  : metric.tone === "bad"
                    ? "text-red-600 dark:text-red-400"
                    : metric.tone === "caution"
                      ? "text-amber-700 dark:text-amber-300"
                      : "text-slate-900 dark:text-white"
              }`}>{metric.value}</div>
              <div className="mt-0.5 text-[11px] leading-snug text-slate-500 dark:text-slate-400">{metric.caption}</div>
            </div>
          ))}
        </div>
        {view.modelFailureDiagnostics.policyRows.length > 0 && (
          <div className="mb-3 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
            <div className="flex items-center justify-between gap-2 bg-slate-50 dark:bg-slate-900/40 px-3 py-2">
              <div className="text-xs font-semibold text-slate-900 dark:text-white">策略动作</div>
              <Badge variant={view.modelFailureDiagnostics.policyRows.some((rule) => rule.tone === "bad") ? "bad" : "info"}>
                {view.modelFailureDiagnostics.policyRows.length} 条
              </Badge>
            </div>
            <div className="divide-y divide-slate-100 dark:divide-slate-700/60">
              {view.modelFailureDiagnostics.policyRows.slice(0, 4).map((rule) => (
                <div key={rule.key} className="grid grid-cols-1 md:grid-cols-12 gap-3 px-3 py-3 text-xs">
                  <div className="md:col-span-4 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={toneVariant(rule.tone)}>{rule.statusText}</Badge>
                      <span className="font-semibold text-slate-900 dark:text-white">{rule.title}</span>
                    </div>
                    <div className="mt-1 leading-relaxed text-slate-600 dark:text-slate-300">{rule.detail}</div>
                  </div>
                  <div className="md:col-span-3">
                    <div className="text-slate-500 dark:text-slate-400">动作 / 目标</div>
                    <div className="font-semibold text-slate-900 dark:text-white">{rule.actionText}</div>
                    <div className="mt-1 text-slate-600 dark:text-slate-300">{rule.targetText}</div>
                  </div>
                  <div className="md:col-span-2">
                    <div className="text-slate-500 dark:text-slate-400">样本 / ROI</div>
                    <div className="font-semibold tabular-nums text-slate-900 dark:text-white">{rule.sampleText} · {rule.roiText}</div>
                  </div>
                  <div className="md:col-span-3">
                    <div className="text-slate-500 dark:text-slate-400">证据</div>
                    <div className="leading-relaxed text-slate-700 dark:text-slate-300">{rule.evidence}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        {view.modelFailureDiagnostics.driverRows.length > 0 ? (
          <div className="rounded-lg border border-slate-200 dark:border-slate-700 divide-y divide-slate-100 dark:divide-slate-700/60 overflow-hidden">
            {view.modelFailureDiagnostics.driverRows.slice(0, 5).map((driver) => (
              <div key={driver.key} className="grid grid-cols-1 lg:grid-cols-12 gap-3 px-3 py-3 text-xs">
                <div className="lg:col-span-4 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={toneVariant(driver.tone)}>{driver.categoryText}</Badge>
                    <span className="font-semibold text-slate-900 dark:text-white">{driver.title}</span>
                  </div>
                  <div className="mt-1 leading-relaxed text-slate-600 dark:text-slate-300">{driver.detail}</div>
                </div>
                <div className="lg:col-span-2">
                  <div className="text-slate-500 dark:text-slate-400">样本 / ROI</div>
                  <div className="font-semibold tabular-nums text-slate-900 dark:text-white">{driver.sampleText} · {driver.roiText}</div>
                  <div className="mt-1 text-slate-500 dark:text-slate-400">亏损贡献 {driver.lossText}</div>
                </div>
                <div className="lg:col-span-3">
                  <div className="text-slate-500 dark:text-slate-400">证据</div>
                  <div className="leading-relaxed text-slate-700 dark:text-slate-300">{driver.evidence}</div>
                </div>
                <div className="lg:col-span-3">
                  <div className="text-slate-500 dark:text-slate-400">下一步</div>
                  <div className="leading-relaxed text-slate-700 dark:text-slate-300">{driver.action}</div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-3 text-xs text-slate-600 dark:text-slate-300">
            已回测样本不足或暂未发现稳定负收益分组，继续积累样本后再归因。
          </div>
        )}
      </Panel>

      {!validationJob && (
        <Panel title="Holdout 执行进度" icon="checklist" badge="未启动">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="text-sm text-slate-600 dark:text-slate-300">
              还没有可展示的验证任务。启动后会按联赛拆分执行，并复用已有缓存；失败后可从未成功联赛继续。
            </div>
            <button
              type="button"
              onClick={onStartQuickValidationJob}
              disabled={validationActionBusy}
              title="用小样本快速验证队列、缓存、模型和亚盘结算链路"
              className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-sky-200 dark:border-sky-800 bg-white dark:bg-slate-950 px-3 py-1.5 text-xs font-semibold text-sky-700 dark:text-sky-300 hover:bg-sky-50 dark:hover:bg-sky-950/40 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Icon name={validationActionBusy ? "loading" : "zap"} size={13} className={validationActionBusy ? "animate-spin" : ""} />
              快速诊断
            </button>
            <button
              type="button"
              onClick={onStartValidationJob}
              disabled={validationActionBusy}
              title="启动完整 Holdout 验证任务"
              className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-emerald-200 dark:border-emerald-800 bg-white dark:bg-slate-950 px-3 py-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Icon name={validationActionBusy ? "loading" : "refresh"} size={13} className={validationActionBusy ? "animate-spin" : ""} />
              {startValidationLabel}
            </button>
          </div>
        </Panel>
      )}

      {/* Latest holdout validation snapshot */}
      {latestValidation && (
        <Panel title="最近一次 Holdout 验证" icon="gauge" badge={latestValidation.beats_market ? "✓ 跑赢市场" : "✗ 未跑赢"}>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
            <Metric label="Log Loss 差" value={latestValidation.log_loss_diff != null ? (latestValidation.log_loss_diff < 0 ? "" : "+") + latestValidation.log_loss_diff.toFixed(4) : "—"} />
            <Metric label="Brier 差" value={latestValidation.brier_diff != null ? (latestValidation.brier_diff < 0 ? "" : "+") + latestValidation.brier_diff.toFixed(4) : "—"} />
            <Metric label="ROI" value={latestValidation.roi != null ? `${(latestValidation.roi * 100).toFixed(1)}%` : "—"} />
            <Metric label="样本数" value={`${latestValidation.bet_count}/${latestValidation.evaluated_count}`} />
          </div>
          <div className="text-xs text-ink-600 dark:text-ink-400 leading-relaxed">
            自动化就绪度: <strong className={latestValidation.automation_readiness === "paper_trade_only" ? "text-success-600" : latestValidation.automation_readiness === "watchlist" ? "text-warning-600" : "text-danger-600"}>{latestValidation.automation_readiness}</strong>
            <span className="mx-2">·</span>
            训练赛季: {latestValidation.training_seasons?.join(", ")}
            <span className="mx-2">·</span>
            验证赛季: {latestValidation.validation_seasons?.join(", ")}
            <span className="mx-2">·</span>
            {latestValidation.created_at_utc ? fullLocalTime(latestValidation.created_at_utc) : "—"}
          </div>
        </Panel>
      )}

      {validationJob && validationProgress && (
        <Panel
          title="Holdout 执行进度"
          icon="checklist"
          badge={`${validationProgress.completed_leagues}/${validationProgress.total_leagues} 联赛`}
        >
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-4">
            <Metric label="任务状态" value={validationJobStatusLabel(validationJob.status)} />
            <Metric label="缓存命中" value={`${(validationJob.league_results ?? []).filter((item) => item.cache_hit).length} 联赛`} />
            <Metric label="Log Loss 差" value={validationSummary.log_loss_diff != null ? `${validationSummary.log_loss_diff > 0 ? "+" : ""}${Number(validationSummary.log_loss_diff).toFixed(4)}` : "—"} />
            <Metric label="ROI" value={validationSummary.roi != null ? `${(Number(validationSummary.roi) * 100).toFixed(1)}%` : "—"} />
            <Metric label="更新时间" value={fullLocalTime(validationJob.updated_at_utc ?? null)} />
          </div>
          <div className={`mb-4 rounded-lg border px-3 py-3 ${
            validationMetricScope.tone === "good"
              ? "border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/30"
              : "border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30"
          }`}>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={toneVariant(validationMetricScope.tone)}>{validationMetricScope.badge}</Badge>
                  <span className="text-sm font-semibold text-slate-900 dark:text-white">{validationMetricScope.title}</span>
                </div>
                <div className="mt-1 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                  {validationMetricScope.detail}
                </div>
              </div>
              <div className="text-xs font-semibold tabular-nums text-slate-700 dark:text-slate-200">
                {validationMetricScope.sampleText}
              </div>
            </div>
          </div>
          <div className={`mb-4 rounded-lg border px-3 py-3 ${
            asianHandicapValidation.tone === "good"
              ? "border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/30"
              : asianHandicapValidation.tone === "bad"
                ? "border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30"
                : "border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30"
          }`}>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={toneVariant(asianHandicapValidation.tone)}>{asianHandicapValidation.badge}</Badge>
                  <span className="text-sm font-semibold text-slate-900 dark:text-white">{asianHandicapValidation.title}</span>
                </div>
                <div className="mt-1 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                  {asianHandicapValidation.detail}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-700 dark:text-slate-200 lg:min-w-[360px]">
                <div><span className="text-slate-500 dark:text-slate-400">样本：</span>{asianHandicapValidation.sampleText}</div>
                <div><span className="text-slate-500 dark:text-slate-400">ROI：</span>{asianHandicapValidation.roiText}</div>
                <div><span className="text-slate-500 dark:text-slate-400">结果：</span>{asianHandicapValidation.resultText}</div>
                <div><span className="text-slate-500 dark:text-slate-400">收益：</span>{asianHandicapValidation.profitText}</div>
              </div>
            </div>
          </div>
          {validationRunSummary && (
            <div className="mb-4 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/40 px-3 py-3">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={toneVariant(validationRunSummary.tone)}>运行摘要</Badge>
                    <span className="text-sm font-semibold text-slate-900 dark:text-white">
                      {validationRunSummary.headline}
                    </span>
                  </div>
                  <div className="mt-1 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                    {validationRunSummary.detail}
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-600 dark:text-slate-300 lg:min-w-[480px]">
                  <div><span className="text-slate-500 dark:text-slate-400">进度：</span>{validationRunSummary.progressText}</div>
                  <div><span className="text-slate-500 dark:text-slate-400">缓存：</span>{validationRunSummary.cacheText}</div>
                  <div><span className="text-slate-500 dark:text-slate-400">当前：</span>{validationRunSummary.activeText}</div>
                  <div><span className="text-slate-500 dark:text-slate-400">续跑：</span>{validationRunSummary.resumeText}</div>
                  <div><span className="text-slate-500 dark:text-slate-400">执行：</span>{validationRunSummary.queueText}</div>
                  <div><span className="text-slate-500 dark:text-slate-400">队列：</span>{validationRunSummary.queueDetail}</div>
                  <div><span className="text-slate-500 dark:text-slate-400">队列 id：</span>{validationRunSummary.queueJobText}</div>
                  <div><span className="text-slate-500 dark:text-slate-400">Runner：</span>{validationRunSummary.runnerText}</div>
                  <div><span className="text-slate-500 dark:text-slate-400">健康：</span>{validationRunSummary.healthText}</div>
                  <div><span className="text-slate-500 dark:text-slate-400">动作：</span>{validationRunSummary.healthNextAction}</div>
                  <div><span className="text-slate-500 dark:text-slate-400">尝试：</span>{validationRunSummary.attemptText}</div>
                  <div><span className="text-slate-500 dark:text-slate-400">心跳：</span>{validationRunSummary.heartbeatText}</div>
                  <div><span className="text-slate-500 dark:text-slate-400">重试：</span>{validationRunSummary.retryText}</div>
                  <div><span className="text-slate-500 dark:text-slate-400">失败：</span>{validationRunSummary.failureText}</div>
                </div>
              </div>
            </div>
          )}
          {validationTimeline && (
            <div className="mb-4 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-3">
              <div className="mb-3 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Badge variant="neutral">执行时间线</Badge>
                  <span className="text-xs text-slate-500 dark:text-slate-400">{validationTimeline.badge}</span>
                </div>
              </div>
              {validationTimeline.rows.length === 0 ? (
                <div className="text-xs text-slate-500 dark:text-slate-400">{validationTimeline.emptyText}</div>
              ) : (
                <div className="space-y-2">
                  {validationTimeline.rows.map((event) => (
                    <div key={event.key} className="grid grid-cols-1 gap-1 rounded-md border border-slate-100 dark:border-slate-800 px-3 py-2 sm:grid-cols-[150px_minmax(0,1fr)]">
                      <div className="text-xs font-semibold text-slate-500 dark:text-slate-400">{event.timeText}</div>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={toneVariant(event.tone)}>{event.title}</Badge>
                          <span className="min-w-0 text-sm font-semibold text-slate-900 dark:text-white">{event.message}</span>
                        </div>
                        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{event.detailText}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          {validationVerdict && (
            <div className={`mb-4 rounded-lg border px-3 py-3 ${
              validationVerdictDisplayTone === "good"
                ? "border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/30"
                : validationVerdictDisplayTone === "bad"
                  ? "border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30"
                  : "border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30"
            }`}>
              <div className="flex flex-col sm:flex-row sm:items-start gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={toneVariant(validationVerdictDisplayTone)}>验证结论</Badge>
                    <span className="text-sm font-semibold text-slate-900 dark:text-white">
                      {validationVerdict.title ?? "验证结论待确认"}
                    </span>
                  </div>
                  {validationVerdict.detail && (
                    <div className="mt-1 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                      {validationVerdict.detail}
                    </div>
                  )}
                </div>
                {validationVerdict.next_action && (
                  <div className="text-xs leading-relaxed text-slate-700 dark:text-slate-200 sm:max-w-md">
                    <span className="font-semibold">下一步：</span>{validationVerdict.next_action}
                  </div>
                )}
              </div>
            </div>
          )}
          {(canCancelValidationJob || canRetryValidationJob || canStartValidationJob) && (
            <ValidationJobActionBar
              job={validationJob}
              actionJobId={validationActionJobId}
              statusLabel={validationJobStatusLabel(validationJob.status)}
              statusTone={validationStatusTone(validationJob.status)}
              startLabel={startValidationLabel}
              quickStartLabel="快速诊断"
              onQuickStart={onStartQuickValidationJob}
              onStart={onStartValidationJob}
              onCancel={onCancelValidationJob}
              onRetry={onRetryValidationJob}
            />
          )}
          <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-700 overflow-hidden mb-3">
            <div
              className={`h-full rounded-full ${
                validationJob.status === "failed" ? "bg-red-500" :
                validationJob.status === "completed" ? "bg-emerald-500" :
                "bg-amber-500"
              }`}
              style={{ width: `${Math.round((validationProgress.progress_ratio ?? 0) * 100)}%` }}
            />
          </div>
          {validationLeagueDiagnostics && (
            <div className="rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
              <div className="bg-slate-50 dark:bg-slate-900/40 px-3 py-3">
                <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">执行诊断</span>
                      <Badge variant={validationLeagueDiagnostics.counts.failed > 0 ? "bad" : validationLeagueDiagnostics.counts.running > 0 || validationLeagueDiagnostics.counts.pending > 0 ? "caution" : "good"}>
                        {validationLeagueDiagnostics.badge}
                      </Badge>
                      <span className="text-sm font-semibold text-slate-900 dark:text-white">{validationLeagueDiagnostics.headline}</span>
                    </div>
                    <div className="mt-1 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                      {validationLeagueDiagnostics.detail}
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-x-4 gap-y-1 text-xs text-slate-600 dark:text-slate-300 lg:min-w-[360px]">
                    <div><span className="text-slate-500 dark:text-slate-400">成功：</span>{validationLeagueDiagnostics.counts.succeeded}</div>
                    <div><span className="text-slate-500 dark:text-slate-400">取消：</span>{validationLeagueDiagnostics.counts.cancelled}</div>
                    <div><span className="text-slate-500 dark:text-slate-400">缓存：</span>{validationLeagueDiagnostics.counts.cacheHit}</div>
                  </div>
                </div>
              </div>
              <div className="divide-y divide-slate-100 dark:divide-slate-700/60">
                {validationLeagueDiagnostics.rows.map((row) => (
                  <div key={row.division} className="grid grid-cols-1 lg:grid-cols-12 gap-3 px-3 py-3 text-xs">
                    <div className="lg:col-span-3 min-w-0">
                      <div className="font-semibold text-slate-900 dark:text-white truncate">{row.name}</div>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <Badge variant={toneVariant(row.tone)}>{row.statusText}</Badge>
                        <Badge variant={row.cacheText === "命中缓存" ? "info" : "neutral"}>{row.cacheText}</Badge>
                      </div>
                    </div>
                    <div className="lg:col-span-2">
                      <div className="text-slate-500 dark:text-slate-400">Log Loss 差 / ROI</div>
                      <div className="mt-0.5 flex flex-wrap gap-2 font-semibold tabular-nums">
                        <span className={row.logLossText.startsWith("-") ? "text-emerald-600 dark:text-emerald-400" : row.logLossText.startsWith("+") ? "text-red-600 dark:text-red-400" : "text-slate-900 dark:text-white"}>
                          {row.logLossText}
                        </span>
                        <span className={row.roiText.startsWith("+") ? "text-emerald-600 dark:text-emerald-400" : row.roiText.startsWith("-") ? "text-red-600 dark:text-red-400" : "text-slate-900 dark:text-white"}>
                          {row.roiText}
                        </span>
                      </div>
                    </div>
                    <div className="lg:col-span-3">
                      <div className="text-slate-500 dark:text-slate-400">时间</div>
                      <div className="mt-0.5 text-slate-900 dark:text-white tabular-nums">
                        {fullLocalTime(row.finishedAt ?? row.updatedAt ?? null)}
                      </div>
                      <div className="mt-1 leading-relaxed text-slate-500 dark:text-slate-400">
                        {row.runtimeText}
                      </div>
                    </div>
                    <div className="lg:col-span-4">
                      <div className="text-slate-500 dark:text-slate-400">诊断 / 下一步</div>
                      {row.errorText && (
                        <div className={`mt-0.5 leading-relaxed ${
                          row.tone === "bad" ? "text-red-600 dark:text-red-400" : "text-amber-700 dark:text-amber-300"
                        }`}>
                          {row.errorText}
                        </div>
                      )}
                      <div className="mt-0.5 leading-relaxed text-slate-700 dark:text-slate-300">{row.actionText}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {validationJob.last_error && (
            <div className="mt-3 rounded-lg bg-red-50 dark:bg-red-900/20 px-3 py-2 text-xs text-red-700 dark:text-red-300">
              {validationJob.last_error}
            </div>
          )}
        </Panel>
      )}

      {/* Reliability diagram - probability calibration */}
      {reliabilityPoints.length > 0 && (
        <ReliabilityDiagram
          points={reliabilityPoints}
          subtitle={`基于 ${reliabilityPoints.length} 个概率桶 · 散点越靠近对角线，模型概率越准`}
        />
      )}

      {/* Per-market breakdown table */}
      {(snapshot.market_breakdown?.by_market?.length ?? 0) > 0 && (
        <Panel title="按市场表现分组" icon="trendUp">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-700/50 text-xs text-slate-500 dark:text-slate-400">
                  <th className="text-left py-2 px-3 font-medium">市场</th>
                  <th className="text-right py-2 px-3 font-medium">已结算</th>
                  <th className="text-right py-2 px-3 font-medium">命中</th>
                  <th className="text-right py-2 px-3 font-medium">命中率</th>
                  <th className="text-right py-2 px-3 font-medium">ROI</th>
                </tr>
              </thead>
              <tbody>
                {(snapshot.market_breakdown?.by_market ?? []).map((row) => (
                  <tr key={row.market} className="border-b border-slate-50 dark:border-slate-700/30">
                    <td className="py-2 px-3 text-xs font-medium text-slate-800 dark:text-slate-200">{row.market}</td>
                    <td className="py-2 px-3 text-xs text-right tabular-nums text-slate-600 dark:text-slate-400">{row.sample_count}</td>
                    <td className="py-2 px-3 text-xs text-right tabular-nums text-slate-600 dark:text-slate-400">{row.hit_count}</td>
                    <td className="py-2 px-3 text-xs text-right tabular-nums font-medium">
                      {row.hit_rate != null ? formatPercent(row.hit_rate) : "—"}
                    </td>
                    <td className={`py-2 px-3 text-xs text-right tabular-nums font-medium ${(row.roi ?? 0) > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-500 dark:text-red-400"}`}>
                      {row.roi != null ? formatSignedPercent(row.roi) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {/* Backtest curve */}
      {backtestCurve?.points?.length > 0 && (
        <Panel title="累计 ROI 曲线" icon="chart">
          <OddsChart
            points={backtestCurve.points.map((p) => ({
              label: String(p.index),
              roi: p.cumulativeValue,
            }))}
            lines={["roi"]}
            referenceValue={0}
          />
        </Panel>
      )}

      {/* Calibration bands from snapshot */}
      {(snapshot.buckets ?? []).length > 0 && (
        <Panel title="概率校准分组" icon="gauge">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-700/50 text-xs text-slate-500 dark:text-slate-400">
                  <th className="text-left py-2 px-3 font-medium">概率区间</th>
                  <th className="text-right py-2 px-3 font-medium">样本数</th>
                  <th className="text-right py-2 px-3 font-medium">命中率</th>
                  <th className="text-right py-2 px-3 font-medium">ROI</th>
                </tr>
              </thead>
              <tbody>
                {(snapshot.buckets ?? []).slice(0, 20).map((b, i) => (
                  <tr key={i} className="border-b border-slate-50 dark:border-slate-700/30">
                    <td className="py-2 px-3 text-xs text-slate-700 dark:text-slate-300">{b.band}</td>
                    <td className="py-2 px-3 text-xs text-right tabular-nums text-slate-600 dark:text-slate-400">{b.sample_count}</td>
                    <td className="py-2 px-3 text-xs text-right tabular-nums">{b.hit_rate != null ? formatPercent(b.hit_rate) : "—"}</td>
                    <td className={`py-2 px-3 text-xs text-right tabular-nums font-medium ${(b.roi ?? 0) > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-500 dark:text-red-400"}`}>
                      {b.roi != null ? formatSignedPercent(b.roi) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {/* CLV Tracking */}
      {view.clvTracking?.metrics && view.clvTracking.metrics.length > 0 && (
        <Panel title="收盘线价值 (CLV)" icon="trendUp">
          <div className="text-sm text-slate-700 dark:text-slate-300 mb-3">{view.clvTracking.detail}</div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {view.clvTracking.metrics.map((m, i) => (
              <Metric key={i} label={m.label} value={m.value} />
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

// ─── Data section ─────────────────────────────────────────────────────────────

function ProgramCapabilitiesPanel({ snapshot }: { snapshot: DashboardSnapshot }) {
  const matrix = snapshot.program_capabilities;
  const capabilities = matrix?.capabilities ?? [];
  if (!matrix || capabilities.length === 0) return null;

  const summary = matrix.summary;
  const needsAttention = (summary.warning_count ?? 0) + (summary.blocked_count ?? 0);
  const statusTone = capabilityTone(matrix.status as ProgramCapabilityItem["status"]);
  const actionPlan = formatProgramCapabilityActionPlan(capabilities);

  return (
    <Panel title="程序能力" icon="checklist" badge={`${summary.ready_count}/${summary.total_count} 可用`}>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <Metric label="运行模式" value={capabilityModeLabel(matrix.operating_mode)} />
        <Metric label="可用能力" value={`${summary.ready_count}/${summary.total_count}`} />
        <Metric label="需补强" value={`${needsAttention} 项`} />
        <Metric label="总体状态" value={capabilityStatusLabel(matrix.status as ProgramCapabilityItem["status"])} />
      </div>

      <div className="mb-4 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/40 px-3 py-3">
        <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={actionPlan.items.length > 0 ? "caution" : "good"}>{actionPlan.badge}</Badge>
            <span className="text-sm font-semibold text-slate-900 dark:text-white">{actionPlan.headline}</span>
          </div>
          <span className="text-xs text-slate-500 dark:text-slate-400">按阻断优先、样本缺口优先排序</span>
        </div>
        {actionPlan.items.length > 0 ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-2">
            {actionPlan.items.map((item) => (
              <div key={item.title} className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-slate-900 dark:text-white truncate">{item.title}</span>
                  <Badge variant={toneVariant(item.tone)}>{item.statusText}</Badge>
                </div>
                <div className="mt-2 flex items-center justify-between gap-2 text-slate-500 dark:text-slate-400">
                  <span>{item.progressText}</span>
                  <span>{item.gapText}</span>
                </div>
                <div className="mt-2 leading-relaxed text-slate-600 dark:text-slate-300">{item.nextAction}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs leading-relaxed text-slate-600 dark:text-slate-300">
            当前没有阻断或学习中能力，保持自动学习、队列和缓存在线即可。
          </div>
        )}
      </div>

      <div className="rounded-lg border border-slate-200 dark:border-slate-700 divide-y divide-slate-100 dark:divide-slate-700/60 overflow-hidden">
        {capabilities.map((item) => {
          const progress = capabilityProgress(item);
          const tone = capabilityTone(item.status);
          return (
            <div key={item.key} className="grid grid-cols-1 lg:grid-cols-12 gap-3 px-3 py-3">
              <div className="min-w-0 lg:col-span-3">
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full flex-shrink-0 ${
                    tone === "good" ? "bg-emerald-500" :
                    tone === "bad" ? "bg-red-500" :
                    tone === "caution" ? "bg-amber-500" :
                    "bg-slate-400"
                  }`} />
                  <span className="font-semibold text-sm text-slate-900 dark:text-white truncate">{item.title}</span>
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <Badge variant={toneVariant(tone)}>{capabilityStatusLabel(item.status)}</Badge>
                  <span className="text-xs text-slate-500 dark:text-slate-400">{item.available ? "当前可执行" : "需要补条件"}</span>
                </div>
              </div>

              <div className="text-xs leading-relaxed text-slate-600 dark:text-slate-300 lg:col-span-6">
                <div>{item.detail}</div>
                {item.next_action && (
                  <div className="mt-1 text-slate-500 dark:text-slate-400">下一步：{item.next_action}</div>
                )}
              </div>

              <div className="min-w-0 lg:col-span-3">
                <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                  <span>{item.target != null ? "进度" : "当前"}</span>
                  <span className="tabular-nums">
                    {capabilityNumber(item.current)}
                    {item.target != null ? ` / ${capabilityNumber(item.target)}` : ""}
                  </span>
                </div>
                {progress != null ? (
                  <div className="mt-2 h-2 rounded-full bg-slate-100 dark:bg-slate-700 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        tone === "good" ? "bg-emerald-500" :
                        tone === "bad" ? "bg-red-500" :
                        tone === "caution" ? "bg-amber-500" :
                        "bg-slate-400"
                      }`}
                      style={{ width: `${Math.round(progress * 100)}%` }}
                    />
                  </div>
                ) : (
                  <div className="mt-2 text-xs text-slate-400 dark:text-slate-500">持续监控</div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {matrix.status !== "ready" && (
        <div className={`mt-3 text-xs rounded-lg px-3 py-2 ${
          statusTone === "bad"
            ? "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300"
            : "bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300"
        }`}>
          当前结论：系统仍处于能力受限状态，优先处理缺数据、阻塞项和链路证据不足的能力。
        </div>
      )}
    </Panel>
  );
}

function TaskQueuePanel({ queue }: { queue: TaskQueueHealth | null | undefined }) {
  const display = formatTaskQueueForDisplay(queue);

  return (
    <Panel title="后台任务队列" icon="activity" badge={display.badge}>
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={toneVariant(display.tone)}>{display.backendText}</Badge>
            <span className="text-xs font-semibold text-slate-900 dark:text-white">{display.workerText}</span>
          </div>
          <div className="mt-1 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
            {display.detail}
          </div>
        </div>
        <div className="text-xs leading-relaxed text-slate-500 dark:text-slate-400 sm:max-w-md">
          {display.nextAction}
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Metric label="Redis" value={display.redisText} />
        <Metric label="队列积压" value={display.queuedJobsText} />
        <Metric label="执行配置" value={display.concurrencyText} />
        <Metric label="运行后端" value={display.backendText} />
      </div>
    </Panel>
  );
}

function DashboardCachePanel({ cache }: { cache: DashboardSnapshot["dashboard_cache"] | null | undefined }) {
  const display = formatDashboardCacheForDisplay(cache);

  return (
    <Panel title="看板缓存" icon="refresh" badge={display.badge}>
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={toneVariant(display.tone)}>{display.statusText}</Badge>
            <span className="text-xs font-semibold text-slate-900 dark:text-white">{display.ageText}</span>
          </div>
          <div className="mt-1 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
            {display.detail}
          </div>
        </div>
        <div className="text-xs leading-relaxed text-slate-500 dark:text-slate-400 sm:max-w-md">
          {display.nextAction}
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Metric label="快照年龄" value={display.ageText} />
        <Metric label="缓存窗口" value={display.ttlText} />
        <Metric label="当前状态" value={display.statusText} />
      </div>
    </Panel>
  );
}

function DataSection({ snapshot, view }: { snapshot: DashboardSnapshot; view: DashboardViewModel }) {
  const auto = snapshot.auto_learning_state;
  const resultSummary = auto.last_result_summary ?? {};
  const enabled = auto.enabled;
  const running = isAfterTime(auto.last_started_at_utc, auto.last_finished_at_utc);
  const runCount = auto.run_count;
  const formalRecords = resultSummary.asian_record_count ?? 0;
  const observationRecords = numericValue((resultSummary as Record<string, unknown>).asian_learning_observation_record_count) ?? 0;
  const shadowRecords = resultSummary.asian_shadow_prediction_record_count ?? resultSummary.saved_shadow_prediction_count ?? 0;
  const analyzedCount = resultSummary.asian_analyzed_count ?? 0;
  const analysisSnapshotSync = resultSummary.analysis_market_snapshot_sync ?? {};
  const analysisSnapshotSaved = numericValue(analysisSnapshotSync.saved_snapshot_count) ?? 0;
  const analysisSnapshotGenerated = numericValue(analysisSnapshotSync.generated_snapshot_count) ?? 0;
  const settledRecords = (resultSummary.settled_count ?? 0) + (resultSummary.shadow_settled_count ?? 0);
  const hasError = !!auto.last_error;
  const statusTone: KpiCard["tone"] = hasError ? "bad" : running ? "caution" : enabled ? "good" : "bad";
  const statusText = !enabled ? "自动学习关闭" : hasError ? "异常" : running ? "扫描中" : runCount > 0 ? "上轮已完成" : "等待首轮";

  return (
    <div className="flex flex-col gap-4">
      {/* Auto-learning status */}
      <Panel title="自动学习运行状态" icon="activity" badge={statusText}>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
          <Metric label="候选/分析" value={`${resultSummary.asian_total_candidates ?? 0}/${analyzedCount}`} />
          <Metric label="发布/观察/影子" value={`${formalRecords}/${observationRecords}/${shadowRecords}`} />
          <Metric label="赔率快照" value={`${analysisSnapshotSaved}/${analysisSnapshotGenerated}`} />
          <Metric label="上轮结算" value={`${settledRecords} 条`} />
          <Metric label="最新结算" value={localTime(latestTime(snapshot.prediction_ledger ?? [], "settled_at_utc"))} />
          <Metric label="上次完成" value={fullLocalTime(auto.last_finished_at_utc ?? null)} />
        </div>
        {hasError && (
          <div className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg p-2">
            上次错误：{auto.last_error}
          </div>
        )}
      </Panel>

      <DashboardCachePanel cache={snapshot.dashboard_cache} />

      <TaskQueuePanel queue={snapshot.task_queue} />

      <ProgramCapabilitiesPanel snapshot={snapshot} />

      <HealthPanel snapshot={snapshot} />

      {/* Events log */}
      {(snapshot.learning_events ?? []).length > 0 && (
        <Panel title="系统事件" icon="clock">
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {(snapshot.learning_events ?? []).slice(0, 30).map((event, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <span className="text-slate-400 dark:text-slate-500 flex-shrink-0 tabular-nums">{localTime(event.at_utc)}</span>
                <span className={`flex-shrink-0 px-1.5 py-0.5 rounded text-xs ${
                  event.severity === "error" || event.severity === "blocked" ? "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300" :
                  event.severity === "warning" ? "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300" :
                  "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300"
                }`}>{event.severity ?? "info"}</span>
                <span className="text-slate-600 dark:text-slate-300"><strong>{event.title}</strong> {readableEventDetail(event.detail ?? "")}</span>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}


// ─── App root ─────────────────────────────────────────────────────────────────

export function App() {
  const [route, setRoute] = useState<DashboardRoute>(() => currentDashboardRoute());
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshingCount, setRefreshingCount] = useState(0);
  const refreshing = refreshingCount > 0;
  const [selectedLedgerId, setSelectedLedgerId] = useState<string | null>(null);
  const [detail, setDetail] = useState<DashboardMatchDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<DashboardSectionKey>(
    () => route.page === "dashboard" ? route.section : "overview",
  );
  const [darkMode, setDarkMode] = useDarkMode();
  const { toasts, dismiss, push } = useToasts();
  const prevPickCount = useRef<number | null>(null);
  const [validationActionJobId, setValidationActionJobId] = useState<string | null>(null);
  const dashboardPollInterval = dashboardPollIntervalMs(snapshot);
  const beginRefresh = useCallback(() => {
    setRefreshingCount((count) => nextRefreshActivityCount(count, 1));
    return () => setRefreshingCount((count) => nextRefreshActivityCount(count, -1));
  }, []);

  // Route sync
  useEffect(() => {
    const syncRoute = () => {
      const nextRoute = currentDashboardRoute();
      setRoute(nextRoute);
      if (nextRoute.page === "dashboard") {
        setActiveSection(nextRoute.section);
      }
    };
    window.addEventListener("popstate", syncRoute);
    return () => window.removeEventListener("popstate", syncRoute);
  }, []);

  function navigateToDashboard() {
    window.history.pushState(null, "", dashboardPath(activeSection));
    setRoute({ page: "dashboard", section: activeSection });
  }

  function navigateToSection(section: DashboardSectionKey) {
    window.history.pushState(null, "", dashboardPath(section));
    setActiveSection(section);
    setRoute({ page: "dashboard", section });
  }

  function navigateToMatch(ledgerId: string) {
    window.history.pushState(null, "", matchDetailPath(ledgerId));
    setSelectedLedgerId(ledgerId);
    setRoute({ page: "match", ledgerId });
  }

  const detailLedgerId = route.page === "match" ? route.ledgerId : null;

  // Main data polling — retry/backoff, AbortController mutex, visibility-aware
  useEffect(() => {
    const poller = createPoller<DashboardSnapshot>(
      async ({ signal }) => {
        const finishRefresh = beginRefresh();
        try {
          return await withRetry(() => fetchDashboardSnapshot({ signal }), {
            retries: 2,
            baseDelayMs: 1000,
            maxDelayMs: 8000,
            signal,
          });
        } finally {
          finishRefresh();
        }
      },
      {
        intervalMs: dashboardPollInterval,
        onResult: (data) => {
          setSnapshot(() => {
            const newCount = data.asian_picks?.length ?? 0;
            if (prevPickCount.current !== null && newCount > (prevPickCount.current ?? 0)) {
              push(`新增 ${newCount - prevPickCount.current!} 个推荐信号`, "success");
            }
            prevPickCount.current = newCount;
            return data;
          });
          setError(null);
          setLoading(false);
        },
        onError: (err) => {
          const message = err instanceof Error ? err.message : String(err);
          setError(message);
          setLoading(false);
          reportError(err, { kind: "dashboard-fetch" });
        },
      }
    );
    poller.start();
    return () => poller.stop();
  }, [push, dashboardPollInterval, beginRefresh]);

  // Detail loader — AbortController on dependency change
  useEffect(() => {
    if (!detailLedgerId) {
      setDetail(null);
      setDetailError(null);
      setDetailLoading(false);
      return;
    }
    const controller = new AbortController();
    let cancelled = false;
    setDetailLoading(true);
    setDetailError(null);
    setDetail((cur) => (cur?.record.ledger_id === detailLedgerId ? cur : null));
    fetchMatchDetail(detailLedgerId, { signal: controller.signal })
      .then((data) => {
        if (cancelled) return;
        if (data.status !== "ok") {
          setDetail(null);
          setDetailError(data.status);
          return;
        }
        setDetail(data);
        setDetailError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof DOMException && err.name === "AbortError") return;
        setDetail(null);
        if (err instanceof HttpError) setDetailError(err.message);
        else setDetailError(err instanceof Error ? err.message : String(err));
        reportError(err, { kind: "match-detail-fetch", ledgerId: detailLedgerId });
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [detailLedgerId]);

  const view = useMemo(() => snapshot ? buildDashboardView(snapshot) : null, [snapshot]);
  const isMatchPage = route.page === "match";

  async function refreshSnapshotOnce(contextKind: string, opts: { forceRefresh?: boolean } = {}) {
    const finishRefresh = beginRefresh();
    try {
      const data = await fetchDashboardSnapshot({ forceRefresh: opts.forceRefresh });
      setSnapshot(data);
      setError(null);
      return data;
    } catch (err) {
      const message = readableError(err);
      setError(message);
      reportError(err, { kind: contextKind });
      push(`刷新失败：${message}`, "warning");
      return null;
    } finally {
      finishRefresh();
    }
  }

  async function handleCancelValidationJob(jobId: string) {
    setValidationActionJobId(jobId);
    try {
      await cancelHoldoutValidationJob(jobId);
      push("Holdout 验证已取消", "warning");
      await refreshSnapshotOnce("holdout-validation-cancel-refresh", { forceRefresh: true });
    } catch (err) {
      push(`取消失败：${readableError(err)}`, "error");
      reportError(err, { kind: "holdout-validation-cancel", jobId });
    } finally {
      setValidationActionJobId(null);
    }
  }

  async function handleRetryValidationJob(jobId: string) {
    setValidationActionJobId(jobId);
    try {
      await retryHoldoutValidationJob(jobId);
      push("Holdout 验证已重新入队", "success");
      await refreshSnapshotOnce("holdout-validation-retry-refresh", { forceRefresh: true });
    } catch (err) {
      push(`重试失败：${readableError(err)}`, "error");
      reportError(err, { kind: "holdout-validation-retry", jobId });
    } finally {
      setValidationActionJobId(null);
    }
  }

  async function handleStartValidationJob() {
    setValidationActionJobId("holdout-new");
    try {
      await startHoldoutValidationJob({ resume: true, start: true });
      push("Holdout 验证已入队", "success");
      await refreshSnapshotOnce("holdout-validation-start-refresh", { forceRefresh: true });
    } catch (err) {
      push(`启动失败：${readableError(err)}`, "error");
      reportError(err, { kind: "holdout-validation-start" });
    } finally {
      setValidationActionJobId(null);
    }
  }

  async function handleStartQuickValidationJob() {
    setValidationActionJobId("holdout-quick");
    try {
      await startHoldoutValidationJob(QUICK_HOLDOUT_VALIDATION_REQUEST);
      push("快速诊断已入队：用于检查执行链路，不代表生产验证结论", "success");
      await refreshSnapshotOnce("holdout-validation-quick-start-refresh", { forceRefresh: true });
    } catch (err) {
      push(`快速诊断启动失败：${readableError(err)}`, "error");
      reportError(err, { kind: "holdout-validation-quick-start" });
    } finally {
      setValidationActionJobId(null);
    }
  }

  async function handleManualDashboardRefresh() {
    const data = await refreshSnapshotOnce("manual-dashboard-refresh", { forceRefresh: true });
    if (data) {
      push("看板已强制刷新", "success");
    }
  }

  return (
    <div className={`min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white`}>
      <TopBar
        snapshot={snapshot}
        darkMode={darkMode}
        onToggleDark={() => setDarkMode((d) => !d)}
        onRefresh={handleManualDashboardRefresh}
        refreshing={refreshing}
        lastRefreshError={error}
      />

      <ToastContainer toasts={toasts} onDismiss={dismiss} />

      {isMatchPage ? (
        <Suspense fallback={<LoadingSpinner label="加载比赛页面..." />}>
          <MatchDetailPage
            ledgerId={route.ledgerId}
            detail={detail}
            loading={detailLoading}
            error={detailError}
            onBack={navigateToDashboard}
          />
        </Suspense>
      ) : (
        <div className="flex max-w-screen-2xl mx-auto">
          {/* Sidebar (desktop) */}
          <Sidebar active={activeSection} onChange={navigateToSection} />

          {/* Main content */}
          <main className="flex-1 min-w-0 px-3 sm:px-4 py-3 pb-20 lg:pb-4">
            {error && (
              <div className="mb-3 rounded-lg border border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 px-3 py-2 text-xs text-amber-800 dark:text-amber-200 flex items-center gap-2">
                <Icon name="warn" size={12} />
                数据刷新失败：{error}。显示最近快照。
              </div>
            )}

            {loading && !snapshot && (
              <div className="flex flex-col gap-4">
                {[1, 2, 3].map((i) => <SkeletonCard key={i} lines={4} />)}
              </div>
            )}

            {snapshot && view && (
              <>
                {activeSection === "overview" && (
                  <OverviewSection
                    snapshot={snapshot}
                    view={view}
                    onSelectRecommendation={(r) => navigateToMatch(`recommendation:${r.id}`)}
                  />
                )}
                {activeSection === "production" && <ProductionSection view={view} />}
                {activeSection === "model" && (
                  <ModelSection
                    view={view}
                    snapshot={snapshot}
                    validationActionJobId={validationActionJobId}
                    onCancelValidationJob={handleCancelValidationJob}
                    onRetryValidationJob={handleRetryValidationJob}
                    onStartValidationJob={handleStartValidationJob}
                    onStartQuickValidationJob={handleStartQuickValidationJob}
                  />
                )}
                {activeSection === "signals" && (
                  <SignalsSection
                    snapshot={snapshot}
                    view={view}
                    onSelectLedger={navigateToMatch}
                    onSelectRecommendation={(r) => navigateToMatch(`recommendation:${r.id}`)}
                  />
                )}
                {activeSection === "data" && <DataSection snapshot={snapshot} view={view} />}

                <footer className="mt-6 text-[10px] text-slate-400 dark:text-slate-600 text-center py-3 border-t border-slate-100 dark:border-slate-800">
                  只读监控台 · 不执行交易动作
                </footer>
              </>
            )}
          </main>
        </div>
      )}

      {/* Bottom nav (mobile) */}
      {!isMatchPage && <BottomNav active={activeSection} onChange={navigateToSection} />}
    </div>
  );
}

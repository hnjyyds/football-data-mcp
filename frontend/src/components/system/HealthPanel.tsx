import { Icon } from "../shared/Icon";
import type { DashboardSnapshot, OddsSourceStatusEntry, SourceHealthEntry } from "../../types";

function StatusIcon({ status }: { status: string | null | undefined }) {
  if (["ok", "fresh", "live", "succeeded", "success", "snapshot_available", "ready"].includes(status ?? "")) {
    return <Icon name="success" size={14} className="text-success-500 flex-shrink-0" />;
  }
  if (
    [
      "stale",
      "degraded",
      "partial",
      "queued",
      "running",
      "empty",
      "no_snapshots",
      "retryable",
      "needs_input",
      "needs_access",
      "needs_config",
      "derived_fallback",
      "stale_derived",
    ].includes(status ?? "")
  ) {
    return <Icon name="warn" size={14} className="text-warning-500 flex-shrink-0" />;
  }
  return <Icon name="error" size={14} className="text-danger-500 flex-shrink-0" />;
}

type ProviderSpec = {
  key: string;
  label: string;
  detail: (entry: SourceHealthEntry) => string | undefined;
};

const PROVIDERS: ProviderSpec[] = [
  {
    key: "football_data",
    label: "Football-Data",
    detail: (e) => (typeof e.fixture_count === "number" ? `${e.fixture_count} 赛事` : undefined),
  },
  {
    key: "leisu",
    label: "雷速",
    detail: (e) => (typeof e.reason === "string" ? e.reason : (typeof e.error === "string" ? e.error : undefined)),
  },
  {
    key: "dongqiudi",
    label: "东球汇",
    detail: (e) => (typeof e.match_count === "number" ? `${e.match_count} 场` : undefined),
  },
  {
    key: "the_odds_api",
    label: "The Odds API",
    detail: () => undefined,
  },
];

const ODDS_SOURCE_LABELS: Record<string, string> = {
  leisu: "雷速赔率",
  oddsportal_scraper: "OddsPortal 爬虫",
  the_odds_api: "The Odds API",
  analysis_odds: "分析快照",
};

const ODDS_STATUS_LABELS: Record<string, string> = {
  succeeded: "最近成功",
  success: "最近成功",
  snapshot_available: "有快照",
  queued: "已入队",
  running: "抓取中",
  retryable: "可续跑",
  available: "可用",
  ready: "已就绪",
  stale: "已过期",
  fresh: "新鲜",
  needs_input: "待输入 URL",
  needs_access: "待配置访问",
  needs_config: "待配置",
  derived_only: "仅兜底",
  derived_fallback: "分析兜底",
  stale_derived: "兜底过期",
  failed: "抓取失败",
  error: "抓取失败",
  empty: "无快照",
  no_snapshots: "无快照",
  session_ready: "会话就绪",
  needs_auth: "待人工验证",
};

function oddsSourceDetail(key: string, entry: OddsSourceStatusEntry): string {
  const statusKey = entry.operational_status || entry.status;
  const statusText = ODDS_STATUS_LABELS[statusKey] ?? statusKey;
  const syncStatus = entry.sync?.latest_status ? (ODDS_STATUS_LABELS[entry.sync.latest_status] ?? entry.sync.latest_status) : statusText;
  const count = entry.snapshot_count || entry.sync?.snapshot_count || 0;
  const snapshotText = key === "oddsportal_scraper" ? `${count} 条亚盘快照` : `${count} 条快照`;
  if (key === "oddsportal_scraper") {
    const activeCount = (entry.queued_count || 0) + (entry.running_count || 0);
    const retryableCount = entry.retryable_url_count || 0;
    const actionText = activeCount > 0 ? `${activeCount} 个执行中` : retryableCount > 0 ? `${retryableCount} 个可续跑` : "可持续补充";
    const discoveryText =
      typeof entry.effective_discovery_url_count === "number"
        ? `发现页 ${entry.effective_discovery_url_count}`
        : "发现页 —";
    const targetCount = entry.discovery_target_count ?? entry.open_target_count;
    const sourceText =
      entry.discovery_target_source === "analysis_odds"
        ? "分析种子"
        : entry.discovery_target_source === "open_prediction"
          ? "open 台账"
          : "目标";
    const targetText = typeof targetCount === "number" ? `${sourceText} ${targetCount}` : "目标 —";
    const daemonText = entry.auto_sync_enabled ? "自动开" : "自动关";
    return `${snapshotText} · ${syncStatus} · ${actionText} · ${discoveryText} · ${targetText} · ${daemonText}`;
  }
  const freshnessText = entry.freshness_status ? (ODDS_STATUS_LABELS[entry.freshness_status] ?? entry.freshness_status) : "";
  return freshnessText ? `${snapshotText} · ${syncStatus} · ${freshnessText}` : `${snapshotText} · ${syncStatus}`;
}

function runtimeSupportDetail(entry: OddsSourceStatusEntry): string | undefined {
  const runtime = entry.runtime_support;
  if (!runtime) return undefined;
  const engine = runtime.engine === "crawlee_playwright" ? "Crawlee 路径" : runtime.engine || "运行时";
  const status = runtime.supported ? "可切换" : "未就绪";
  const message = typeof runtime.message === "string" ? runtime.message : "";
  return message ? `${engine} · ${status} · ${message}` : `${engine} · ${status}`;
}

function healthCardClass(status: string | null | undefined): string {
  if (["ok", "fresh", "live", "succeeded", "success", "snapshot_available", "ready"].includes(status ?? "")) {
    return "border-emerald-500/[0.16] bg-white/[0.66] dark:border-emerald-500/20 dark:bg-white/[0.035]";
  }
  if (
    [
      "stale",
      "degraded",
      "partial",
      "queued",
      "running",
      "empty",
      "no_snapshots",
      "retryable",
      "needs_input",
      "needs_access",
      "needs_config",
      "derived_fallback",
      "stale_derived",
    ].includes(status ?? "")
  ) {
    return "border-amber-500/20 bg-white/[0.66] dark:border-amber-500/25 dark:bg-white/[0.035]";
  }
  return "border-red-500/20 bg-white/[0.66] dark:border-red-500/25 dark:bg-white/[0.035]";
}

export function HealthPanel({ snapshot }: { snapshot: DashboardSnapshot }) {
  const health = snapshot.source_health ?? {};
  const sources: Array<{ name: string; status: string | null; detail?: string }> = [];
  const oddsSources: Array<{ name: string; status: string | null; detail?: string; nextAction?: string }> = [];

  for (const spec of PROVIDERS) {
    const entry = health[spec.key];
    if (!entry) continue;
    sources.push({
      name: spec.label,
      status: entry.status ?? null,
      detail: spec.detail(entry),
    });
  }

  const oddsStatus = snapshot.odds_source_status;
  const closure = oddsStatus?.closure;
  const activeOddsSource = closure?.active_source ? (ODDS_SOURCE_LABELS[closure.active_source] ?? closure.active_source) : "未选定";
  for (const [key, entry] of Object.entries(oddsStatus?.sources ?? {})) {
    oddsSources.push({
      name: ODDS_SOURCE_LABELS[key] ?? key,
      status: entry.operational_status ?? entry.status ?? null,
      detail: oddsSourceDetail(key, entry),
      nextAction: entry.next_action,
    });
  }

  if (!sources.length && !oddsSources.length) return null;

  return (
    <div className="surface-panel p-4">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div>
          <div className="section-kicker">Source Health</div>
          <div className="mt-1 text-sm font-semibold text-ink-950 dark:text-white">数据源健康</div>
        </div>
        {oddsStatus?.policy?.fallback_rule && (
          <div className="text-[11px] text-ink-500 dark:text-ink-400 truncate">
            雷速不稳时启用赔率快照补位
          </div>
        )}
      </div>
      {sources.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {sources.map((s) => (
            <div key={s.name} className={`flex items-start gap-2 rounded-xl border p-2.5 ${healthCardClass(s.status)}`}>
              <StatusIcon status={s.status} />
              <div>
                <div className="text-xs font-semibold text-ink-800 dark:text-ink-200">{s.name}</div>
                {s.detail && <div className="text-xs text-ink-500 dark:text-ink-400">{s.detail}</div>}
              </div>
            </div>
          ))}
        </div>
      )}
      {oddsSources.length > 0 && (
        <div className="mt-3">
          <div className="flex items-center justify-between gap-3 mb-2">
            <div className="text-xs font-semibold text-ink-700 dark:text-ink-300">赔率源闭环</div>
            {closure && (
              <div className="flex items-center gap-1.5 text-[11px] text-ink-500 dark:text-ink-400">
                <StatusIcon status={closure.production_ready ? "ok" : "stale"} />
                <span>
                  当前：{activeOddsSource} · {closure.production_ready ? "生产可用" : "仅观察/兜底"}
                </span>
              </div>
            )}
          </div>
          {closure?.reason && (
            <div className="mb-2 rounded-xl border border-amber-500/20 bg-amber-50/60 px-2.5 py-2 text-[11px] leading-snug text-amber-900 dark:bg-amber-950/[0.18] dark:text-amber-100">
              {closure.reason}
            </div>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
            {oddsSources.map((s) => (
              <div key={s.name} className={`flex items-start gap-2 rounded-xl border p-2.5 ${healthCardClass(s.status)}`}>
                <StatusIcon status={s.status} />
                <div>
                  <div className="text-xs font-semibold text-ink-800 dark:text-ink-200">{s.name}</div>
                  {s.detail && <div className="text-xs text-ink-500 dark:text-ink-400">{s.detail}</div>}
                  {s.name === "雷速赔率" && oddsStatus?.sources?.leisu?.runtime_support && (
                    <div className="mt-1 text-[11px] leading-snug text-ink-500 dark:text-ink-400">
                      {runtimeSupportDetail(oddsStatus.sources.leisu)}
                    </div>
                  )}
                  {s.name === "雷速赔率" && oddsStatus?.sources?.leisu?.runtime_support?.recommended_entrypoint && (
                    <div className="mt-1 text-[11px] leading-snug text-ink-500 dark:text-ink-400 break-all">
                      命令：{oddsStatus.sources.leisu.runtime_support.recommended_entrypoint}
                    </div>
                  )}
                  {s.nextAction && (
                    <div className="mt-1 text-[11px] leading-snug text-ink-500 dark:text-ink-400 line-clamp-2">
                      下一步：{s.nextAction}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

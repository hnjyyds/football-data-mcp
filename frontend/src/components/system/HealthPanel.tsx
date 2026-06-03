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
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm p-4">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="font-semibold text-slate-900 dark:text-white text-sm">数据源健康</div>
        {oddsStatus?.policy?.fallback_rule && (
          <div className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
            雷速不稳时启用赔率快照补位
          </div>
        )}
      </div>
      {sources.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {sources.map((s) => (
            <div key={s.name} className="flex items-start gap-2 p-2 rounded-lg bg-slate-50 dark:bg-slate-700/40">
              <StatusIcon status={s.status} />
              <div>
                <div className="text-xs font-medium text-slate-800 dark:text-slate-200">{s.name}</div>
                {s.detail && <div className="text-xs text-slate-500 dark:text-slate-400">{s.detail}</div>}
              </div>
            </div>
          ))}
        </div>
      )}
      {oddsSources.length > 0 && (
        <div className="mt-3">
          <div className="flex items-center justify-between gap-3 mb-2">
            <div className="text-xs font-semibold text-slate-700 dark:text-slate-300">赔率源闭环</div>
            {closure && (
              <div className="flex items-center gap-1.5 text-[11px] text-slate-500 dark:text-slate-400">
                <StatusIcon status={closure.production_ready ? "ok" : "stale"} />
                <span>
                  当前：{activeOddsSource} · {closure.production_ready ? "生产可用" : "仅观察/兜底"}
                </span>
              </div>
            )}
          </div>
          {closure?.reason && (
            <div className="mb-2 rounded-lg border border-amber-100 bg-amber-50/70 px-2.5 py-2 text-[11px] leading-snug text-slate-600 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-slate-300">
              {closure.reason}
            </div>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
            {oddsSources.map((s) => (
              <div key={s.name} className="flex items-start gap-2 p-2 rounded-lg bg-emerald-50/70 dark:bg-emerald-950/20 border border-emerald-100 dark:border-emerald-900/40">
                <StatusIcon status={s.status} />
                <div>
                  <div className="text-xs font-medium text-slate-800 dark:text-slate-200">{s.name}</div>
                  {s.detail && <div className="text-xs text-slate-500 dark:text-slate-400">{s.detail}</div>}
                  {s.nextAction && (
                    <div className="mt-1 text-[11px] leading-snug text-slate-500 dark:text-slate-400 line-clamp-2">
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

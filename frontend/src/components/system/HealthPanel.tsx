import { Icon } from "../shared/Icon";
import type { DashboardSnapshot, SourceHealthEntry } from "../../types";

function StatusIcon({ status }: { status: string | null | undefined }) {
  if (status === "ok" || status === "fresh" || status === "live") {
    return <Icon name="success" size={14} className="text-success-500 flex-shrink-0" />;
  }
  if (status === "stale" || status === "degraded" || status === "partial") {
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

export function HealthPanel({ snapshot }: { snapshot: DashboardSnapshot }) {
  const health = snapshot.source_health ?? {};
  const sources: Array<{ name: string; status: string | null; detail?: string }> = [];

  for (const spec of PROVIDERS) {
    const entry = health[spec.key];
    if (!entry) continue;
    sources.push({
      name: spec.label,
      status: entry.status ?? null,
      detail: spec.detail(entry),
    });
  }

  if (!sources.length) return null;

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm p-4">
      <div className="font-semibold text-slate-900 dark:text-white text-sm mb-3">数据源健康</div>
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
    </div>
  );
}

import { Icon } from "../shared/Icon";
import type { DashboardSnapshot } from "../../types";

function StatusIcon({ status }: { status: string | null | undefined }) {
  if (status === "ok" || status === "fresh" || status === "live") {
    return <Icon name="success" size={14} className="text-success-500 flex-shrink-0" />;
  }
  if (status === "stale" || status === "degraded" || status === "partial") {
    return <Icon name="warn" size={14} className="text-warning-500 flex-shrink-0" />;
  }
  return <Icon name="error" size={14} className="text-danger-500 flex-shrink-0" />;
}

export function HealthPanel({ snapshot }: { snapshot: DashboardSnapshot }) {
  const health = (snapshot as any).source_health ?? (snapshot as any).decision_audit?.source_audit ?? {};
  const sources: Array<{ name: string; status: string | null; detail?: string }> = [];

  // Build from known patterns
  const footballData = (health.football_data ?? health.football_data_co_uk) as any;
  if (footballData) {
    sources.push({ name: "Football-Data", status: footballData.status, detail: footballData.fixture_count ? `${footballData.fixture_count} 赛事` : undefined });
  }
  const leisu = health.leisu as any;
  if (leisu) {
    sources.push({ name: "雷速", status: leisu.status, detail: leisu.reason });
  }
  const dongqiudi = (health.dongqiudi ?? health.dongqiudi_schedule) as any;
  if (dongqiudi) {
    sources.push({ name: "东球汇", status: dongqiudi.status, detail: dongqiudi.match_count ? `${dongqiudi.match_count} 场` : undefined });
  }
  const theOddsApi = (health.the_odds_api ?? health.odds_api) as any;
  if (theOddsApi) {
    sources.push({ name: "The Odds API", status: theOddsApi.status });
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

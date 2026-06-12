import { Icon } from "../shared/Icon";
import type { DashboardSnapshot } from "../../types";
import { BrandLogo } from "../shared/BrandLogo";

function localTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(d);
}

function relativeTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  const diffSec = Math.round((Date.now() - d.getTime()) / 1000);
  if (diffSec < 60) return `${diffSec}s`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m`;
  return `${Math.floor(diffSec / 3600)}h`;
}

export function TopBar({
  snapshot,
  darkMode,
  onToggleDark,
  onRefresh,
  refreshing,
  lastRefreshError,
}: {
  snapshot: DashboardSnapshot | null;
  darkMode: boolean;
  onToggleDark: () => void;
  onRefresh?: () => void;
  refreshing: boolean;
  lastRefreshError: string | null;
}) {
  const isCalibrationActive = snapshot?.kpis.live_calibration_active;
  const cacheStatus = snapshot?.dashboard_cache?.status;
  const isStaleRefreshing = cacheStatus === "stale_refreshing";
  const openPredictions = snapshot?.prediction_kpis.open_count ?? 0;
  const roi = snapshot?.prediction_kpis.roi;
  const roiText = roi == null ? "ROI —" : `ROI ${roi >= 0 ? "+" : ""}${(roi * 100).toFixed(1)}%`;
  const signalText = openPredictions > 0 ? `${openPredictions} 开放预测` : "无开放预测";
  return (
    <header className="sticky top-0 z-40 border-b border-[hsl(var(--border))] bg-[hsl(var(--background))]/90 backdrop-blur-xl">
      <div className="max-w-screen-2xl mx-auto px-3 sm:px-4 h-12 flex items-center gap-2 sm:gap-4">
        {/* Brand */}
        <div className="flex items-center gap-2 mr-auto min-w-0">
          <BrandLogo size={24} />
        </div>

        {/* Live status */}
        <div className="flex items-center gap-1.5 sm:gap-2 text-xs">
          {lastRefreshError ? (
            <span className="hidden sm:flex items-center gap-1 px-2 py-1 rounded-md bg-danger-500/10 text-danger-600 dark:text-danger-500 text-2xs font-medium">
              <Icon name="alert" size={10} />
              刷新失败
            </span>
          ) : (
            <span className="hidden sm:flex items-center gap-1.5 text-2xs">
              <span className="live-dot" />
              <span className="text-[hsl(var(--muted-foreground))] font-medium">LIVE</span>
            </span>
          )}
          <span className={`hidden md:flex items-center gap-1 px-2 py-1 rounded-md text-2xs font-medium ${
            isCalibrationActive
              ? "text-[hsl(var(--muted-foreground))]"
              : "text-amber-700 dark:text-amber-400"
          }`}>
            <Icon name="database" size={11} />
            {isCalibrationActive ? "实时校准" : "收集中"}
          </span>
          <span className={`hidden md:flex items-center gap-1 px-2 py-1 rounded-md text-2xs font-medium ${
            openPredictions > 0
              ? "text-[hsl(var(--foreground))]"
              : "text-[hsl(var(--muted-foreground))]"
          }`}>
            <Icon name="signals" size={11} />
            {signalText}
          </span>
          <span className={`hidden lg:flex items-center gap-1 px-2 py-1 rounded-md text-2xs font-medium tabular-nums ${
            roi != null && roi > 0
              ? "text-emerald-700 dark:text-emerald-400"
              : roi != null && roi < 0
                ? "text-[hsl(var(--destructive))]"
                : "text-[hsl(var(--muted-foreground))]"
          }`}>
            <Icon name={roi != null && roi < 0 ? "trendDown" : "trendUp"} size={11} />
            {roiText}
          </span>
          <span className="hidden sm:flex items-center gap-1 text-2xs text-[hsl(var(--muted-foreground))] tabular-nums">
            <Icon name="clock" size={11} />
            {snapshot ? localTime(snapshot.generated_at_utc) : "—"}
          </span>
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing || !onRefresh}
            aria-label="强制刷新看板"
            title="强制刷新看板"
            className="shadcn-button-ghost min-h-8 rounded-md px-2 py-1 text-2xs disabled:cursor-not-allowed"
          >
            <Icon name="refresh" size={11} className={refreshing ? "animate-spin text-[hsl(var(--foreground))]" : ""} />
            <span className="hidden lg:inline tabular-nums">{snapshot ? relativeTime(snapshot.generated_at_utc) : "—"}</span>
          </button>
          {isStaleRefreshing && (
            <span
              className="hidden md:flex items-center gap-1 rounded-md border border-[hsl(var(--border))] px-2 py-1 text-2xs font-medium text-[hsl(var(--muted-foreground))]"
              title="正在后台刷新 dashboard 快照"
            >
              <Icon name="refresh" size={11} className="animate-spin" />
              快照刷新中
            </span>
          )}
        </div>

        {/* Dark toggle */}
        <button
          type="button"
          onClick={onToggleDark}
          className="shadcn-button-ghost grid h-9 w-9 place-items-center rounded-md p-0"
          aria-label={darkMode ? "切换浅色模式" : "切换深色模式"}
        >
          <Icon name={darkMode ? "sun" : "moon"} size={15} />
        </button>
      </div>
    </header>
  );
}

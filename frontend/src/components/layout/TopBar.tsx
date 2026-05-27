import { Icon } from "../shared/Icon";
import type { DashboardSnapshot } from "../../types";
import { BrandLogo, BrandWordmark } from "../shared/BrandLogo";

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
  refreshing,
  lastRefreshError,
}: {
  snapshot: DashboardSnapshot | null;
  darkMode: boolean;
  onToggleDark: () => void;
  refreshing: boolean;
  lastRefreshError: string | null;
}) {
  const isCalibrationActive = snapshot?.kpis.live_calibration_active;
  return (
    <header className="sticky top-0 z-40 bg-white/95 dark:bg-ink-950/95 backdrop-blur-md border-b border-ink-200 dark:border-ink-800">
      <div className="max-w-screen-2xl mx-auto px-3 sm:px-4 h-12 flex items-center gap-2 sm:gap-4">
        {/* Brand */}
        <div className="flex items-center gap-2 mr-auto min-w-0">
          <BrandLogo size={26} glow />
          <div className="hidden sm:block min-w-0">
            <BrandWordmark className="text-base leading-none" />
            <div className="text-2xs text-ink-500 dark:text-ink-500 leading-none mt-0.5">足球策略控制台</div>
          </div>
        </div>

        {/* Live status */}
        <div className="flex items-center gap-1.5 sm:gap-3 text-xs">
          {lastRefreshError ? (
            <span className="hidden sm:flex items-center gap-1 px-2 py-1 rounded-md bg-danger-500/10 text-danger-600 dark:text-danger-500 text-2xs font-medium">
              <Icon name="alert" size={11} />
              刷新失败
            </span>
          ) : (
            <span className="hidden sm:flex items-center gap-1.5 text-2xs">
              <span className="live-dot" />
              <span className="text-ink-600 dark:text-ink-400 font-medium">LIVE</span>
            </span>
          )}
          <span className={`hidden md:flex items-center gap-1 px-2 py-1 rounded-md text-2xs font-medium ${
            isCalibrationActive
              ? "bg-success-500/10 text-success-700 dark:text-success-500"
              : "bg-warning-500/10 text-warning-700 dark:text-warning-500"
          }`}>
            <Icon name="database" size={11} />
            {isCalibrationActive ? "实时校准" : "收集中"}
          </span>
          <span className="hidden sm:flex items-center gap-1 text-2xs text-ink-500 dark:text-ink-400 tabular-nums font-mono">
            <Icon name="clock" size={11} />
            {snapshot ? localTime(snapshot.generated_at_utc) : "—"}
          </span>
          <span className="flex items-center gap-1 text-2xs text-ink-500 dark:text-ink-400">
            <Icon name="refresh" size={11} className={refreshing ? "animate-spin text-brand-500" : ""} />
            <span className="hidden lg:inline tabular-nums">{snapshot ? relativeTime(snapshot.generated_at_utc) : "—"}</span>
          </span>
        </div>

        {/* Dark toggle */}
        <button
          type="button"
          onClick={onToggleDark}
          className="p-1.5 rounded-lg text-ink-500 dark:text-ink-400 hover:bg-ink-100 dark:hover:bg-ink-800 hover:text-brand-600 dark:hover:text-brand-400 transition-colors"
          aria-label={darkMode ? "切换浅色模式" : "切换深色模式"}
        >
          <Icon name={darkMode ? "sun" : "moon"} size={15} />
        </button>
      </div>
    </header>
  );
}

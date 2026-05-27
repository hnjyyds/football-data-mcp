import { Database, Clock, RefreshCw, Moon, Sun, Activity } from "lucide-react";
import type { DashboardSnapshot } from "../../types";

function localTime(value: string | null | undefined): string {
  if (!value) return "加载中";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
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
    <header className="sticky top-0 z-40 bg-white/90 dark:bg-slate-900/90 backdrop-blur border-b border-slate-200 dark:border-slate-700/60">
      <div className="max-w-screen-2xl mx-auto px-4 h-14 flex items-center gap-3">
        {/* Logo */}
        <div className="flex items-center gap-2 mr-auto">
          <Activity size={18} className="text-blue-500" />
          <span className="font-semibold text-slate-900 dark:text-white text-sm hidden sm:block">足球策略控制台</span>
          <span className="font-semibold text-slate-900 dark:text-white text-sm sm:hidden">策略台</span>
        </div>

        {/* Status chips */}
        <div className="hidden md:flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
          {lastRefreshError && (
            <span className="text-red-500 dark:text-red-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
              刷新失败
            </span>
          )}
          <span className="flex items-center gap-1">
            <Database size={13} />
            <span className={isCalibrationActive ? "text-emerald-600 dark:text-emerald-400" : ""}>
              {isCalibrationActive ? "实时校准" : "收集中"}
            </span>
          </span>
          <span className="flex items-center gap-1">
            <Clock size={13} />
            {snapshot ? localTime(snapshot.generated_at_utc) : "—"}
          </span>
          <span className="flex items-center gap-1">
            <RefreshCw size={13} className={refreshing ? "animate-spin" : ""} />
            30s 刷新
          </span>
        </div>

        {/* Dark mode toggle */}
        <button
          type="button"
          onClick={onToggleDark}
          className="p-2 rounded-lg text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          aria-label={darkMode ? "切换浅色模式" : "切换深色模式"}
        >
          {darkMode ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </div>
    </header>
  );
}

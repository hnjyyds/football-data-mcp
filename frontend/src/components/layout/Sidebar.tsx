import { Target, Rocket, Gauge, TrendingUp, Database } from "lucide-react";
import type { DashboardSectionKey } from "../../types";

const SECTIONS: Array<{ key: DashboardSectionKey; label: string; icon: typeof Target; shortLabel: string }> = [
  { key: "overview",    label: "总览",    shortLabel: "总览",    icon: Target },
  { key: "production",  label: "上线",    shortLabel: "上线",    icon: Rocket },
  { key: "model",       label: "模型",    shortLabel: "模型",    icon: Gauge },
  { key: "signals",     label: "信号",    shortLabel: "信号",    icon: TrendingUp },
  { key: "data",        label: "数据",    shortLabel: "数据",    icon: Database },
];

export function Sidebar({
  active,
  onChange,
  badges,
}: {
  active: DashboardSectionKey;
  onChange: (key: DashboardSectionKey) => void;
  badges?: Partial<Record<DashboardSectionKey, string>>;
}) {
  return (
    <aside className="hidden lg:flex flex-col w-16 xl:w-48 flex-shrink-0 border-r border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-900 py-4 gap-1">
      {SECTIONS.map(({ key, label, shortLabel, icon: Icon }) => {
        const isActive = active === key;
        const badge = badges?.[key];
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            aria-pressed={isActive}
            className={`flex items-center gap-3 px-3 py-2.5 mx-2 rounded-lg text-sm transition-colors text-left ${
              isActive
                ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
            }`}
          >
            <Icon size={18} className="flex-shrink-0" />
            <span className="hidden xl:block flex-1">{label}</span>
            <span className="hidden xl:block xl:hidden flex-1">{shortLabel}</span>
            {badge && (
              <span className="hidden xl:block text-xs px-1.5 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 font-medium">
                {badge}
              </span>
            )}
          </button>
        );
      })}
    </aside>
  );
}

export function BottomNav({
  active,
  onChange,
}: {
  active: DashboardSectionKey;
  onChange: (key: DashboardSectionKey) => void;
}) {
  return (
    <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-40 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-700/60 flex">
      {SECTIONS.map(({ key, label, icon: Icon }) => {
        const isActive = active === key;
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            aria-pressed={isActive}
            className={`flex-1 flex flex-col items-center justify-center py-2 gap-0.5 text-xs transition-colors ${
              isActive
                ? "text-blue-600 dark:text-blue-400"
                : "text-slate-500 dark:text-slate-400"
            }`}
          >
            <Icon size={20} />
            <span>{label}</span>
          </button>
        );
      })}
    </nav>
  );
}

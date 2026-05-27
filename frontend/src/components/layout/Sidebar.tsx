import { Icon, type IconName } from "../shared/Icon";
import type { DashboardSectionKey } from "../../types";

const SECTIONS: Array<{ key: DashboardSectionKey; label: string; icon: IconName }> = [
  { key: "overview",    label: "总览",    icon: "overview" },
  { key: "production",  label: "上线",    icon: "production" },
  { key: "model",       label: "模型",    icon: "model" },
  { key: "signals",     label: "信号",    icon: "signals" },
  { key: "data",        label: "数据",    icon: "data" },
];

export function Sidebar({
  active,
  onChange,
  badges,
}: {
  active: DashboardSectionKey;
  onChange: (key: DashboardSectionKey) => void;
  badges?: Partial<Record<DashboardSectionKey, string | number>>;
}) {
  return (
    <aside className="hidden lg:flex flex-col w-14 flex-shrink-0 border-r border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-900 py-3 gap-0.5">
      {SECTIONS.map(({ key, label, icon }) => {
        const isActive = active === key;
        const badge = badges?.[key];
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            aria-pressed={isActive}
            title={label}
            className={`relative flex flex-col items-center justify-center py-2.5 mx-1.5 rounded-lg text-xs transition-all duration-150 ${
              isActive
                ? "bg-brand-50 dark:bg-brand-900/30 text-brand-700 dark:text-brand-300"
                : "text-ink-500 dark:text-ink-400 hover:bg-ink-100 dark:hover:bg-ink-800 hover:text-brand-600 dark:hover:text-brand-400"
            }`}
          >
            <Icon name={icon} size={18} />
            <span className="mt-1 text-[10px] leading-none">{label}</span>
            {badge != null && (
              <span className="absolute top-1 right-1 min-w-[16px] h-4 px-1 flex items-center justify-center text-[9px] rounded-full bg-strike-500 text-white font-medium leading-none">
                {badge}
              </span>
            )}
            {isActive && (
              <span className="absolute left-0 top-1/4 bottom-1/4 w-0.5 rounded-r-full bg-brand-500" />
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
    <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-40 bg-white dark:bg-ink-900 border-t border-ink-200 dark:border-ink-800 flex shadow-lg">
      {SECTIONS.map(({ key, label, icon }) => {
        const isActive = active === key;
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            aria-pressed={isActive}
            className={`flex-1 flex flex-col items-center justify-center py-2 gap-0.5 text-xs transition-colors ${
              isActive
                ? "text-brand-600 dark:text-brand-400"
                : "text-ink-500 dark:text-ink-400"
            }`}
          >
            <Icon name={icon} size={18} />
            <span className="text-[10px]">{label}</span>
          </button>
        );
      })}
    </nav>
  );
}

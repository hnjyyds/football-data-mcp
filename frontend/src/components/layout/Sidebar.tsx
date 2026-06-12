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
    <aside className="hidden lg:flex flex-col w-14 xl:w-40 flex-shrink-0 py-3 gap-0.5">
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
            className={`focusable-control relative mx-1.5 flex min-h-10 items-center justify-center xl:justify-start gap-2 rounded-md px-2 py-2 text-xs transition-colors ${
              isActive
                ? "bg-[hsl(var(--foreground))] text-[hsl(var(--background))]"
                : "text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))]"
            }`}
          >
            <Icon name={icon} size={16} className="shrink-0" />
            <span className="hidden xl:inline text-sm font-normal">{label}</span>
            <span className="xl:hidden mt-0.5 text-[10px] leading-none">{label}</span>
            {badge != null && (
              <span className="absolute top-1 right-1 xl:right-2 min-w-[16px] h-4 px-1 flex items-center justify-center text-[9px] rounded-full bg-[hsl(var(--destructive))] text-[hsl(var(--destructive-foreground))] font-medium leading-none">
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
    <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-40 bg-[hsl(var(--background))]/95 border-t border-[hsl(var(--border))] flex backdrop-blur">
      {SECTIONS.map(({ key, label, icon }) => {
        const isActive = active === key;
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            aria-pressed={isActive}
            className={`focusable-control flex-1 flex min-h-14 flex-col items-center justify-center py-2 gap-0.5 text-xs transition-colors ${
              isActive
                ? "text-[hsl(var(--foreground))]"
                : "text-[hsl(var(--muted-foreground))]"
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

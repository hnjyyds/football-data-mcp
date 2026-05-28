import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";
import { Badge } from "./Badge";

export function Panel({
  title,
  icon,
  children,
  className = "",
  badge,
  dense = false,
}: {
  title?: string;
  icon?: IconName;
  children: ReactNode;
  className?: string;
  badge?: string;
  dense?: boolean;
}) {
  return (
    <section className={`rounded-xl border border-ink-200 dark:border-ink-700 bg-white dark:bg-ink-800 shadow-sm overflow-hidden ${className}`}>
      {title && (
        <div className={`flex items-center gap-2 ${dense ? "px-3 py-2" : "px-4 py-3"} border-b border-ink-100 dark:border-ink-700/50`}>
          {icon && <Icon name={icon} size={14} className="text-ink-500 dark:text-ink-400" />}
          <span className="font-semibold text-ink-900 dark:text-white text-sm flex-1">{title}</span>
          {badge && <Badge variant="neutral">{badge}</Badge>}
        </div>
      )}
      <div className={dense ? "p-3" : "p-4"}>{children}</div>
    </section>
  );
}

export function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-slate-500 dark:text-slate-400 mb-0.5">{label}</div>
      <div className="text-sm font-semibold text-slate-900 dark:text-white tabular-nums">{value}</div>
    </div>
  );
}

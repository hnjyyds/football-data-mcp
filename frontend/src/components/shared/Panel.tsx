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
    <section className={`surface-panel overflow-hidden ${className}`}>
      {title && (
        <div className={`flex items-center gap-2 ${dense ? "px-3 pt-3 pb-1" : "px-4 pt-4 pb-1"}`}>
          {icon && <Icon name={icon} size={14} className="text-ink-400 dark:text-ink-500" />}
          <span className="text-sm font-semibold text-ink-950 dark:text-white flex-1">{title}</span>
          {badge && <Badge variant="neutral">{badge}</Badge>}
        </div>
      )}
      <div className={dense ? "p-3" : "p-4"}>{children}</div>
    </section>
  );
}

export function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="metric-label mb-1 truncate">{label}</div>
      <div className="metric-value truncate">{value}</div>
    </div>
  );
}

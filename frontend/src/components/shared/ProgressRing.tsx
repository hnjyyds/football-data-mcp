export function ProgressRing({
  value,
  max = 1,
  size = 56,
  strokeWidth = 5,
  color = "#3b82f6",
  label,
  sublabel,
}: {
  value: number;
  max?: number;
  size?: number;
  strokeWidth?: number;
  color?: string;
  label?: string;
  sublabel?: string;
}) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const fraction = Math.max(0, Math.min(1, value / max));
  const offset = circumference * (1 - fraction);

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={strokeWidth}
            className="text-[hsl(var(--border))]"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ transition: "stroke-dashoffset 0.4s ease" }}
          />
        </svg>
        {label && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs font-semibold text-[hsl(var(--foreground))]">{label}</span>
          </div>
        )}
      </div>
      {sublabel && <span className="text-xs text-[hsl(var(--muted-foreground))] text-center">{sublabel}</span>}
    </div>
  );
}

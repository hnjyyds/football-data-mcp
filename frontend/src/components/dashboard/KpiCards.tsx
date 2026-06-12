import type { KpiCard } from "../../types";

const TONE_BG: Record<string, string> = {
  good:    "border-[hsl(var(--border))] bg-[hsl(var(--card))]",
  bad:     "border-[hsl(var(--destructive))]/30 bg-[hsl(var(--card))]",
  caution: "border-[hsl(var(--border))] bg-[hsl(var(--card))]",
  info:    "border-[hsl(var(--primary))]/30 bg-[hsl(var(--card))]",
  neutral: "border-[hsl(var(--border))] bg-[hsl(var(--card))]",
};

const TONE_VALUE: Record<string, string> = {
  good:    "text-[hsl(var(--foreground))]",
  bad:     "text-red-700 dark:text-red-300",
  caution: "text-[hsl(var(--foreground))]",
  info:    "text-[hsl(var(--foreground))]",
  neutral: "text-[hsl(var(--foreground))]",
};

export function KpiCards({ cards, compact = false }: { cards: KpiCard[]; compact?: boolean }) {
  if (compact) {
    return (
      <div className="surface-panel overflow-hidden">
        <div className="px-4 pt-4 pb-2">
          <span className="text-sm font-semibold text-[hsl(var(--foreground))]">系统指标</span>
        </div>
        <div className="px-2 pb-2">
          {cards.map((card) => {
            const tone = card.tone ?? "neutral";
            return (
              <div key={card.label} className="flex items-center justify-between rounded-md px-2 py-2 hover:bg-[hsl(var(--muted))]/70">
                <span className="text-xs text-[hsl(var(--muted-foreground))] truncate flex-1 min-w-0 mr-2">{card.label}</span>
                <span className={`text-sm font-semibold tabular-nums ${TONE_VALUE[tone] ?? TONE_VALUE.neutral}`}>
                  {card.value}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-2.5">
      {cards.map((card) => {
        const tone = card.tone ?? "neutral";
        return (
          <div key={card.label} className={`rounded-lg border p-3 shadow-sm ${TONE_BG[tone] ?? TONE_BG.neutral}`}>
            <div className="text-[11px] text-[hsl(var(--muted-foreground))] mb-1 truncate">{card.label}</div>
            <div className={`text-xl font-semibold tabular-nums tracking-tight ${TONE_VALUE[tone] ?? TONE_VALUE.neutral}`}>
              {card.value}
            </div>
          </div>
        );
      })}
    </div>
  );
}

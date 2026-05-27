import type { KpiCard } from "../../types";

const TONE_BG: Record<string, string> = {
  good:    "border-l-2 border-emerald-400 bg-emerald-50/50 dark:bg-emerald-900/10",
  bad:     "border-l-2 border-red-400 bg-red-50/50 dark:bg-red-900/10",
  caution: "border-l-2 border-amber-400 bg-amber-50/50 dark:bg-amber-900/10",
  info:    "border-l-2 border-sky-400 bg-sky-50/50 dark:bg-sky-900/10",
  neutral: "border-l-2 border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800",
};

const TONE_VALUE: Record<string, string> = {
  good:    "text-emerald-700 dark:text-emerald-300",
  bad:     "text-red-700 dark:text-red-300",
  caution: "text-amber-700 dark:text-amber-300",
  info:    "text-sky-700 dark:text-sky-300",
  neutral: "text-slate-900 dark:text-white",
};

export function KpiCards({ cards, compact = false }: { cards: KpiCard[]; compact?: boolean }) {
  if (compact) {
    return (
      <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm overflow-hidden">
        <div className="px-3 py-2 border-b border-slate-100 dark:border-slate-700/50">
          <span className="text-xs font-semibold text-slate-900 dark:text-white">系统指标</span>
        </div>
        <div className="divide-y divide-slate-50 dark:divide-slate-700/30">
          {cards.map((card) => {
            const tone = card.tone ?? "neutral";
            return (
              <div key={card.label} className="flex items-center justify-between px-3 py-2">
                <span className="text-xs text-slate-600 dark:text-slate-400 truncate flex-1 min-w-0 mr-2">{card.label}</span>
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
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-2">
      {cards.map((card) => {
        const tone = card.tone ?? "neutral";
        return (
          <div
            key={card.label}
            className={`rounded-lg p-3 shadow-sm ${TONE_BG[tone] ?? TONE_BG.neutral}`}
          >
            <div className="text-[11px] text-slate-500 dark:text-slate-400 mb-0.5 truncate">{card.label}</div>
            <div className={`text-lg font-bold tabular-nums ${TONE_VALUE[tone] ?? TONE_VALUE.neutral}`}>
              {card.value}
            </div>
          </div>
        );
      })}
    </div>
  );
}

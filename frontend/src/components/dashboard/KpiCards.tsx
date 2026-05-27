import type { KpiCard } from "../../types";

const TONE_BG: Record<string, string> = {
  good:    "border-l-4 border-emerald-400 bg-emerald-50 dark:bg-emerald-900/20",
  bad:     "border-l-4 border-red-400 bg-red-50 dark:bg-red-900/20",
  caution: "border-l-4 border-amber-400 bg-amber-50 dark:bg-amber-900/20",
  info:    "border-l-4 border-sky-400 bg-sky-50 dark:bg-sky-900/20",
  neutral: "border-l-4 border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800",
};

const TONE_VALUE: Record<string, string> = {
  good:    "text-emerald-700 dark:text-emerald-300",
  bad:     "text-red-700 dark:text-red-300",
  caution: "text-amber-700 dark:text-amber-300",
  info:    "text-sky-700 dark:text-sky-300",
  neutral: "text-slate-900 dark:text-white",
};

export function KpiCards({ cards }: { cards: KpiCard[] }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
      {cards.map((card) => {
        const tone = card.tone ?? "neutral";
        return (
          <div
            key={card.label}
            className={`rounded-xl p-3 shadow-sm ${TONE_BG[tone] ?? TONE_BG.neutral}`}
          >
            <div className="text-xs text-slate-500 dark:text-slate-400 mb-1 truncate">{card.label}</div>
            <div className={`text-xl font-bold tabular-nums ${TONE_VALUE[tone] ?? TONE_VALUE.neutral}`}>
              {card.value}
            </div>
          </div>
        );
      })}
    </div>
  );
}

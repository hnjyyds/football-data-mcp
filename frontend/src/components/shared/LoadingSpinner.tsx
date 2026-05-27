export function LoadingSpinner({ label = "加载中..." }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-8 text-slate-500 dark:text-slate-400">
      <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-4 animate-pulse bg-white dark:bg-slate-800">
      <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-1/3 mb-3" />
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className={`h-3 bg-slate-100 dark:bg-slate-700/60 rounded mb-2 ${i === lines - 1 ? "w-2/3" : "w-full"}`} />
      ))}
    </div>
  );
}

export function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 p-3 animate-pulse">
      <div className="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 flex-shrink-0" />
      <div className="flex-1 space-y-1.5">
        <div className="h-3 bg-slate-200 dark:bg-slate-700 rounded w-1/2" />
        <div className="h-2.5 bg-slate-100 dark:bg-slate-700/60 rounded w-1/3" />
      </div>
      <div className="h-5 w-12 bg-slate-200 dark:bg-slate-700 rounded-full" />
    </div>
  );
}

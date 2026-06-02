import { Badge, toneVariant } from "../shared/Badge";
import { Icon } from "../shared/Icon";
import type { ValidationJob } from "../../types";

type Props = {
  job: ValidationJob;
  actionJobId: string | null;
  statusLabel: string;
  statusTone: string;
  startLabel: string;
  quickStartLabel?: string;
  onStart: () => void;
  onQuickStart?: () => void;
  onCancel: (jobId: string) => void;
  onRetry: (jobId: string) => void;
};

export function ValidationJobActionBar({
  job,
  actionJobId,
  statusLabel,
  statusTone,
  startLabel,
  quickStartLabel = "快速诊断",
  onStart,
  onQuickStart,
  onCancel,
  onRetry,
}: Props) {
  const progress = job.progress;
  const canCancel = ["pending", "running"].includes(String(job.status));
  const canRetry = ["failed", "cancelled"].includes(String(job.status));
  const canStart = !["pending", "running"].includes(String(job.status));
  const busy = actionJobId === "holdout-new" || actionJobId === job.job_id;

  return (
    <div className="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/40 px-3 py-2">
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
        <Badge variant={toneVariant(statusTone)}>{statusLabel}</Badge>
        <span>已处理 {progress.processed_leagues ?? progress.completed_leagues}/{progress.total_leagues} 联赛</span>
        <span>成功 {progress.completed_leagues} 联赛</span>
        {progress.failed_leagues > 0 && <span>失败 {progress.failed_leagues} 联赛</span>}
        {(progress.cancelled_leagues ?? 0) > 0 && <span>已取消 {progress.cancelled_leagues} 联赛</span>}
      </div>
      <div className="flex items-center gap-2">
        {canStart && onQuickStart && (
          <button
            type="button"
            onClick={onQuickStart}
            disabled={busy}
            title="用小样本快速验证队列、缓存、模型和亚盘结算链路"
            className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-sky-200 dark:border-sky-800 bg-white dark:bg-slate-950 px-3 py-1.5 text-xs font-semibold text-sky-700 dark:text-sky-300 hover:bg-sky-50 dark:hover:bg-sky-950/40 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Icon name={busy ? "loading" : "zap"} size={13} className={busy ? "animate-spin" : ""} />
            {quickStartLabel}
          </button>
        )}
        {canStart && (
          <button
            type="button"
            onClick={onStart}
            disabled={busy}
            title="启动或继续 Holdout 验证"
            className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-emerald-200 dark:border-emerald-800 bg-white dark:bg-slate-950 px-3 py-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Icon name={busy ? "loading" : "refresh"} size={13} className={busy ? "animate-spin" : ""} />
            {startLabel}
          </button>
        )}
        {canCancel && (
          <button
            type="button"
            onClick={() => onCancel(job.job_id)}
            disabled={busy}
            title="取消当前 Holdout 验证"
            className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-red-200 dark:border-red-800 bg-white dark:bg-slate-950 px-3 py-1.5 text-xs font-semibold text-red-700 dark:text-red-300 hover:bg-red-50 dark:hover:bg-red-950/40 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Icon name={busy ? "loading" : "close"} size={13} className={busy ? "animate-spin" : ""} />
            取消
          </button>
        )}
        {canRetry && (
          <button
            type="button"
            onClick={() => onRetry(job.job_id)}
            disabled={busy}
            title="从未成功联赛继续验证"
            className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-emerald-200 dark:border-emerald-800 bg-white dark:bg-slate-950 px-3 py-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Icon name={busy ? "loading" : "refresh"} size={13} className={busy ? "animate-spin" : ""} />
            重试
          </button>
        )}
      </div>
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";

export type ToastItem = {
  id: string;
  message: string;
  type: "success" | "warning" | "error";
};

const TYPE_STYLES = {
  success: "bg-emerald-50 dark:bg-emerald-900/40 border-emerald-200 dark:border-emerald-700 text-emerald-800 dark:text-emerald-200",
  warning: "bg-amber-50 dark:bg-amber-900/40 border-amber-200 dark:border-amber-700 text-amber-800 dark:text-amber-200",
  error:   "bg-red-50 dark:bg-red-900/40 border-red-200 dark:border-red-700 text-red-800 dark:text-red-200",
};

const DISMISS_MS = 5000;

function ToastEntry({ item, onDismiss }: { item: ToastItem; onDismiss: (id: string) => void }) {
  const [paused, setPaused] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (paused) {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      return;
    }
    timerRef.current = setTimeout(() => onDismiss(item.id), DISMISS_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = null;
    };
  }, [item.id, onDismiss, paused]);

  const iconName = item.type === "success" ? "success" : "warn";
  return (
    <div
      role="status"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      className={`flex items-start gap-2 px-4 py-3 rounded-xl border shadow-md text-sm max-w-sm ${TYPE_STYLES[item.type]}`}
    >
      <Icon name={iconName} size={16} className="flex-shrink-0 mt-0.5" />
      <span className="flex-1">{item.message}</span>
      <button
        type="button"
        onClick={() => onDismiss(item.id)}
        className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
        aria-label="关闭"
      >
        <Icon name="close" size={14} />
      </button>
    </div>
  );
}

export function ToastContainer({ toasts, onDismiss }: { toasts: ToastItem[]; onDismiss: (id: string) => void }) {
  if (!toasts.length) return null;
  const hasError = toasts.some((t) => t.type === "error");
  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2" aria-live={hasError ? "assertive" : "polite"} aria-atomic="true">
      {toasts.map((t) => <ToastEntry key={t.id} item={t} onDismiss={onDismiss} />)}
    </div>
  );
}

export function useToasts() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const dismiss = (id: string) => setToasts((prev) => prev.filter((t) => t.id !== id));
  const push = (message: string, type: ToastItem["type"] = "success") => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev.slice(-4), { id, message, type }]);
  };
  return { toasts, dismiss, push };
}

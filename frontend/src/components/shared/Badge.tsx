import type { ReactNode } from "react";

type Variant = "success" | "error" | "warning" | "info" | "neutral" | "good" | "bad" | "caution";

const VARIANT_CLASSES: Record<Variant, string> = {
  success: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  good:    "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  error:   "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  bad:     "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  warning: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  caution: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  info:    "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
  neutral: "bg-slate-100 text-slate-700 dark:bg-slate-700/50 dark:text-slate-300",
};

export function Badge({
  children,
  variant = "neutral",
  className = "",
}: {
  children: ReactNode;
  variant?: Variant;
  className?: string;
}) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${VARIANT_CLASSES[variant]} ${className}`}>
      {children}
    </span>
  );
}

export function toneVariant(tone: string | null | undefined): Variant {
  if (tone === "good") return "good";
  if (tone === "bad") return "bad";
  if (tone === "caution") return "caution";
  if (tone === "info") return "info";
  return "neutral";
}

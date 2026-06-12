import type { ReactNode } from "react";

type Variant = "success" | "error" | "warning" | "info" | "neutral" | "good" | "bad" | "caution";

const VARIANT_CLASSES: Record<Variant, string> = {
  success: "border-emerald-600/20 bg-transparent text-emerald-700 dark:text-emerald-400",
  good:    "border-emerald-600/20 bg-transparent text-emerald-700 dark:text-emerald-400",
  error:   "border-transparent bg-[hsl(var(--destructive))] text-[hsl(var(--destructive-foreground))]",
  bad:     "border-transparent bg-[hsl(var(--destructive))] text-[hsl(var(--destructive-foreground))]",
  warning: "border-amber-500/25 bg-transparent text-amber-700 dark:text-amber-400",
  caution: "border-amber-500/25 bg-transparent text-amber-700 dark:text-amber-400",
  info:    "border-[hsl(var(--border))] bg-transparent text-[hsl(var(--foreground))]",
  neutral: "border-[hsl(var(--border))] bg-[hsl(var(--card))] text-[hsl(var(--foreground))]",
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
    <span className={`inline-flex items-center rounded-md border px-1.5 py-0.5 text-[11px] font-medium leading-5 transition-colors ${VARIANT_CLASSES[variant]} ${className}`}>
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

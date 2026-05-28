export const BEIJING_TZ = "Asia/Shanghai";

function safeDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

const SHORT = new Intl.DateTimeFormat("zh-CN", {
  timeZone: BEIJING_TZ,
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const FULL = new Intl.DateTimeFormat("zh-CN", {
  timeZone: BEIJING_TZ,
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

const CLOCK = new Intl.DateTimeFormat("zh-CN", {
  timeZone: BEIJING_TZ,
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

export function formatBeijingShort(value: string | null | undefined): string {
  const d = safeDate(value);
  return d ? SHORT.format(d) : "—";
}

export function formatBeijingFull(value: string | null | undefined): string {
  const d = safeDate(value);
  return d ? FULL.format(d) : "—";
}

export function formatBeijingClock(value: string | null | undefined): string {
  const d = safeDate(value);
  return d ? CLOCK.format(d) : "—";
}

export function relativeFromNow(value: string | null | undefined): string {
  const d = safeDate(value);
  if (!d) return "—";
  const diffSec = Math.round((Date.now() - d.getTime()) / 1000);
  if (Math.abs(diffSec) < 60) return `${diffSec}s`;
  if (Math.abs(diffSec) < 3600) return `${Math.floor(diffSec / 60)}m`;
  return `${Math.floor(diffSec / 3600)}h`;
}

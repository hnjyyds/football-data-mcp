export type ErrorRecord = {
  message: string;
  stack: string | null;
  context: Record<string, unknown> & { kind: string };
  at: string;
};

export type ErrorSink = (record: ErrorRecord) => void;

const MAX_QUEUE = 50;
const queue: ErrorRecord[] = [];
let sink: ErrorSink | null = null;
let installed = false;
let onErrorHandler: ((event: ErrorEvent) => void) | null = null;
let onRejectionHandler: ((event: PromiseRejectionEvent) => void) | null = null;

function normalize(input: unknown, context: { kind: string } & Record<string, unknown>): ErrorRecord {
  if (input instanceof Error) {
    return { message: input.message, stack: input.stack ?? null, context, at: new Date().toISOString() };
  }
  return { message: typeof input === "string" ? input : JSON.stringify(input), stack: null, context, at: new Date().toISOString() };
}

export function reportError(input: unknown, context: { kind: string } & Record<string, unknown>): void {
  const record = normalize(input, context);
  queue.push(record);
  while (queue.length > MAX_QUEUE) queue.shift();
  try {
    sink?.(record);
  } catch {
    // never let sink failure cascade
  }
  if (typeof console !== "undefined") {
    console.warn("[errorReporter]", record.context.kind, record.message);
  }
}

export function setErrorSink(next: ErrorSink | null): void {
  sink = next;
}

export function getQueuedErrors(): ErrorRecord[] {
  return queue.slice();
}

export function installGlobalErrorReporter(): void {
  if (installed) return;
  if (typeof window === "undefined") return;
  onErrorHandler = (event: ErrorEvent) => {
    reportError(event.error ?? event.message ?? "unknown error", {
      kind: "window.onerror",
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
    });
  };
  onRejectionHandler = (event: PromiseRejectionEvent) => {
    reportError(event.reason, { kind: "unhandledrejection" });
  };
  window.addEventListener("error", onErrorHandler);
  window.addEventListener("unhandledrejection", onRejectionHandler);
  installed = true;
}

export function resetErrorReporterForTest(): void {
  queue.length = 0;
  sink = null;
  if (typeof window !== "undefined") {
    if (onErrorHandler) window.removeEventListener("error", onErrorHandler);
    if (onRejectionHandler) window.removeEventListener("unhandledrejection", onRejectionHandler);
  }
  onErrorHandler = null;
  onRejectionHandler = null;
  installed = false;
}

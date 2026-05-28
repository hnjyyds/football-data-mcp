export type RetryOpts = {
  retries: number;
  baseDelayMs: number;
  maxDelayMs?: number;
  signal?: AbortSignal;
};

function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

function isClientError(err: unknown): boolean {
  if (err && typeof err === "object" && "status" in err) {
    const status = (err as { status?: number }).status;
    return typeof status === "number" && status >= 400 && status < 500;
  }
  return false;
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    if (signal) {
      const onAbort = () => {
        clearTimeout(t);
        reject(new DOMException("aborted", "AbortError"));
      };
      if (signal.aborted) onAbort();
      else signal.addEventListener("abort", onAbort, { once: true });
    }
  });
}

export async function withRetry<T>(fn: () => Promise<T>, opts: RetryOpts): Promise<T> {
  const { retries, baseDelayMs, maxDelayMs = 30000, signal } = opts;
  let attempt = 0;
  let lastErr: unknown;
  while (attempt <= retries) {
    try {
      return await fn();
    } catch (err) {
      lastErr = err;
      if (isAbortError(err)) throw err;
      if (isClientError(err)) throw err;
      if (attempt === retries) break;
      const wait = Math.min(baseDelayMs * 2 ** attempt, maxDelayMs);
      await delay(wait, signal);
      attempt += 1;
    }
  }
  throw lastErr;
}

type PollerTask<T> = (ctx: { signal: AbortSignal }) => Promise<T>;

export type Poller = {
  start: () => void;
  stop: () => void;
  isRunning: () => boolean;
  triggerNow: () => void;
};

export function createPoller<T>(
  task: PollerTask<T>,
  opts: { intervalMs: number; onResult?: (value: T) => void; onError?: (err: unknown) => void; visibilityAware?: boolean }
): Poller {
  let timer: ReturnType<typeof setTimeout> | null = null;
  let inFlight = false;
  let stopped = true;
  let controller: AbortController | null = null;
  const visibilityAware = opts.visibilityAware !== false;

  function isHidden(): boolean {
    return visibilityAware && typeof document !== "undefined" && document.hidden;
  }

  async function tick() {
    if (stopped) return;
    if (inFlight) return;
    if (isHidden()) return;
    inFlight = true;
    controller = new AbortController();
    try {
      const value = await task({ signal: controller.signal });
      if (!stopped) opts.onResult?.(value);
    } catch (err) {
      if (!stopped && !isAbortError(err)) opts.onError?.(err);
    } finally {
      inFlight = false;
      controller = null;
      schedule();
    }
  }

  function schedule() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    if (stopped) return;
    if (isHidden()) return;
    timer = setTimeout(() => {
      timer = null;
      void tick();
    }, opts.intervalMs);
  }

  function onVisibilityChange() {
    if (stopped) return;
    if (isHidden()) {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
    } else if (!inFlight && !timer) {
      void tick();
    }
  }

  return {
    start() {
      if (!stopped) return;
      stopped = false;
      if (visibilityAware && typeof document !== "undefined") {
        document.addEventListener("visibilitychange", onVisibilityChange);
      }
      timer = setTimeout(() => {
        timer = null;
        void tick();
      }, 0);
    },
    stop() {
      stopped = true;
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      if (controller) controller.abort();
      if (visibilityAware && typeof document !== "undefined") {
        document.removeEventListener("visibilitychange", onVisibilityChange);
      }
    },
    isRunning() {
      return !stopped;
    },
    triggerNow() {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      void tick();
    },
  };
}

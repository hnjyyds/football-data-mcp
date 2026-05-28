import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { createPoller, withRetry } from "./poller";

describe("withRetry", () => {
  it("returns immediately on success", async () => {
    const fn = vi.fn(async () => 42);
    const result = await withRetry(fn, { retries: 3, baseDelayMs: 1 });
    expect(result).toBe(42);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("retries on failure and eventually succeeds", async () => {
    let calls = 0;
    const fn = vi.fn(async () => {
      calls += 1;
      if (calls < 3) throw new Error("flaky");
      return "ok";
    });
    const result = await withRetry(fn, { retries: 3, baseDelayMs: 1 });
    expect(result).toBe("ok");
    expect(fn).toHaveBeenCalledTimes(3);
  });

  it("rethrows after exhausting retries", async () => {
    const fn = vi.fn(async () => {
      throw new Error("nope");
    });
    await expect(withRetry(fn, { retries: 2, baseDelayMs: 1 })).rejects.toThrow("nope");
    expect(fn).toHaveBeenCalledTimes(3);
  });

  it("does not retry AbortError", async () => {
    const fn = vi.fn(async () => {
      throw new DOMException("aborted", "AbortError");
    });
    await expect(withRetry(fn, { retries: 5, baseDelayMs: 1 })).rejects.toThrow(/abort/i);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("does not retry HTTP 4xx", async () => {
    const fn = vi.fn(async () => {
      const err = Object.assign(new Error("HTTP 404"), { status: 404, name: "HttpError" });
      throw err;
    });
    await expect(withRetry(fn, { retries: 3, baseDelayMs: 1 })).rejects.toThrow(/404/);
    expect(fn).toHaveBeenCalledTimes(1);
  });
});

describe("createPoller", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("invokes the task immediately on start", async () => {
    const task = vi.fn(async () => "v1");
    const p = createPoller(task, { intervalMs: 1000 });
    p.start();
    await vi.runOnlyPendingTimersAsync();
    expect(task).toHaveBeenCalledTimes(1);
    p.stop();
  });

  it("schedules subsequent runs at intervalMs", async () => {
    const task = vi.fn(async () => "v");
    const p = createPoller(task, { intervalMs: 5000 });
    p.start();
    await vi.runOnlyPendingTimersAsync();
    expect(task).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(5000);
    expect(task).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(5000);
    expect(task).toHaveBeenCalledTimes(3);
    p.stop();
  });

  it("never overlaps a run with itself (mutex)", async () => {
    let inFlight = 0;
    let maxInFlight = 0;
    const task = vi.fn(async () => {
      inFlight += 1;
      maxInFlight = Math.max(maxInFlight, inFlight);
      await new Promise((r) => setTimeout(r, 10000));
      inFlight -= 1;
      return null;
    });
    const p = createPoller(task, { intervalMs: 1000 });
    p.start();
    await vi.runOnlyPendingTimersAsync();
    await vi.advanceTimersByTimeAsync(5000);
    expect(maxInFlight).toBe(1);
    p.stop();
    await vi.advanceTimersByTimeAsync(10000);
  });

  it("aborts in-flight task on stop", async () => {
    const aborted = vi.fn();
    const task = vi.fn(async ({ signal }: { signal: AbortSignal }) => {
      signal.addEventListener("abort", aborted);
      await new Promise((_, reject) => signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))));
    });
    const p = createPoller(task, { intervalMs: 1000 });
    p.start();
    await vi.runOnlyPendingTimersAsync();
    p.stop();
    expect(aborted).toHaveBeenCalled();
  });

  it("pauses while document.hidden and resumes on visibilitychange", async () => {
    const task = vi.fn(async () => "v");
    Object.defineProperty(document, "hidden", { configurable: true, get: () => true });
    const p = createPoller(task, { intervalMs: 2000 });
    p.start();
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(10000);
    expect(task).toHaveBeenCalledTimes(0);
    Object.defineProperty(document, "hidden", { configurable: true, get: () => false });
    document.dispatchEvent(new Event("visibilitychange"));
    await Promise.resolve();
    expect(task).toHaveBeenCalledTimes(1);
    p.stop();
  });
});

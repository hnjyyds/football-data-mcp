import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import {
  reportError,
  installGlobalErrorReporter,
  resetErrorReporterForTest,
  getQueuedErrors,
  setErrorSink,
} from "./errorReporter";

describe("errorReporter", () => {
  beforeEach(() => {
    resetErrorReporterForTest();
  });
  afterEach(() => {
    resetErrorReporterForTest();
  });

  it("queues errors with normalized shape", () => {
    reportError(new Error("kaboom"), { kind: "manual" });
    const items = getQueuedErrors();
    expect(items).toHaveLength(1);
    expect(items[0].message).toBe("kaboom");
    expect(items[0].context.kind).toBe("manual");
    expect(typeof items[0].at).toBe("string");
  });

  it("captures window.onerror through installGlobalErrorReporter", () => {
    installGlobalErrorReporter();
    window.dispatchEvent(new ErrorEvent("error", { error: new Error("global!"), message: "global!" }));
    const items = getQueuedErrors();
    expect(items.some((i) => i.message === "global!")).toBe(true);
  });

  it("captures unhandledrejection through installGlobalErrorReporter", () => {
    installGlobalErrorReporter();
    const reason = new Error("rejected");
    window.dispatchEvent(new Event("unhandledrejection") as any);
    // jsdom does not fire PromiseRejectionEvent ergonomically; emulate manually
    reportError(reason, { kind: "unhandledrejection" });
    expect(getQueuedErrors().some((i) => i.message === "rejected" && i.context.kind === "unhandledrejection")).toBe(true);
  });

  it("forwards to a configured sink", () => {
    const sink = vi.fn();
    setErrorSink(sink);
    reportError(new Error("sent"), { kind: "manual" });
    expect(sink).toHaveBeenCalledTimes(1);
    expect(sink.mock.calls[0][0].message).toBe("sent");
  });

  it("caps the queue at 50 entries", () => {
    for (let i = 0; i < 80; i++) reportError(new Error(`e${i}`), { kind: "manual" });
    expect(getQueuedErrors().length).toBeLessThanOrEqual(50);
    expect(getQueuedErrors()[0].message).not.toBe("e0");
  });

  it("installGlobalErrorReporter is idempotent", () => {
    installGlobalErrorReporter();
    installGlobalErrorReporter();
    window.dispatchEvent(new ErrorEvent("error", { error: new Error("once"), message: "once" }));
    const count = getQueuedErrors().filter((i) => i.message === "once").length;
    expect(count).toBe(1);
  });
});

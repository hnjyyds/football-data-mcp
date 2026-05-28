import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ErrorBoundary } from "./ErrorBoundary";

function Boom({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error("boom!");
  return <div>safe</div>;
}

describe("ErrorBoundary", () => {
  let errSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });
  afterEach(() => {
    errSpy.mockRestore();
  });

  it("renders children when no error", () => {
    render(
      <ErrorBoundary>
        <Boom shouldThrow={false} />
      </ErrorBoundary>
    );
    expect(screen.getByText("safe")).toBeInTheDocument();
  });

  it("renders fallback UI with retry when child throws", () => {
    render(
      <ErrorBoundary>
        <Boom shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/出错|error/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /重试|retry/i })).toBeInTheDocument();
  });

  it("calls onError with the error", () => {
    const onError = vi.fn();
    render(
      <ErrorBoundary onError={onError}>
        <Boom shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError.mock.calls[0][0]).toBeInstanceOf(Error);
    expect((onError.mock.calls[0][0] as Error).message).toBe("boom!");
  });

  it("retry button resets to render children again", () => {
    function Toggle() {
      const [n, setN] = (globalThis as any).__counter ?? [0, () => {}];
      return <button onClick={() => setN(n + 1)}>x</button>;
    }
    let throwIt = true;
    function Conditional() {
      if (throwIt) throw new Error("boom!");
      return <div>recovered</div>;
    }
    const { rerender } = render(
      <ErrorBoundary>
        <Conditional />
      </ErrorBoundary>
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    throwIt = false;
    fireEvent.click(screen.getByRole("button", { name: /重试|retry/i }));
    rerender(
      <ErrorBoundary>
        <Conditional />
      </ErrorBoundary>
    );
    expect(screen.getByText("recovered")).toBeInTheDocument();
  });
});

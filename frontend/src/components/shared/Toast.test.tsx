import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { ToastContainer } from "./Toast";

describe("Toast", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("auto-dismisses after 5s", () => {
    const onDismiss = vi.fn();
    render(<ToastContainer toasts={[{ id: "a", message: "hi", type: "success" }]} onDismiss={onDismiss} />);
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(onDismiss).toHaveBeenCalledWith("a");
  });

  it("pauses dismiss timer on hover", () => {
    const onDismiss = vi.fn();
    render(<ToastContainer toasts={[{ id: "a", message: "hi", type: "success" }]} onDismiss={onDismiss} />);
    const toast = screen.getByText("hi").closest("[role='status']") as HTMLElement;
    fireEvent.mouseEnter(toast);
    act(() => {
      vi.advanceTimersByTime(10000);
    });
    expect(onDismiss).not.toHaveBeenCalled();
    fireEvent.mouseLeave(toast);
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(onDismiss).toHaveBeenCalledWith("a");
  });

  it("container has aria-live polite for non-error and uses assertive for error", () => {
    const { container, rerender } = render(
      <ToastContainer toasts={[{ id: "a", message: "ok", type: "success" }]} onDismiss={() => {}} />
    );
    const region = container.querySelector("[aria-live]") as HTMLElement;
    expect(region.getAttribute("aria-live")).toBe("polite");
    rerender(<ToastContainer toasts={[{ id: "b", message: "boom", type: "error" }]} onDismiss={() => {}} />);
    expect(container.querySelector("[aria-live]")?.getAttribute("aria-live")).toBe("assertive");
  });
});

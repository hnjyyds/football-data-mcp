import { describe, expect, it, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDarkMode, DARK_STORAGE_KEY } from "./useDarkMode";

describe("useDarkMode", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  it("falls back to OS preference when no stored value", () => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: () => ({ matches: true, addEventListener() {}, removeEventListener() {}, media: "" }),
    });
    const { result } = renderHook(() => useDarkMode());
    expect(result.current[0]).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("reads stored preference over OS preference", () => {
    localStorage.setItem(DARK_STORAGE_KEY, "light");
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: () => ({ matches: true, addEventListener() {}, removeEventListener() {}, media: "" }),
    });
    const { result } = renderHook(() => useDarkMode());
    expect(result.current[0]).toBe(false);
  });

  it("persists toggle to localStorage", () => {
    const { result } = renderHook(() => useDarkMode());
    act(() => result.current[1](true));
    expect(localStorage.getItem(DARK_STORAGE_KEY)).toBe("dark");
    act(() => result.current[1](false));
    expect(localStorage.getItem(DARK_STORAGE_KEY)).toBe("light");
  });

  it("applies the dark class on the documentElement when enabled", () => {
    const { result } = renderHook(() => useDarkMode());
    act(() => result.current[1](true));
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    act(() => result.current[1](false));
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});

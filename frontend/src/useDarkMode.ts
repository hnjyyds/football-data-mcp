import { useCallback, useEffect, useState } from "react";

export const DARK_STORAGE_KEY = "football-mcp:darkMode";

function readStored(): boolean | null {
  try {
    const v = localStorage.getItem(DARK_STORAGE_KEY);
    if (v === "dark") return true;
    if (v === "light") return false;
  } catch {
    // localStorage may be unavailable (SSR, privacy mode)
  }
  return null;
}

function readSystem(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function useDarkMode(): [boolean, (next: boolean | ((prev: boolean) => boolean)) => void] {
  const [dark, setDark] = useState<boolean>(() => readStored() ?? readSystem());

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem(DARK_STORAGE_KEY, dark ? "dark" : "light");
    } catch {
      // ignore quota / privacy errors
    }
  }, [dark]);

  const setter = useCallback((next: boolean | ((prev: boolean) => boolean)) => {
    setDark((prev) => (typeof next === "function" ? (next as (p: boolean) => boolean)(prev) : next));
  }, []);

  return [dark, setter];
}

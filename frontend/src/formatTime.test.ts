import { describe, expect, it } from "vitest";
import { formatBeijingShort, formatBeijingFull, formatBeijingClock, BEIJING_TZ } from "./formatTime";

describe("formatTime", () => {
  it("BEIJING_TZ is Asia/Shanghai", () => {
    expect(BEIJING_TZ).toBe("Asia/Shanghai");
  });

  it("formatBeijingShort renders MM-DD HH:mm in Asia/Shanghai regardless of host tz", () => {
    // 2026-05-25T05:30:00Z -> Beijing 13:30 on 05-25
    const out = formatBeijingShort("2026-05-25T05:30:00+00:00");
    expect(out).toMatch(/05/);
    expect(out).toMatch(/13:30/);
  });

  it("formatBeijingFull includes seconds", () => {
    const out = formatBeijingFull("2026-05-25T05:30:09+00:00");
    expect(out).toMatch(/13:30:09/);
  });

  it("formatBeijingClock returns HH:mm:ss only", () => {
    const out = formatBeijingClock("2026-05-25T05:30:09+00:00");
    expect(out).toBe("13:30:09");
  });

  it("returns dash for empty / invalid input", () => {
    expect(formatBeijingShort(null)).toBe("—");
    expect(formatBeijingShort(undefined)).toBe("—");
    expect(formatBeijingShort("not-a-date")).toBe("—");
  });

  it("treats `+08:00` field values correctly (no double-add)", () => {
    // 2026-05-25T13:30:00+08:00 == 05:30Z -> Beijing 13:30
    expect(formatBeijingClock("2026-05-25T13:30:00+08:00")).toBe("13:30:00");
  });
});

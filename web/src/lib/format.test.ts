import { describe, expect, it } from "vitest";
import { compact, date, daysUntil, num, pct, price, tone } from "./format";

describe("format", () => {
  it("shows missing values as a dash, never as zero", () => {
    for (const f of [pct, num, compact, price]) {
      expect(f(null)).toBe("–");
      expect(f(undefined)).toBe("–");
      expect(f(Number.NaN)).toBe("–");
    }
    expect(date(null)).toBe("–");
    expect(tone(null)).toBe("");
  });

  it("formats percentages from fractions", () => {
    expect(pct(0.1234)).toBe("+12.3%");
    expect(pct(-0.05)).toBe("-5.0%");
    expect(pct(0)).toBe("0.0%");
    expect(pct(-0.00001)).toBe("0.0%"); // no "-0.0%"
    expect(pct(0.0456, 2, false)).toBe("4.56%");
  });

  it("formats sizes and prices", () => {
    expect(compact(1_132_624_740_352)).toBe("1.13T");
    expect(compact(20_611_657_728)).toBe("20.6B");
    expect(compact(-950_000)).toBe("-950K");
    expect(price(256.6499, "DKK")).toBe("256.65 DKK");
    expect(price(12345.6)).toBe("12,346");
    expect(num(1234.5, 1)).toBe("1,234.5");
  });

  it("formats dates and counts days", () => {
    expect(date("2026-11-04")).toBe("4 Nov 2026");
    expect(daysUntil("2026-11-04", new Date(2026, 9, 13))).toBe(22);
    expect(tone(0.1)).toBe("pos");
    expect(tone(-0.1)).toBe("neg");
  });
});

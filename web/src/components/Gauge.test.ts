import { describe, expect, it } from "vitest";
import { fmtGauge, lvClass, nearest, worst, type GaugeData } from "./Gauge";

const rsi: GaugeData = { value: 69.5, score: -0.58, level: -2, label: "near overbought", scale: "diverging", unit: "num",
  ticks: [30, 70], lo: 0, hi: 100 };

describe("gauge display", () => {
  it("maps levels to the warm, grey and green classes", () => {
    expect(lvClass(rsi)).toBe("lv-2");
    expect(lvClass({ ...rsi, level: 0 })).toBe("lv0");
    expect(lvClass({ ...rsi, level: 3 })).toBe("lv+3");
    expect(lvClass(undefined)).toBe("lv0");
  });

  it("names the nearest threshold and the distance to it", () => {
    expect(nearest(rsi)).toBe("0.5 below the 70 threshold");
    expect(nearest({ ...rsi, value: 25 })).toBe("5 below the 30 threshold");
    expect(nearest({ ...rsi, ticks: [] })).toBeNull();
    const stop = { ...rsi, unit: "pct" as const, value: -0.021, ticks: [-0.08, -0.04] };
    expect(nearest(stop)).toBe("1.9% above the -4% threshold");
  });

  it("formats by unit and finds the worst level of a row", () => {
    expect(fmtGauge(0.123, { unit: "pct" })).toBe("12.3%");
    expect(fmtGauge(1.5, { unit: "num" })).toBe("1.5");
    expect(worst({ a: rsi, b: { ...rsi, level: 2 } })).toBe(-2);
    expect(worst({})).toBeNull();
  });
});

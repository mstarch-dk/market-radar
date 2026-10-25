import { describe, expect, it } from "vitest";
import { extent, stack, waterfall } from "./attribution";

describe("attribution", () => {
  it("chains the waterfall's steps from 0", () => {
    const s = waterfall([{ key: "a", label: "A", value: 0.02 }, { key: "b", label: "B", value: -0.05 }]);
    expect(s.map((x) => [x.from, x.to])).toEqual([[0, 0.02], [0.02, expect.closeTo(-0.03)]]);
  });

  it("gives no position after a missing step, never a zero bar", () => {
    const s = waterfall([{ key: "a", label: "A", value: null }, { key: "b", label: "B", value: 0.01 }]);
    expect(s.every((x) => x.from === null && x.to === null)).toBe(true);
    expect(s[1]?.value).toBe(0.01);
  });

  it("spans 0 and skips missing values", () => {
    expect(extent([0.1, null, 0.3])).toEqual([0, 0.3]);
    expect(extent([-0.2, 0.1])).toEqual([-0.2, 0.1]);
  });

  it("stacks positive effects up and negative ones down", () => {
    const s = stack({ allocation: 0.01, selection: -0.02, interaction: 0.005, currency: -0.01, cross: 0 });
    expect(s.find((x) => x.effect === "interaction")).toEqual({ effect: "interaction", y0: 0.01, y1: 0.015 });
    expect(s.find((x) => x.effect === "currency")).toEqual({ effect: "currency", y0: -0.03, y1: -0.02 });
    expect(s.some((x) => x.effect === "cross")).toBe(false);
  });
});

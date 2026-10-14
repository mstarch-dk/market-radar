import { describe, expect, it } from "vitest";
import { alignSort, dots } from "./views";

const a = (label: "aligned" | "conflicts" | "mixed" | "unrelated", score: number) => ({ label, score, views: [] });

describe("alignSort", () => {
  it("orders aligned, mixed, unrelated, conflicts; stronger first within a label; missing last", () => {
    const rows = [a("conflicts", -0.8), a("aligned", 0.4), undefined, a("unrelated", 0), a("aligned", 0.9), a("mixed", 0.1)];
    const sorted = [...rows].sort((x, y) => (alignSort(y) ?? -9) - (alignSort(x) ?? -9));
    expect(sorted.map((r) => (r ? `${r.label}:${r.score}` : "none"))).toEqual(
      ["aligned:0.9", "aligned:0.4", "mixed:0.1", "unrelated:0", "conflicts:-0.8", "none"]);
    expect(alignSort(undefined)).toBeNull();
  });
});

describe("dots", () => {
  it("shows conviction out of five", () => {
    expect(dots(3)).toBe("●●●○○");
    expect(dots(5)).toBe("●●●●●");
  });
});

import { describe, expect, it } from "vitest";
import { indexAt, rebase } from "./chartRange";

const dates = ["2025-12-29", "2025-12-30", "2025-12-31", "2026-01-02", "2026-01-05", "2026-01-06"];

describe("indexAt", () => {
  it("finds the session on the base date", () => {
    expect(indexAt(dates, "2025-12-31")).toBe(2);
  });
  it("uses the last session before a base date the ticker didn't trade on", () => {
    expect(indexAt(dates, "2026-01-01")).toBe(2);
  });
  it("starts at the first session when the base date is before the series or missing", () => {
    expect(indexAt(dates, "2020-01-01")).toBe(0);
    expect(indexAt(dates, null)).toBe(0);
  });
});

describe("rebase", () => {
  it("rebases to 100 at the first value from the range start", () => {
    expect(rebase([50, null, 80, 120], 1)).toEqual([62.5, null, 100, 150]);
  });
  it("leaves the line missing when there is nothing to rebase on", () => {
    expect(rebase([null, null], 0)).toEqual([null, null]);
  });
});

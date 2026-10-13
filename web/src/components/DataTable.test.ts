import { describe, expect, it } from "vitest";
import { sortRows } from "./DataTable";

describe("sortRows", () => {
  const rows = [{ v: 2 }, { v: null }, { v: 5 }, { v: undefined }, { v: -1 }, { v: Number.NaN }];
  const by = (r: { v: number | null | undefined }) => r.v;

  it("keeps missing values last in both directions", () => {
    expect(sortRows(rows, by, false).map(by).slice(0, 3)).toEqual([5, 2, -1]);
    expect(sortRows(rows, by, true).map(by).slice(0, 3)).toEqual([-1, 2, 5]);
    expect(sortRows(rows, by, true).slice(3).every((r) => r.v == null || Number.isNaN(r.v))).toBe(true);
  });

  it("sorts text alphabetically and leaves the input alone", () => {
    const names = [{ v: "b" }, { v: "a" }, { v: null }];
    expect(sortRows(names, (r) => r.v, true).map((r) => r.v)).toEqual(["a", "b", null]);
    expect(names[0]?.v).toBe("b");
  });
});

import { describe, expect, it } from "vitest";
import { csvCell, filterRows, parseState, serializeState, sortRows, toCsv, type ColSpec, type TableState } from "./tableState";

type Row = { t: string; q: string | null; r3m: number | null; trend: boolean | null; flags: string[] };
const rows: Row[] = [
  { t: "AAA", q: "Leading", r3m: 0.12, trend: true, flags: ["trend intact", "near 52w high"] },
  { t: "BBB", q: "Lagging", r3m: -0.05, trend: false, flags: [] },
  { t: "CCC", q: "Improving", r3m: null, trend: null, flags: ["turning up"] },
  { t: "DDD", q: "Leading", r3m: 0.02, trend: true, flags: ["trend intact"] },
];
const cols: ColSpec<Row>[] = [
  { key: "t", sort: (r) => r.t, search: (r) => r.t },
  { key: "q", sort: (r) => r.q, filter: { kind: "enum" } },
  { key: "r3m", sort: (r) => r.r3m, filter: { kind: "range", unit: "pct" } },
  { key: "trend", sort: (r) => r.trend, filter: { kind: "bool" } },
  { key: "flags", filter: { kind: "enum", value: (r) => r.flags } },
];
const st = (s: Partial<TableState>): TableState => ({ q: "", filters: {}, ...s });

describe("URL state", () => {
  it("round-trips every filter kind and keeps other params", () => {
    const s = st({
      sort: { key: "r3m", asc: false }, q: "semi",
      filters: { q: { kind: "enum", values: ["Leading", "Improving"] }, trend: { kind: "bool", value: true },
                 r3m: { kind: "range", min: 0.05 }, x: { kind: "range", max: -0.1 } },
    });
    const p = serializeState(new URLSearchParams("other=1&m.q=old"), "m", s);
    expect(p.get("other")).toBe("1");
    expect(p.get("m.f.q")).toBe("in:Leading|Improving");
    expect(p.get("m.f.r3m")).toBe("range:0.05:");
    expect(parseState(new URLSearchParams(p.toString()), "m")).toEqual(s);
  });

  it("ignores other tables and malformed values", () => {
    const p = new URLSearchParams("a.q=x&b.f.r3m=range:abc:&b.f.q=in:&b.sort=name:asc");
    expect(parseState(p, "b")).toEqual(st({ sort: { key: "name", asc: true } }));
  });
});

describe("filterRows", () => {
  it("applies enum, bool and range filters, and search", () => {
    expect(filterRows(rows, cols, st({ filters: { q: { kind: "enum", values: ["Leading"] } } })).rows.map((r) => r.t)).toEqual(["AAA", "DDD"]);
    expect(filterRows(rows, cols, st({ filters: { trend: { kind: "bool", value: false } } })).rows.map((r) => r.t)).toEqual(["BBB"]);
    expect(filterRows(rows, cols, st({ filters: { flags: { kind: "enum", values: ["trend intact"] } } })).rows).toHaveLength(2);
    expect(filterRows(rows, cols, st({ q: "cc" })).rows.map((r) => r.t)).toEqual(["CCC"]);
  });

  it("drops rows without data from a range filter and counts them, never treating them as 0", () => {
    const res = filterRows(rows, cols, st({ filters: { r3m: { kind: "range", max: 0.05 } } }));
    expect(res.rows.map((r) => r.t)).toEqual(["BBB", "DDD"]);
    expect(res.missing).toBe(1);
  });

  it("ignores filters on columns the table doesn't have", () => {
    expect(filterRows(rows, cols, st({ filters: { nope: { kind: "bool", value: true } } })).rows).toHaveLength(4);
  });
});

describe("sortRows", () => {
  it("keeps missing values last in both directions", () => {
    expect(sortRows(rows, (r) => r.r3m, false).map((r) => r.t)).toEqual(["AAA", "DDD", "BBB", "CCC"]);
    expect(sortRows(rows, (r) => r.r3m, true).map((r) => r.t)).toEqual(["BBB", "DDD", "AAA", "CCC"]);
  });
});

describe("CSV", () => {
  it("escapes and leaves missing values empty", () => {
    expect(csvCell('say "hi", ok')).toBe('"say ""hi"", ok"');
    expect(csvCell(null)).toBe("");
    expect(csvCell(Number.NaN)).toBe("");
    expect(csvCell(["a", "b"])).toBe('"a; b"');
    expect(toCsv(["t", "r3m"], rows.slice(1, 3), [(r) => r.t, (r) => r.r3m])).toBe("t,r3m\nBBB,-0.05\nCCC,\n");
  });
});

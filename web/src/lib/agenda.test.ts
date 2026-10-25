import { describe, expect, it } from "vitest";
import { byWeek, filterItems, inDays, isoWeek, KINDS, LEVEL_KIND, monthGrid, monthsOf, soonItems, when, type Item } from "./agenda";

const item = (o: Partial<Item>): Item => ({
  id: `${o.kind ?? "earnings"}:${o.symbol ?? "X"}:${o.date}`, kind: "earnings", date: "2026-10-28", date_end: null, days: 3,
  symbol: "X", name: null, status: "holding", level: "normal", weight: null, reasons: [], earnings: null, link: "/ticker/X", ...o,
});

describe("calendar layout", () => {
  it("finds ISO weeks, including the ones that straddle a new year", () => {
    expect(isoWeek("2026-10-28")).toEqual({ key: "2026-W44", monday: "2026-10-26", week: 44 });
    expect(isoWeek("2026-11-01").monday).toBe("2026-10-26");        // Sunday belongs to the week before
    expect(isoWeek("2027-01-01").key).toBe("2026-W53");              // a Friday: its Thursday is in 2026
    expect(isoWeek("2025-12-29").key).toBe("2026-W01");
  });

  it("groups the agenda by week in date order", () => {
    const w = byWeek([item({ date: "2026-11-03" }), item({ date: "2026-10-27" }), item({ date: "2026-10-30", symbol: "Y" })]);
    expect(w.map((g) => [g.key, g.items.map((i) => i.date)])).toEqual([
      ["2026-W44", ["2026-10-27", "2026-10-30"]], ["2026-W45", ["2026-11-03"]]]);
  });

  it("filters by held or watched and by kind; your own dates count as held", () => {
    const items = [item({ status: "holding" }), item({ status: "watch", symbol: "W" }),
      item({ status: "own", kind: "review", symbol: null }), item({ status: "holding", kind: "ex_dividend" })];
    const all = new Set(KINDS.map(([k]) => k));
    expect(filterItems(items, "all", all)).toHaveLength(4);
    expect(filterItems(items, "holding", all).map((i) => i.status)).toEqual(["holding", "own", "holding"]);
    expect(filterItems(items, "watch", all).map((i) => i.symbol)).toEqual(["W"]);
    expect(filterItems(items, "all", new Set(["earnings"] as const))).toHaveLength(2);
  });

  it("draws a month as whole weeks, a range across every day it spans", () => {
    const range = item({ date: "2026-10-29", date_end: "2026-11-02", symbol: "R", level: "info", status: "watch" });
    const day = item({ date: "2026-10-29", symbol: "D", level: "high", weight: 0.05 });
    const weeks = monthGrid([range, day], "2026-10", "2026-10-23");
    expect(weeks.every((w) => w.length === 7)).toBe(true);
    expect(weeks[0]![0]!.date).toBe("2026-09-28");                    // the Monday before 1 October
    expect(weeks.at(-1)!.at(-1)!.date).toBe("2026-11-01");            // the Sunday after 31 October
    const cells = new Map(weeks.flat().map((c) => [c.date, c]));
    expect(cells.get("2026-10-23")!.today).toBe(true);
    expect(cells.get("2026-10-29")!.entries.map((e) => [e.item.symbol, e.part])).toEqual([["D", "day"], ["R", "start"]]);
    expect(cells.get("2026-10-31")!.entries.map((e) => e.part)).toEqual(["mid"]);
    expect(cells.get("2026-11-01")!.entries.map((e) => e.part)).toEqual(["mid"]);   // clipped: the end lies in November
    expect(cells.get("2026-11-01")!.inMonth).toBe(false);
    const nov = new Map(monthGrid([range], "2026-11", "2026-10-23").flat().map((c) => [c.date, c]));
    expect(nov.get("2026-11-02")!.entries.map((e) => e.part)).toEqual(["end"]);
    expect(nov.get("2026-11-03")!.entries).toEqual([]);
  });

  it("colours levels and names the months of a window", () => {
    expect(LEVEL_KIND).toEqual({ high: "warn", normal: "accent", info: "na" });
    expect(monthsOf("2026-10-23", 35)).toEqual(["2026-10", "2026-11"]);
    expect(monthsOf("2026-12-20", 35)).toEqual(["2026-12", "2027-01"]);
  });

  it("writes a range as a range, never as its first day", () => {
    expect(when({ date: "2026-10-28", date_end: "2026-11-03" })).toBe("28 Oct – 3 Nov");
    expect(when({ date: "2026-10-28", date_end: null })).toBe("28 Oct");
    expect(when({ date: "2026-10-28", date_end: "2026-10-28" })).toBe("28 Oct");
    expect([inDays(0), inDays(4), inDays(-2)]).toEqual(["today", "in 4 d", "2 d ago"]);
  });

  it("keeps soon in the API's order and skips ids it doesn't know", () => {
    const a = item({ id: "a" }), b = item({ id: "b" });
    expect(soonItems({ items: [a, b], soon: ["b", "a", "gone"] }).map((i) => i.id)).toEqual(["b", "a"]);
  });
});

describe("glossary settings", () => {
  it("quotes a setting as written, or with |pct as a percentage", async () => {
    const { glossary } = await import("./glossary");
    const s = { "calendar.soon_days": "7", "calendar.highlight.big_position": "0.05", "calendar.highlight.near_level": "0.05" };
    const t = glossary("cal_level", s)!;
    expect(t).toContain("within 7 days");
    expect(t).toContain("at least 5% of");
    expect(glossary("cal_level", {})).toContain("within – days");
  });
});

import { describe, expect, it } from "vitest";
import { ALL_PAGES, groupOf, lastPage, NAV, remember } from "./nav";

function memory() {
  const m = new Map<string, string>();
  return { get: (k: string) => m.get(k) ?? null, set: (k: string, v: string) => void m.set(k, v) };
}

describe("navigation groups", () => {
  it("puts every page in exactly one group, with at most six per group", () => {
    const paths = ALL_PAGES.map((p) => p.path);
    expect(new Set(paths).size).toBe(paths.length);
    expect(NAV.every((g) => g.pages.length <= 6)).toBe(true);
  });

  it("finds the group of a page, its sub-pages and ticker pages", () => {
    expect(groupOf("/regime")?.id).toBe("markets");
    expect(groupOf("/notebook/journal/2026-09-01-X-buy")?.id).toBe("mine");
    expect(groupOf("/ops")?.id).toBe("system");
    expect(groupOf("/ticker/NOVO-B.CO")?.id).toBe("markets");
    expect(groupOf("/")).toBeNull();
    expect(groupOf("/guide/laerebog/rrg")).toBeNull();
    expect(groupOf("/regimes")).toBeNull();
  });

  it("returns to the page last opened in a group, else its first page", () => {
    const store = memory();
    const mine = NAV[1]!;
    expect(lastPage(mine, store)).toBe("/me");
    remember("/returns", "?pf=real", store);
    remember("/momentum", "", store);
    remember("/ticker/AAPL", "", store);            // a ticker page doesn't replace the Markets choice
    expect(lastPage(mine, store)).toBe("/returns?pf=real");
    expect(lastPage(NAV[0]!, store)).toBe("/momentum");
  });

  it("ignores broken or stale storage", () => {
    const store = memory();
    store.set("nav.last", "not json");
    expect(lastPage(NAV[2]!, store)).toBe("/data");
    store.set("nav.last", JSON.stringify({ system: "/regime" }));   // a page that moved to another group
    expect(lastPage(NAV[2]!, store)).toBe("/data");
  });
});

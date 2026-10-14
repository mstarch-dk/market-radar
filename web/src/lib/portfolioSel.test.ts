import { describe, expect, it } from "vitest";
import { DEFAULT_SEL, formatSel, isDefaultSel, parseSel, selQuery } from "./portfolioSel";

describe("parseSel", () => {
  it("defaults to your real portfolios for anything empty or unreadable", () => {
    expect(parseSel(null)).toEqual(DEFAULT_SEL);
    expect(parseSel("")).toEqual(DEFAULT_SEL);
    expect(parseSel("real")).toEqual(DEFAULT_SEL);
    expect(parseSel("nonsense,,x1")).toEqual(DEFAULT_SEL);
  });
  it("reads scopes, ids and tags, without duplicates", () => {
    expect(parseSel("virtual")).toEqual({ scope: "virtual" });
    expect(parseSel("3, 5,3,tag:Sim-A,tag:sim-a,tag:")).toEqual({ ids: [3, 5], tags: ["sim-a"] });
  });
});

describe("formatSel and selQuery", () => {
  it("round-trip through the URL", () => {
    for (const raw of ["real", "all", "3,5", "tag:a,tag:b", "7,tag:a"]) expect(formatSel(parseSel(raw))).toBe(raw);
  });
  it("send nothing for the default, so the API's own default (real) applies", () => {
    expect(selQuery(DEFAULT_SEL)).toBe("");
    expect(isDefaultSel(DEFAULT_SEL)).toBe(true);
    expect(selQuery({ scope: "all" })).toBe("scope=all");
    expect(selQuery(parseSel("3,tag:x y"))).toBe("portfolio=3&tag=x+y");
  });
});

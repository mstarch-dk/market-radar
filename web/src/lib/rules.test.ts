import { describe, expect, it } from "vitest";
import { actionProblem, attention, sortVerdicts, toAction, verdictValue } from "./rules";

type St = "breaks" | "near" | "unknown" | "judgment" | "complies" | "not_applicable";
const v = (rule_id: number, status: St, severity: "hard" | "soft" | "reminder") => ({ rule_id, status, severity });

describe("sortVerdicts", () => {
  it("puts breaks first, then close, unknown, questions, complies and doesn't apply; hard first within", () => {
    const rows = [v(1, "complies", "hard"), v(2, "not_applicable", "hard"), v(3, "breaks", "reminder"),
      v(4, "unknown", "soft"), v(5, "breaks", "hard"), v(6, "near", "soft"), v(7, "judgment", "soft")];
    expect(sortVerdicts(rows).map((r) => r.rule_id)).toEqual([5, 3, 6, 4, 7, 1, 2]);
    expect(attention(rows)).toBe(3);
  });
});

describe("the action form", () => {
  it("names the first problem", () => {
    expect(actionProblem({ side: "buy", ticker: " ", mode: "dkk", amount: "1000" })).toMatch(/ticker/);
    expect(actionProblem({ side: "buy", ticker: "X", mode: "dkk", amount: "0" })).toMatch(/above 0/);
    expect(actionProblem({ side: "buy", ticker: "X", mode: "fraction", amount: "0.5" })).toMatch(/sale/);
    expect(actionProblem({ side: "sell", ticker: "X", mode: "fraction", amount: "2" })).toMatch(/0 to 1/);
    expect(actionProblem({ side: "sell", ticker: "X", mode: "fraction", amount: "0,5" })).toBeNull();
  });
  it("sends exactly one amount", () => {
    const a = toAction({ side: "sell", ticker: "novo-b.co", portfolio: 2, mode: "fraction", amount: "0,5" });
    expect(a).toMatchObject({ ticker: "NOVO-B.CO", fraction: 0.5, amount_dkk: null, quantity: null, portfolio: 2 });
  });
});

describe("verdictValue", () => {
  it("shows a weight as a percentage and missing as a dash, never 0", () => {
    expect(verdictValue({ value: 0.162, unit: "pct" })).toBe("16.2 %");
    expect(verdictValue({ value: null, unit: "pct" })).toBe("–");
  });
});

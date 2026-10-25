import { describe, expect, it } from "vitest";
import { headStatus, meanWithT, strongT, tText } from "./evidence";

describe("report status", () => {
  it("greys a report of another rule and keeps its numbers inside the card", () => {
    expect(headStatus({ status: "stale", old_data: false, age_days: 3 })).toEqual(
      { label: "older rule", kind: "na", greyed: true, numbers: true });
  });

  it("calls a current report with old data so, without greying it", () => {
    const s = headStatus({ status: "ok", old_data: true, age_days: 70 });
    expect(s.label).toBe("old data (70 d)");
    expect(s.greyed).toBe(false);
    expect(headStatus({ status: "ok", old_data: false, age_days: 2 }).label).toBe("current");
  });

  it("has no numbers for a missing or unreadable report", () => {
    expect(headStatus({ status: "missing", old_data: false, age_days: null }).numbers).toBe(false);
    expect(headStatus({ status: "invalid", old_data: false, age_days: null })).toMatchObject({ label: "unreadable", numbers: false });
  });
});

describe("a mean next to its t", () => {
  const f = (v: number) => v.toFixed(2);

  it("prints the t with its sign", () => {
    expect(tText(0.05, 2.43)).toBe("t +2.4");
    expect(tText(-0.01, -0.5)).toBe("t -0.5");
    expect(meanWithT(0.05, 2.43, f)).toBe("0.05 (t +2.4)");
  });

  it("says when the t is missing instead of leaving it blank", () => {
    expect(tText(0.05, null)).toBe("t n/a");
    expect(meanWithT(0.05, undefined, f)).toBe("0.05 (t n/a)");
  });

  it("shows nothing for a missing mean, never 0", () => {
    expect(tText(null, 2)).toBe("");
    expect(meanWithT(null, 2, f)).toBe("–");
  });

  it("marks |t| of 2 or more", () => {
    expect(strongT(2)).toBe(true);
    expect(strongT(-2.1)).toBe(true);
    expect(strongT(1.9)).toBe(false);
    expect(strongT(null)).toBe(false);
  });
});

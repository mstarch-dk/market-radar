// The Evidence page's rules for showing a study report: its status as a word and a colour, whether its card is
// greyed (another rule: never mixed with current numbers), and a mean always next to its t.
// Pure, so the page and the tests share them.
import type { ReportHead } from "../api/client";
import { isNum, type Maybe } from "./format";

export type HeadStatus = { label: string; kind: "pos" | "warn" | "neg" | "na"; greyed: boolean; numbers: boolean };

/** How a report's header reads: current, old data (same rule), older rule (greyed), not run yet or unreadable.
 *  `numbers`: whether the card has numbers to show at all. */
export function headStatus(h: Pick<ReportHead, "status" | "old_data" | "age_days">): HeadStatus {
  switch (h.status) {
    case "ok":
      return h.old_data
        ? { label: `old data${isNum(h.age_days) ? ` (${h.age_days} d)` : ""}`, kind: "warn", greyed: false, numbers: true }
        : { label: "current", kind: "pos", greyed: false, numbers: true };
    case "stale":
      return { label: "older rule", kind: "na", greyed: true, numbers: true };
    case "missing":
      return { label: "not run yet", kind: "na", greyed: false, numbers: false };
    default:
      return { label: "unreadable", kind: "neg", greyed: false, numbers: false };
  }
}

/** A t-statistic as shown next to its mean: "t +2.4"; "t n/a" when the mean exists but the report has no t for it
 *  (an older report, or too few dates), so a missing t never reads as fine; "" without a mean. */
export function tText(mean: Maybe, t: Maybe, digits = 1): string {
  if (!isNum(mean)) return "";
  if (!isNum(t)) return "t n/a";
  return `t ${t >= 0 ? "+" : ""}${t.toFixed(digits)}`;
}

/** "+0.05 (t +2.4)", "+1.2% (t n/a)" or "–": a mean is never shown without its t. */
export function meanWithT(mean: Maybe, t: Maybe, fmt: (v: number) => string): string {
  return isNum(mean) ? `${fmt(mean)} (${tText(mean, t)})` : "–";
}

/** Whether a t clears the usual bar of 2 in absolute value (the page highlights those). */
export const strongT = (t: Maybe): boolean => isNum(t) && Math.abs(t) >= 2;

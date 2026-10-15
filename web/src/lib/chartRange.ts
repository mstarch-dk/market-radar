// The chart's time ranges. The numbers for each range (return, ACWI, high/low, base date) come from the API,
// counted like the Returns card; this only maps a range onto the chart's own sessions and rebases a line.

import { isNum, type Maybe } from "./format";

export type RangeKey = "1W" | "1M" | "3M" | "6M" | "YTD" | "1Y" | "3Y" | "5Y";

export const RANGES: RangeKey[] = ["1W", "1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y"];

/** Index of the last session on or before `start` (the range's base date), or 0 when it lies before the series. */
export function indexAt(dates: string[], start: string | null | undefined): number {
  if (!start) return 0;
  let lo = 0, hi = dates.length - 1, at = 0;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (dates[mid]! <= start) { at = mid; lo = mid + 1; } else hi = mid - 1;
  }
  return at;
}

/** The relative-strength line rebased to 100 at `from` (the first non-missing value from there). */
export function rebase(rel: Maybe[], from: number): (number | null)[] {
  let base: number | null = null;
  for (let i = from; i < rel.length; i++) {
    const v = rel[i];
    if (isNum(v) && v !== 0) { base = v; break; }
  }
  return rel.map((v) => (isNum(v) && base !== null ? (100 * v) / base : null));
}

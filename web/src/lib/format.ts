// Display formatting only: every number arrives computed from the API. Missing values render as an en dash,
// never as 0, so "no data" can't be mistaken for "no change".

export type Maybe = number | null | undefined;

const DASH = "–";

export const isNum = (v: Maybe): v is number => typeof v === "number" && Number.isFinite(v);

export function pct(v: Maybe, digits = 1, signed = true): string {
  if (!isNum(v)) return DASH;
  const s = (v * 100).toFixed(digits);
  return `${signed && v > 0 ? "+" : ""}${s === `-${(0).toFixed(digits)}` ? (0).toFixed(digits) : s}%`;
}

export function num(v: Maybe, digits = 2): string {
  if (!isNum(v)) return DASH;
  return v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** 1.13T, 4.06B, 12.3M, 950K */
export function compact(v: Maybe): string {
  if (!isNum(v)) return DASH;
  const a = Math.abs(v);
  for (const [div, unit] of [[1e12, "T"], [1e9, "B"], [1e6, "M"], [1e3, "K"]] as const) {
    if (a >= div) return `${(v / div).toFixed(a / div >= 100 ? 0 : a / div >= 10 ? 1 : 2)}${unit}`;
  }
  return v.toFixed(0);
}

export function price(v: Maybe, currency?: string | null): string {
  if (!isNum(v)) return DASH;
  const d = Math.abs(v) >= 1000 ? 0 : Math.abs(v) >= 1 ? 2 : 4;
  return `${num(v, d)}${currency ? ` ${currency}` : ""}`;
}

export function date(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(d.getTime())
    ? DASH
    : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

export function daysUntil(iso: string | null | undefined, today = new Date()): number | null {
  if (!iso) return null;
  const t = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) - t) / 86_400_000);
}

/** CSS class for a signed value */
export function tone(v: Maybe): "pos" | "neg" | "" {
  return !isNum(v) || v === 0 ? "" : v > 0 ? "pos" : "neg";
}

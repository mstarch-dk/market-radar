// Your trading rules (a mirror, never a gate): display helpers for verdicts and the action form's checks.
import type { ActionIn, RuleIn, RuleKind, RuleVerdict } from "../api/client";

export type VerdictStatus = RuleVerdict["status"];
export type Severity = RuleVerdict["severity"];

export const STATUS_TEXT: Record<VerdictStatus, string> = {
  breaks: "Breaks", near: "Close to", unknown: "Unknown", judgment: "Ask yourself", complies: "Complies",
  not_applicable: "Doesn't apply",
};
export const STATUS_KIND: Record<VerdictStatus, string> = {
  breaks: "neg", near: "warn", unknown: "na", judgment: "", complies: "pos", not_applicable: "",
};
const STATUS_ORDER: Record<VerdictStatus, number> = {
  breaks: 0, near: 1, unknown: 2, judgment: 3, complies: 4, not_applicable: 5,
};
const SEVERITY_ORDER: Record<Severity, number> = { hard: 0, soft: 1, reminder: 2 };
export const SEVERITY_KIND: Record<Severity, string> = { hard: "neg", soft: "warn", reminder: "" };

/** Breaks first, then close, unknown, the questions, complies and doesn't apply; hard before soft before reminder. */
export function sortVerdicts<T extends Pick<RuleVerdict, "status" | "severity" | "rule_id">>(rows: T[]): T[] {
  return [...rows].sort((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status]
    || SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity] || a.rule_id - b.rule_id);
}

/** How many verdicts need a look (breaks and close ones). */
export const attention = (rows: Pick<RuleVerdict, "status">[]) =>
  rows.filter((r) => r.status === "breaks" || r.status === "near").length;

export type AmountMode = "dkk" | "shares" | "fraction";

const number = (s: string) => Number(s.trim().replace(",", "."));

/** What is wrong with the action form, or null when it can be checked. */
export function actionProblem(a: { side: string; ticker: string; mode: AmountMode; amount: string }): string | null {
  if (!a.ticker.trim()) return "Choose a ticker.";
  const v = number(a.amount);
  if (!a.amount.trim() || !Number.isFinite(v) || v <= 0) return "Enter an amount above 0.";
  if (a.mode === "fraction" && a.side !== "sell") return "A share of the position is for a sale.";
  if (a.mode === "fraction" && v > 1) return "A share of the position is from 0 to 1 (1 = all of it).";
  return null;
}

/** The form as the API's ActionIn: exactly one of the amount, the shares or the share of the position. */
export function toAction(a: { side: "buy" | "sell"; ticker: string; portfolio: number | null; mode: AmountMode;
  amount: string; style?: ActionIn["style"]; horizon?: ActionIn["horizon"] }): ActionIn {
  const v = number(a.amount);
  return {
    side: a.side, ticker: a.ticker.trim().toUpperCase(), portfolio: a.portfolio, style: a.style ?? null,
    horizon: a.horizon ?? null, amount_dkk: a.mode === "dkk" ? v : null, quantity: a.mode === "shares" ? v : null,
    fraction: a.mode === "fraction" ? v : null, log: false,
  };
}

/** A rule's numbers in words, e.g. "Max weight (%): 10" (exposures and tickers listed). */
export function paramText(kind: RuleKind | undefined, params: RuleIn["params"]): string {
  if (!kind) return "";
  return kind.params.map((p) => {
    const v = params?.[p.key];
    if (v === undefined || v === null) return null;
    if (p.type === "exposures") return `${p.label}: ${(v as { kind: string; key: string }[]).map((e) => `${e.kind} ${e.key}`).join(", ")}`;
    if (p.type === "tickers") return `${p.label}: ${(v as string[]).join(", ")}`;
    return `${p.label}: ${String(v)}`;
  }).filter(Boolean).join(" · ");
}

/** A verdict's value in its unit (a weight, an amount, a count); missing is a dash, never 0. */
export function verdictValue(v: Pick<RuleVerdict, "value" | "unit">): string {
  if (v.value === null || v.value === undefined) return "–";
  if (v.unit === "pct") return `${(v.value * 100).toFixed(1)} %`;
  if (v.unit === "dkk") return `${Math.round(v.value).toLocaleString("da-DK")} DKK`;
  if (v.unit === "score") return v.value.toFixed(0);
  return String(Math.round(v.value * 100) / 100);
}

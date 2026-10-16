import type { components } from "../api/schema";
import { date, isNum, num, pct, type Maybe } from "../lib/format";
import type { Col } from "./columns";
import { Graded } from "./Gauge";

type Row = Pick<components["schemas"]["MyRow"], "quality" | "value" | "qv" | "q_n" | "v_n" | "fund_source" | "fund_period_end"
  | "fcf_yield" | "ev_ebit" | "roic" | "fund_gauges">;   // api_models StockFundamentals

/** "3/4": how many of the four pillars (or value metrics) a score rests on. */
export const coverage = (n: number | null | undefined) => (n == null ? "–" : `${n}/4`);
export const times = (v: Maybe, digits = 1) => (isNum(v) ? `${num(v, digits)}×` : "–");

/** Kvalitetsscore, værdiscore and K+V columns for a stock table (fundamentals/context.py). Missing statements show as
 *  a dash, never as 0. `show` lists the columns visible by default; the rest can be switched on. */
export function scoreCols<T extends Row>(show: string[] = ["quality", "value"]): Col<T>[] {
  const cols: Col<T>[] = [
    { key: "qv", label: "K+V", name: "Quality + value (mean)", sort: (r) => r.qv, help: "qv", filter: { kind: "range", unit: "num" },
      render: (r) => num(r.qv, 0) },
    { key: "quality", label: "Quality", name: "Kvalitetsscore", sort: (r) => r.quality, help: "quality", filter: { kind: "range", unit: "num" },
      render: (r) => <Graded g={r.fund_gauges?.quality}>{num(r.quality, 0)}</Graded> },
    { key: "value", label: "Value", name: "Værdiscore", sort: (r) => r.value, help: "value", filter: { kind: "range", unit: "num" },
      render: (r) => <Graded g={r.fund_gauges?.value}>{num(r.value, 0)}</Graded> },
    { key: "fcf_yield", label: "FCF yield", name: "Free cash flow yield", sort: (r) => r.fcf_yield, help: "fcf_yield",
      filter: { kind: "range", unit: "pct" }, render: (r) => pct(r.fcf_yield, 1, false) },
    { key: "ev_ebit", label: "EV/EBIT", sort: (r) => r.ev_ebit, help: "ev_ebit", render: (r) => times(r.ev_ebit) },
    { key: "roic", label: "ROIC", sort: (r) => r.roic, help: "roic", render: (r) => pct(r.roic, 0, false) },
    { key: "fund_source", label: "Statements", name: "Statements (source, latest period)", align: "l", help: "fund_source",
      sort: (r) => r.fund_period_end, filter: { kind: "enum", value: (r) => r.fund_source ?? "none" }, csv: (r) => r.fund_source,
      render: (r) => r.fund_source
        ? <span className="muted small">{r.fund_source === "edgar" ? "EDGAR" : "Yahoo"} · {date(r.fund_period_end)}</span>
        : <span className="muted">–</span> },
  ];
  return cols.map((c) => ({ ...c, hidden: !show.includes(c.key) }));
}

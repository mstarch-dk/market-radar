import type { components } from "../api/schema";
import { date, num, pct } from "../lib/format";
import type { Col } from "./columns";
import { Graded } from "./Gauge";

type Row = components["schemas"]["MyRow"];   // carries both sets of fields (api_models StockValuation, FundValuation)
type StockVal = Pick<Row, "pe_fy1" | "pe_cy" | "pe_ttm" | "pe_vs_sector" | "eps_rev_4w" | "eps_rev_12w" | "div_yield"
  | "earnings_date" | "val_gauges">;
type FundVal = Pick<Row, "pe" | "pe_vs_acwi" | "pe_pct" | "val_gauges">;

const times = (v: number | null | undefined) => (v == null ? "–" : `${num(v, 2)}×`);

/** Valuation columns for a stock table (weekly snapshot): P/E on next year's EPS, tinted by how it compares with
 * its sector, is shown; the other bases, the ratio itself and the EPS revisions can be switched on. */
export function stockValCols<T extends StockVal>(): Col<T>[] {
  return [
    { key: "pe_fy1", label: "P/E next yr", name: "P/E on next year's EPS", sort: (r) => r.pe_fy1, help: "pe_fy1",
      filter: { kind: "range", unit: "num" },
      render: (r) => <Graded g={r.val_gauges?.pe_vs_sector}>{num(r.pe_fy1, 1)}</Graded> },
    { key: "pe_vs_sector", label: "vs sector", name: "P/E vs sector median", sort: (r) => r.pe_vs_sector, help: "pe_vs_sector",
      hidden: true, filter: { kind: "range", unit: "num" },
      render: (r) => <Graded g={r.val_gauges?.pe_vs_sector}>{times(r.pe_vs_sector)}</Graded> },
    { key: "pe_cy", label: "P/E this yr", name: "P/E on this year's EPS", sort: (r) => r.pe_cy, help: "pe_cy", hidden: true,
      render: (r) => num(r.pe_cy, 1) },
    { key: "pe_ttm", label: "P/E ttm", name: "P/E on trailing 12-month EPS", sort: (r) => r.pe_ttm, help: "pe_ttm", hidden: true,
      render: (r) => num(r.pe_ttm, 1) },
    { key: "eps_rev_4w", label: "EPS rev 4w", name: "EPS estimate change, 4 weeks", sort: (r) => r.eps_rev_4w, help: "eps_rev",
      hidden: true, filter: { kind: "range", unit: "pct" },
      render: (r) => <Graded g={r.val_gauges?.eps_rev}>{pct(r.eps_rev_4w)}</Graded> },
    { key: "eps_rev_12w", label: "EPS rev 12w", name: "EPS estimate change, 12 weeks", sort: (r) => r.eps_rev_12w, help: "eps_rev",
      hidden: true, render: (r) => pct(r.eps_rev_12w) },
    { key: "div_yield", label: "Div yield", name: "Dividend yield (trailing)", sort: (r) => r.div_yield, help: "div_yield",
      hidden: true, render: (r) => pct(r.div_yield, 1, false) },
    { key: "earnings", label: "Earnings", name: "Next earnings date", sort: (r) => r.earnings_date, help: "earnings_date",
      hidden: true, render: (r) => date(r.earnings_date) },
  ];
}

/** Valuation columns for a fund table: Yahoo's fund P/E, tinted against ACWI's. */
export function fundValCols<T extends FundVal>(): Col<T>[] {
  return [
    { key: "pe", label: "P/E", name: "Fund P/E", sort: (r) => r.pe, help: "fund_pe", filter: { kind: "range", unit: "num" },
      render: (r) => <Graded g={r.val_gauges?.pe_vs_acwi}>{num(r.pe, 1)}</Graded> },
    { key: "pe_vs_acwi", label: "vs ACWI", name: "P/E vs ACWI", sort: (r) => r.pe_vs_acwi, help: "pe_vs_acwi", hidden: true,
      render: (r) => <Graded g={r.val_gauges?.pe_vs_acwi}>{times(r.pe_vs_acwi)}</Graded> },
    { key: "pe_pct", label: "P/E pct", name: "P/E percentile in its own history", sort: (r) => r.pe_pct, help: "pe_pct", hidden: true,
      render: (r) => <Graded g={r.val_gauges?.pe_pct}>{num(r.pe_pct, 0)}</Graded> },
  ];
}

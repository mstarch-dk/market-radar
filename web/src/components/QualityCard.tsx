import type { Profile, QualityCard as Card_ } from "../api/client";
import { compact, date, isNum, num, pct, type Maybe } from "../lib/format";
import type { GlossaryKey } from "../lib/glossary";
import { coverage, times } from "./fundCols";
import { GaugeBadge, lvClass } from "./Gauge";
import { Sparkline } from "./Sparkline";
import { Term } from "./Term";
import { Card } from "./ui";

type Metric = Card_["metrics"][number];

const PCT = new Set(["fcf_margin", "roic", "fcf_yield", "ebit_ev", "shareholder_yield", "roe", "equity_assets", "ep"]);
const PP = new Set(["gm_stability", "roe_stability"]);
const TIMES = new Set(["nd_ebitda", "interest_cover", "bp"]);

/** A metric's own value in its unit: a share, percentage points, a multiple, a percentile or a count. */
function fmt(m: Metric): string {
  const v: Maybe = m.value;
  if (!isNum(v)) return "–";
  if (PCT.has(m.key)) return pct(v, 1, false);
  if (PP.has(m.key)) return `${num(v, 1)} pp`;
  if (TIMES.has(m.key)) return times(v, m.key === "interest_cover" ? 0 : 1);
  if (m.key === "div_years") return num(v, 0);
  if (m.key.endsWith("_vs_history")) return `${num(v, 0)} / 100`;
  return num(v, 2);
}

const PILLARS: [string, string][] = [["profitability", "Profitability"], ["durability", "Durability"], ["balance", "Balance sheet"],
  ["record", "Dividend record"], ["value", "Value"]];
const SOURCE = { edgar: "SEC EDGAR", yahoo: "Yahoo statements" } as const;
const BASIS: Record<string, string> = { fy: "the latest fiscal year", ytd: "fiscal year + year to date", "4q": "four quarters",
  yahoo_ttm: "Yahoo's trailing twelve months" };

function Score({ label, help, v, n, g }: { label: string; help: GlossaryKey; v: Maybe; n?: number | null; g?: Card_["gauges"][string] }) {
  return (
    <div className={`gl ${lvClass(g)}`}>
      <div className="gl-k"><Term k={help}>{label}</Term></div>
      <div className="gl-v">{isNum(v) ? num(v, 0) : "–"} <small>/ 100</small> {g && <GaugeBadge g={g} name={label} />}</div>
      {n !== undefined && <div className="gl-s">rests on {coverage(n)}</div>}
    </div>
  );
}

/** The ticker page's kvalitetsscore and værdiscore: the scores, every metric with its value and percentile among
 *  the peers, the fiscal years behind the stability measures, and where the figures come from. */
export function QualityCard({ p }: { p: Profile }) {
  const c = p.quality;
  if (!c) return null;
  if (c.status === "missing") return (
    <Card title="Quality & value" meta={c}>
      <p className="empty">No score: {c.notes.length ? c.notes.join("; ") : "no statements stored for this stock"}.</p>
    </Card>
  );
  const by = (pillar: string) => c.metrics.filter((m) => m.pillar === pillar);
  return (
    <Card title="Quality & value" meta={c}>
      <div className="glance q-scores">
        <Score label="Quality" help="quality" v={c.quality} n={c.q_n} g={c.gauges.quality} />
        <Score label="Value" help="value" v={c.value} n={c.v_n} g={c.gauges.value} />
        <Score label="K+V" help="qv" v={c.qv} />
      </div>
      <table className="t q-metrics">
        <thead><tr><th>Metric</th><th>Value</th><th>Percentile among peers</th></tr></thead>
        <tbody>
          {PILLARS.map(([key, label]) => by(key).length > 0 && [
            <tr key={key} className="q-pillar"><td colSpan={3}><b>{label}</b>
              {key !== "value" && isNum(c.pillars[key]) && <span className="muted"> · {num(c.pillars[key], 0)}</span>}</td></tr>,
            ...by(key).map((m) => (
              <tr key={m.key}>
                <td>{m.key in TERMS ? <Term k={TERMS[m.key]!}>{m.label}</Term> : m.label}</td>
                <td className="num">{fmt(m)}</td>
                <td className="pct">
                  {isNum(m.pct)
                    ? <span className="q-bar" title={`${m.basis === "sector" ? "sector" : "whole universe"}, ${m.peers ?? "?"} peers`}>
                        <span className="stack"><span className="bar" style={{ width: `${m.pct}%` }} /></span>
                        <span className="num small">{num(m.pct, 0)}</span>
                        <span className="muted small">{m.basis === "sector" ? "sector" : "all"} · {m.peers ?? "?"}</span>
                      </span>
                    : <span className="muted">–</span>}
                </td>
              </tr>
            )),
          ])}
        </tbody>
      </table>
      {c.history.length > 0 && (
        <>
          <h3>Fiscal years</h3>
          <table className="t">
            <thead><tr><th>Year end</th><th>Revenue{c.currency ? ` (${c.currency})` : ""}</th><th>Gross margin</th><th>FCF margin</th></tr></thead>
            <tbody>
              {[...c.history].reverse().map((y) => (
                <tr key={y.year}><td>{date(y.year)}</td><td className="num">{compact(y.revenue)}</td>
                  <td className="num">{pct(y.gross_margin, 1, false)}</td><td className="num">{pct(y.fcf_margin, 1, false)}</td></tr>
              ))}
            </tbody>
          </table>
          <Sparkline values={c.history.map((y) => y.revenue).filter(isNum)} />
        </>
      )}
      <p className="small muted">
        <Term k="fund_source">{c.fund_source ? SOURCE[c.fund_source] : "Statements"}</Term>
        {c.fund_set === "financial" && " · the bank and insurer set"}
        {c.period_end && <> · figures to {date(c.period_end)}</>}
        {c.filed && <> · filed {date(c.filed)}</>}
        {c.ttm_basis && <> · last 12 months from {BASIS[c.ttm_basis] ?? c.ttm_basis}</>}
        {isNum(c.market_cap) && <> · market value {compact(c.market_cap)} {c.currency ?? ""}</>}
        {isNum(c.ev_ebit) && <> · EV/EBIT {times(c.ev_ebit)}</>}.
      </p>
      {c.notes.length > 0 && <ul className="small muted">{c.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
    </Card>
  );
}

const TERMS: Record<string, GlossaryKey> = {
  fcf_margin: "fcf_margin", roic: "roic", gm_stability: "gm_stability", rev_stability: "rev_stability", nd_ebitda: "nd_ebitda",
  interest_cover: "interest_cover", div_years: "div_years", fcf_yield: "fcf_yield", ebit_ev: "ev_ebit",
  shareholder_yield: "shareholder_yield", ey_vs_history: "ey_vs_history", ep_vs_history: "ey_vs_history", roe: "roe", bp: "bp",
};

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type AbTest, type QualityRow } from "../api/client";
import { Loaded, PageHead, Pct } from "../components/cells";
import { DataTable, type Col } from "../components/DataTable";
import { coverage, times } from "../components/fundCols";
import { Graded } from "../components/Gauge";
import { LineChart } from "../components/LineChart";
import { TableToolbar } from "../components/TableToolbar";
import { Term } from "../components/Term";
import { TickerLink, TickerList } from "../components/TickerLink";
import { WatchStar } from "../components/WatchButton";
import { date, num, pct } from "../lib/format";

type By = "qv" | "quality" | "value";
const BY: [By, string][] = [["qv", "Quality + value"], ["quality", "Quality"], ["value", "Value"]];
const RANK: Record<By, (r: QualityRow) => number | null | undefined> = {
  qv: (r) => r.rank_qv, quality: (r) => r.rank_q, value: (r) => r.rank_v };

const cols: Col<QualityRow>[] = [
  { key: "name", label: "Company", align: "l", sort: (r) => r.name ?? r.ticker, search: (r) => `${r.name ?? ""} ${r.ticker}`,
    csv: (r) => r.ticker, csvHeader: "Ticker",
    render: (r) => <><TickerLink symbol={r.ticker} name={r.name} nameFirst />{r.new && <span className="new">NEW</span>}</> },
  { key: "sector", label: "Sector", align: "l", sort: (r) => r.sector, search: (r) => r.sector, filter: { kind: "enum" },
    render: (r) => <span className="muted">{r.sector || "–"}{r.fund_set === "financial" && <> · <Term k="roe">bank/insurer</Term></>}</span> },
  { key: "industry", label: "Industry", align: "l", sort: (r) => r.industry, search: (r) => r.industry, filter: { kind: "enum" }, hidden: true,
    render: (r) => <span className="muted">{r.industry || "–"}</span> },
  { key: "qv", label: "K+V", name: "Quality + value", sort: (r) => r.qv, help: "qv", filter: { kind: "range", unit: "num" },
    render: (r) => <b>{num(r.qv, 0)}</b> },
  { key: "quality", label: "Quality", sort: (r) => r.quality, help: "quality", filter: { kind: "range", unit: "num" },
    render: (r) => <Graded g={r.fund_gauges?.quality}>{num(r.quality, 0)}</Graded> },
  { key: "value", label: "Value", sort: (r) => r.value, help: "value", filter: { kind: "range", unit: "num" },
    render: (r) => <Graded g={r.fund_gauges?.value}>{num(r.value, 0)}</Graded> },
  { key: "cov", label: "Basis", name: "Pillars / value metrics scored", help: "q_n", sort: (r) => (r.q_n ?? 0) + (r.v_n ?? 0),
    csv: (r) => `${r.q_n ?? ""}/${r.v_n ?? ""}`, render: (r) => <span className="muted small">{coverage(r.q_n)} · {coverage(r.v_n)}</span> },
  { key: "momentum", label: "Momentum", name: "Momentum score (region)", sort: (r) => r.momentum, help: "score",
    filter: { kind: "range", unit: "num" }, render: (r) => <span className="muted">{num(r.momentum, 0)}</span> },
  { key: "q_profitability", label: "Profit.", name: "Pillar: profitability", sort: (r) => r.q_profitability, help: "fund_pillars", hidden: true,
    render: (r) => num(r.q_profitability, 0) },
  { key: "q_durability", label: "Durab.", name: "Pillar: durability", sort: (r) => r.q_durability, help: "fund_pillars", hidden: true,
    render: (r) => num(r.q_durability, 0) },
  { key: "q_balance", label: "Balance", name: "Pillar: balance sheet", sort: (r) => r.q_balance, help: "fund_pillars", hidden: true,
    render: (r) => num(r.q_balance, 0) },
  { key: "q_record", label: "Record", name: "Pillar: dividend record", sort: (r) => r.q_record, help: "fund_pillars", hidden: true,
    render: (r) => num(r.q_record, 0) },
  { key: "fcf_margin", label: "FCF margin", sort: (r) => r.fcf_margin, help: "fcf_margin", hidden: true,
    render: (r) => pct(r.fcf_margin, 0, false) },
  { key: "roic", label: "ROIC", sort: (r) => r.roic, help: "roic", render: (r) => pct(r.roic, 0, false) },
  { key: "roe", label: "ROE", sort: (r) => r.roe, help: "roe", hidden: true, render: (r) => pct(r.roe, 0, false) },
  { key: "gm_stability", label: "GM spread", name: "Gross-margin spread (pp)", sort: (r) => r.gm_stability, help: "gm_stability",
    hidden: true, render: (r) => num(r.gm_stability, 1) },
  { key: "rev_stability", label: "Rev. steady", name: "Revenue steadiness", sort: (r) => r.rev_stability, help: "rev_stability",
    hidden: true, render: (r) => num(r.rev_stability, 2) },
  { key: "rev_cagr", label: "Rev. growth", name: "Revenue growth per year", sort: (r) => r.rev_cagr, help: "rev_cagr", hidden: true,
    render: (r) => <Pct v={r.rev_cagr} /> },
  { key: "nd_ebitda", label: "ND/EBITDA", name: "Net debt / EBITDA", sort: (r) => r.nd_ebitda, help: "nd_ebitda",
    render: (r) => times(r.nd_ebitda) },
  { key: "interest_cover", label: "Int. cover", name: "Interest cover", sort: (r) => r.interest_cover, help: "interest_cover",
    hidden: true, render: (r) => times(r.interest_cover, 0) },
  { key: "div_years", label: "Div. years", name: "Dividend years", sort: (r) => r.div_years, help: "div_years",
    render: (r) => num(r.div_years, 0) },
  { key: "fcf_yield", label: "FCF yield", sort: (r) => r.fcf_yield, help: "fcf_yield", filter: { kind: "range", unit: "pct" },
    render: (r) => pct(r.fcf_yield, 1, false) },
  { key: "ev_ebit", label: "EV/EBIT", sort: (r) => r.ev_ebit, help: "ev_ebit", render: (r) => times(r.ev_ebit) },
  { key: "shareholder_yield", label: "Sh. yield", name: "Shareholder yield", sort: (r) => r.shareholder_yield, help: "shareholder_yield",
    render: (r) => pct(r.shareholder_yield, 1, false) },
  { key: "ey_vs_history", label: "vs own hist.", name: "EBIT/EV vs own history (percentile)", sort: (r) => r.ey_vs_history,
    help: "ey_vs_history", hidden: true, render: (r) => num(r.ey_vs_history, 0) },
  { key: "pb", label: "P/B", sort: (r) => r.pb, help: "pb", hidden: true, render: (r) => times(r.pb) },
  { key: "fund_source", label: "Statements", name: "Statements (source, latest period)", align: "l", help: "fund_source",
    sort: (r) => r.fund_period_end, filter: { kind: "enum", value: (r) => r.fund_source ?? "none" }, csv: (r) => r.fund_source,
    render: (r) => <span className="muted small">{r.fund_source === "edgar" ? "EDGAR" : "Yahoo"} · {date(r.fund_period_end)}</span> },
  { key: "star", label: "", name: "Watch", render: (r) => <WatchStar symbol={r.ticker} />, csv: false },
];

const withRank = (by: By): Col<QualityRow>[] => [
  { key: "rank", label: "#", sort: RANK[by], help: "rank", render: (r) => <span className="muted">{RANK[by](r) ?? "–"}</span> },
  ...cols,
];

/** The forward A/B test: start it, or follow the three baskets against ACWI. */
function AbPanel() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["abtest"], queryFn: api.abtest, retry: false, staleTime: 5 * 60_000 });
  const start = useMutation({ mutationFn: () => api.startAbtest({}),
    onSuccess: (d) => { qc.setQueryData(["abtest"], d); qc.invalidateQueries({ queryKey: ["portfolios"] }); } });
  if (q.isPending) return <div className="skeleton" style={{ height: 120 }} aria-busy="true" />;
  if (q.isError) return <p className="error">Couldn&apos;t load the A/B test: {q.error.message}</p>;
  const d = q.data;
  return (
    <section id="ab" className="group">
      <h2><Term k="ab_test">A/B test: quality + value vs momentum</Term></h2>
      {!d.running ? (
        <div className="card">
          <p>
            Three virtual baskets, bought on the scores of the first report each month: the top names by quality + value,
            the top names by momentum (pooled over every region) and a 50/50 mix of the two. They run forward from today, so
            the comparison can&apos;t be fitted to the past. Nothing is bought for real.
          </p>
          <button type="button" className="btn" onClick={() => start.mutate()} disabled={start.isPending}>
            {start.isPending ? "Starting…" : "Start the A/B test"}
          </button>
          {start.isError && <p className="error">{start.error.message}</p>}
        </div>
      ) : <AbRunning d={d} />}
    </section>
  );
}

function AbRunning({ d }: { d: AbTest }) {
  const latest = useMemo(() => {
    const out = new Map<string, AbTest["rebalances"][number]>();
    for (const r of d.rebalances) out.set(r.kind, r);   // in date order: the last one per basket wins
    return [...out.values()];
  }, [d.rebalances]);
  const c = d.correlation;
  return (
    <>
      <p className="small muted">
        Next picks due {date(d.next_due)} (the first report that month).{" "}
        <Link to={`/returns?pf=tag:ab-qvm`}>Open on the Returns page</Link>.
      </p>
      {d.notes.length > 0 && <ul className="small muted">{d.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
      {d.comparison && d.comparison.rows.some((r) => r.stats) && (
        <div className="card">
          <LineChart chart={d.comparison.chart} height={280} />
          <table className="t">
            <thead><tr><th>Basket</th><th>From</th><th><Term k="twr">Return</Term></th><th><Term k="acwi_twr">ACWI</Term></th>
              <th><Term k="excess_twr">vs ACWI</Term></th><th><Term k="max_drawdown">Max drawdown</Term></th></tr></thead>
            <tbody>
              {d.comparison.rows.map((r) => (
                <tr key={r.label}>
                  <td>{r.label}</td><td>{date(r.stats?.start)}</td><td><Pct v={r.stats?.twr_total} /></td>
                  <td><Pct v={r.stats?.acwi_twr_total} /></td><td><Pct v={r.stats?.excess_twr} /></td><td><Pct v={r.stats?.max_drawdown} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {c && (
        <div className="card">
          <h3><Term k="ab_corr">Correlation of weekly returns</Term> <span className="muted small">({c.weeks} weeks)</span></h3>
          <table className="t">
            <thead><tr><th />{c.symbols.map((s) => <th key={s}>{s}</th>)}</tr></thead>
            <tbody>
              {c.symbols.map((s, i) => (
                <tr key={s}><td>{s}</td>{c.matrix[i]!.map((v, j) => <td key={j} className="num">{num(v, 2)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="ab-picks">
        {latest.map((r) => (
          <div key={r.kind} className="card">
            <h3>{r.label} <span className="muted small">picked {date(r.date)} ·{" "}
              {d.rebalances.filter((x) => x.kind === r.kind).length === 1 ? "first picks"
                : <><Term k="turnover">turnover</Term> {pct(r.turnover, 0, false)}</>}</span></h3>
            <TickerList symbols={[...r.picks].sort((a, b) => b.weight - a.weight).map((p) => p.ticker)} />
          </div>
        ))}
      </div>
    </>
  );
}

/** Kvalitetsscore and værdiscore per region: the businesses that earn well, steadily and safely, and what they cost. */
export function Quality() {
  const q = useQuery({ queryKey: ["quality"], queryFn: api.quality, retry: false, staleTime: 5 * 60_000 });
  const [params, setParams] = useSearchParams();
  const by = (BY.find(([k]) => k === params.get("by"))?.[0] ?? "qv") as By;
  const [all, setAll] = useState(false);
  const setBy = (v: By) => setParams((p) => {
    const next = new URLSearchParams(p);
    if (v === "qv") next.delete("by"); else next.set("by", v);
    return next;
  }, { replace: true });
  const tableCols = useMemo(() => withRank(by), [by]);
  return (
    <Loaded q={q} title="Quality & value">
      {(d) => {
        const shown = d.regions.map((r) => {
          const ranked = r.rows.filter((x) => RANK[by](x) != null).sort((a, b) => RANK[by](a)! - RANK[by](b)!);
          return { ...r, ranked, view: all ? ranked : ranked.slice(0, d.top_n) };
        });
        return (
          <>
            <PageHead title="Quality & value" asof={d.asof} generated={d.generated} ageDays={d.age_days} stale={d.stale}>
              Two scores from the companies&apos; reported statements, not from prices, each 0–100 among the sector&apos;s
              peers across regions. <b>Quality</b>: free cash flow and ROIC, steady margins and revenue, a sound balance
              sheet and a dividend record. <b>Value</b>: free cash flow yield, EBIT / EV, cash returned to owners and the
              price against the company&apos;s own history. <b>K+V</b> is their mean. A missing statement shows as a dash, never
              as 0. <span className="new">NEW</span> marks names new in the top {d.top_n} since {d.prev ? date(d.prev) : "– (no earlier snapshot yet)"}.
              A cheap stock can be cheap for a reason: read value with quality, and both with the story. Analysis, not advice.
            </PageHead>
            <div className="q-controls small">
              <span className="muted">Rank by</span>
              <span className="seg" role="group" aria-label="Rank by">
                {BY.map(([k, label]) => (
                  <button key={k} type="button" aria-pressed={k === by} onClick={() => setBy(k)}>{label}</button>
                ))}
              </span>
              <label className="chip-check"><input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} />
                every scored stock, not just the top {d.top_n}</label>
            </div>
            <nav className="jump">{d.regions.map((r) => <a key={r.key} href={`#${r.key}`}>{r.label}</a>)}<a href="#ab">A/B test</a></nav>
            <div className="sticky-tools">
              <TableToolbar id="q" csvName="quality" rows={shown.flatMap((r) => r.view)} cols={tableCols} />
              <p className="small muted">Search, filters and columns apply to every region below.</p>
            </div>
            {shown.map((r) => (
              <section key={r.key} id={r.key} className="group">
                <h2>{r.label}</h2>
                <p className="small muted">
                  {r.coverage.quality} of {r.coverage.stocks} stocks have a quality score and {r.coverage.value} a value score
                  ({r.coverage.edgar} from SEC EDGAR, {r.coverage.yahoo} from Yahoo).
                  {r.coverage.quality < r.coverage.stocks && " The rest have no statements yet, or too few figures."}
                </p>
                {r.dropped.length > 0 && <p className="note muted">Dropped out of the top {d.top_n} (K+V): <TickerList symbols={r.dropped} /></p>}
                {r.ranked.length === 0
                  ? <p className="note">No stock in this region has a score yet. Statements are fetched in the daily update
                    (or <code>uv run radar fundamentals update --all</code>).</p>
                  : <div className="card"><DataTable id="q" toolbar={false} rows={r.view} cols={tableCols} rowKey={(x) => x.ticker} /></div>}
              </section>
            ))}
            <AbPanel />
          </>
        );
      }}
    </Loaded>
  );
}

import { useQuery } from "@tanstack/react-query";
import { api, type PositioningView } from "../api/client";
import { Loaded, PageHead } from "../components/cells";
import { DataTable, type Col } from "../components/DataTable";
import { GaugeBadge, Graded } from "../components/Gauge";
import { LineChart } from "../components/LineChart";
import { Term } from "../components/Term";
import { Badge } from "../components/ui";
import { date, num, pct, tone } from "../lib/format";

type Cot = PositioningView["cot"][number];

const signed = (v: number | null | undefined, d = 1) => (v == null ? "–" : `${v > 0 ? "+" : ""}${v.toFixed(d)}`);

const cotCols: Col<Cot>[] = [
  { key: "market", label: "Market", align: "l", sort: (r) => r.market, render: (r) => r.market, search: (r) => r.market, filter: { kind: "enum" } },
  { key: "group", label: "Trader group", align: "l", sort: (r) => r.group, render: (r) => r.group, filter: { kind: "enum" } },
  { key: "net", label: "Net % of OI", sort: (r) => r.net_pct_oi, render: (r) => `${signed(r.net_pct_oi)}%`, help: "cot_net" },
  { key: "chg", label: "4w change", sort: (r) => r.chg_4w, render: (r) => <span className={tone(r.chg_4w)}>{signed(r.chg_4w)}</span>, help: "cot_chg" },
  { key: "pct", label: "3y percentile", sort: (r) => r.percentile, render: (r) => <Graded g={r.gauge}>{num(r.percentile, 0)}</Graded>, help: "cot_pct", filter: { kind: "range", unit: "num" } },
  { key: "flag", label: "Flag", align: "l", sort: (r) => r.flag, render: (r) => r.flag ? <Badge>{r.flag}</Badge> : null, filter: { kind: "enum" } },
  { key: "asof", label: "As of", sort: (r) => r.asof, render: (r) => date(r.asof) },
];

const PHASE_KIND: Record<string, string> = { Expansion: "pos", Contraction: "neg" };

type Val = NonNullable<PositioningView["valuation"]>;
type Rev = NonNullable<PositioningView["revisions"]>;
type RevRow = Rev["windows"][number]["rows"][number];
type Sent = NonNullable<PositioningView["sentiment"]>;
type RatesT = NonNullable<PositioningView["rates"]>;

const ordinal = (v: number | null | undefined) => (v == null ? "–" : `${v.toFixed(0)}th`);

function ValuationCard({ v }: { v: Val }) {
  const { cape, erp, yield_gap: gap } = v;
  if (!cape && !erp && !gap) return <p className="note muted">No valuation data yet. Run <code>radar update</code>.</p>;
  return (
    <>
      <div className="card">
        <div className="hero">
          {cape && <div><div className="sub"><Term k="cape">Shiller CAPE</Term> (S&amp;P 500)</div>
            <div className="big">{num(cape.value, 1)}</div>
            <div className="sub"><GaugeBadge g={cape.gauge} name="CAPE percentile" /> {ordinal(cape.pct_all)} percentile since {cape.since.slice(0, 4)}
              {" "}· {ordinal(cape.pct_1990)} since 1990 · median {num(cape.median, 1)}</div></div>}
          {erp && <div><div className="sub"><Term k="erp">Implied equity risk premium</Term> (Damodaran)</div>
            <div className="big">{pct(erp.value, 2, false)}</div>
            <div className="sub"><GaugeBadge g={erp.gauge} name="ERP percentile" /> {ordinal(erp.pct)} percentile since {erp.since.slice(0, 4)}
              {" "}· median {pct(erp.median, 2, false)} · {date(erp.asof)}</div></div>}
          {gap && <div><div className="sub"><Term k="yield_gap">Earnings yield − real yield</Term></div>
            <div className="big">{num(gap.value, 2)}<span className="unit"> pts</span></div>
            <div className="sub"><GaugeBadge g={gap.gauge} name="Yield gap" /> {num(gap.earnings_yield, 2)}% (forward P/E {num(gap.fwd_pe, 1)})
              {" "}− {num(gap.real_yield, 2)}% US 10Y real</div></div>}
        </div>
        <p className="note muted">Valuation says a lot about the next ten years and little about the next months: a stretched
          market can stay stretched for a long time. It only votes in the regime if you switch it on there. CAPE: multpl.com
          (Shiller&apos;s method, unofficial). ERP: Aswath Damodaran, NYU Stern (monthly).</p>
      </div>
      {v.charts.length > 0 && <div className="grid charts">{v.charts.map((c) => <LineChart key={c.title} chart={c} />)}</div>}
    </>
  );
}

const revCols: Col<RevRow>[] = [
  { key: "label", label: "Region / market", align: "l", sort: (r) => r.label, render: (r) => r.label, search: (r) => r.label },
  { key: "names", label: "Names", sort: (r) => r.names, render: (r) => r.names },
  { key: "up", label: "Raised", sort: (r) => r.up, render: (r) => <span className="pos">{pct(r.up, 0, false)}</span> },
  { key: "down", label: "Cut", sort: (r) => r.down, render: (r) => <span className="neg">{pct(r.down, 0, false)}</span> },
  { key: "net", label: "Net", sort: (r) => r.net, help: "revision_breadth", render: (r) => <Graded g={r.gauge}>{pct(r.net, 0)}</Graded> },
  { key: "median", label: "Median change", sort: (r) => r.median, render: (r) => pct(r.median, 1) },
];

function RevisionsCard({ r }: { r: Rev }) {
  const ready = r.windows.filter((w) => w.rows.length > 0);
  return (
    <>
      {ready.length === 0 ? (
        <p className="note muted">Building history: {r.weeks_stored} weekly snapshot{r.weeks_stored === 1 ? "" : "s"} of the
          consensus estimates so far{r.asof && <> (latest {date(r.asof)})</>}. The first reading needs a snapshot from 4 weeks
          earlier, the second 12 weeks. <code>radar update</code> takes one a week.</p>
      ) : ready.map((w) => (
        <div className="card" key={w.weeks}>
          <h2>Over {w.weeks} weeks <span className="meta">vs the snapshot of {date(w.base)}</span></h2>
          <DataTable id={`rev${w.weeks}`} csvName={`revisions-${w.weeks}w`} rows={w.rows} cols={revCols} rowKey={(x) => `${x.scope}:${x.group}`} />
        </div>
      ))}
      <p className="note muted">The share of names whose consensus EPS estimate for next year was <Term k="revision_breadth">raised
        minus cut</Term> (by more than 1%), per radar region and Discover market. Yahoo&apos;s consensus, so unofficial; outside
        the S&amp;P 500 it is the radar&apos;s only revisions reading.</p>
    </>
  );
}

function RatesCard({ r }: { r: RatesT }) {
  const keys = Object.keys(r.latest);
  if (!keys.length) return <p className="note muted">No rates data yet.</p>;
  return (
    <div className="grid charts">
      <div className="card">
        <table className="t">
          <thead><tr><th className="l">10-year yield</th><th>Latest</th><th>As of</th></tr></thead>
          <tbody>{keys.map((k) => <tr key={k}><td className="l">{k}</td><td>{num(r.latest[k]!.value, 2)}%</td><td>{date(r.latest[k]!.asof)}</td></tr>)}</tbody>
        </table>
        <p className="note muted">The euro area&apos;s AAA curve comes from the ECB, the US series from FRED. A real yield is
          the yield after expected inflation (TIPS); the breakeven is the inflation the bond market prices in.</p>
      </div>
      {r.chart && <LineChart chart={r.chart} />}
    </div>
  );
}

function SentimentCard({ s }: { s: Sent }) {
  const a = s.aaii, p = s.putcall;
  if (!a && !p) return <p className="note muted">No sentiment data yet.</p>;
  const chart = a && a.history.length > 1 ? {
    title: "AAII bull − bear spread (% points, weekly)", decimals: 0, hlines: [0],
    series: [{ name: "Bull − bear", dates: a.history.map((h) => h.date), values: a.history.map((h) => h.spread * 100) }],
  } : null;
  return (
    <>
      <div className="card">
        <div className="hero">
          {a && <div><div className="sub"><Term k="aaii">AAII survey</Term>, {date(a.asof)}</div>
            <div className="big">{pct(a.spread, 0)}<span className="unit"> bull − bear</span></div>
            <div className="sub"><GaugeBadge g={a.gauge} name="AAII spread percentile" /> {ordinal(a.pct)} percentile since 1987 ·
              bullish {pct(a.bullish, 0, false)} · neutral {pct(a.neutral, 0, false)} · bearish {pct(a.bearish, 0, false)} · 8-week avg {pct(a.spread_8w, 0)}</div></div>}
          {p && <div><div className="sub"><Term k="putcall">Equity put/call</Term> (CBOE), {date(p.asof)}</div>
            <div className="big">{num(p.equity_10d, 2)}<span className="unit"> 10-day avg</span></div>
            <div className="sub">{p.gauge ? <><GaugeBadge g={p.gauge} name="Put/call percentile" /> {ordinal(p.pct)} percentile of 3 years</>
              : <>{p.days} days stored; a percentile needs 60</>} · today: equity {num(p.equity, 2)}, total {num(p.total, 2)}, index {num(p.index, 2)}</div></div>}
        </div>
        <p className="note muted">Both are contrarian and US-centred: extreme fear has tended to come before better returns, and
          complacency before weaker ones, but neither times a turn. Shown for context; they don&apos;t vote in the regime.</p>
      </div>
      {chart && <div className="grid charts"><LineChart chart={chart} /></div>}
    </>
  );
}

export function Positioning() {
  const q = useQuery({ queryKey: ["positioning"], queryFn: api.positioning, retry: false, staleTime: 5 * 60_000 });
  return (
    <Loaded q={q} title="Positioning & cycle">
      {(d) => {
        const f = d.factset;
        return (
          <>
            <PageHead title="Positioning & cycle" asof={d.asof} generated={d.generated} ageDays={d.age_days} stale={d.stale}>
              Data that doesn&apos;t come from prices, so it can lead or confirm what rotation and momentum show. Sources: FactSet
              Earnings Insight (weekly), Yahoo consensus estimates (weekly snapshots), Shiller CAPE and Damodaran&apos;s equity
              risk premium (monthly), OECD Composite Leading Indicators (monthly, about 2 months&apos; lag), ECB and FRED rates,
              the CFTC Commitments of Traders (weekly; Tuesday positions published on Friday), and the AAII survey and CBOE
              put/call ratios.
            </PageHead>

            <h2>Earnings revisions (S&amp;P 500, FactSet)</h2>
            {f ? (
              <div className="card">
                <div className="hero">
                  <div><div className="sub">{f.quarter ?? "Current quarter"} growth estimate</div><div className="big">{num(f.growth_now, 1)}%</div>
                    <div className="sub">{num(f.growth_start, 1)}% at quarter start</div></div>
                  <div><div className="sub">Forward P/E</div><div className="big">{num(f.fwd_pe, 1)}</div>
                    <div className="sub">5y avg {num(f.fwd_pe_5y, 1)} · 10y avg {num(f.fwd_pe_10y, 1)}</div></div>
                  <div><div className="sub">EPS guidance</div>
                    <div className="big"><span className="pos">+{num(f.guidance_pos, 0)}</span> / <span className="neg">−{num(f.guidance_neg, 0)}</span></div>
                    <div className="sub">positive / negative</div></div>
                  <div><div className="sub">Next calendar year growth</div><div className="big">{num(f.cy_next_growth, 1)}%</div></div>
                </div>
                <p className="note">
                  Sectors with upward revisions: <b>{f.rev_up_sectors || "–"}</b>. Downward revisions: <b>{f.rev_down_sectors || "–"}</b>.{" "}
                  <span className="muted">Report {date(f.report_date)}. The full key pages are saved in data/factset_latest.txt.</span>
                </p>
                {f.history.length > 1 && (
                  <table className="t">
                    <thead><tr><th>Report</th><th>Quarter</th><th>Growth estimate</th><th>Forward P/E</th></tr></thead>
                    <tbody>{[...f.history].reverse().map((h) => (
                      <tr key={h.report_date}><td>{date(h.report_date)}</td><td>{h.quarter ?? "–"}</td><td>{num(h.growth_now, 1)}%</td><td>{num(h.fwd_pe, 1)}</td></tr>
                    ))}</tbody>
                  </table>
                )}
              </div>
            ) : <p className="note muted">No FactSet data yet. Run <code>radar update</code>.</p>}

            <h2>Earnings revisions by region (Yahoo consensus)</h2>
            {d.revisions ? <RevisionsCard r={d.revisions} /> : <p className="note muted">No valuation snapshot yet.</p>}

            <h2>Valuation</h2>
            {d.valuation ? <ValuationCard v={d.valuation} /> : <p className="note muted">No valuation data yet.</p>}

            <h2>Leading indicators (OECD CLI)</h2>
            {d.cli.length > 0 ? (
              <>
                <div className="card scroll">
                  <table className="t dt">
                    <thead><tr><th className="l">Area</th><th><Term k="cli">CLI</Term></th><th><Term k="cli_chg">3m change</Term></th><th className="l"><Term k="cli_phase">Phase</Term></th><th>As of</th></tr></thead>
                    <tbody>{d.cli.map((r) => (
                      <tr key={r.area}>
                        <td className="l">{r.label}</td><td>{num(r.cli, 2)}</td>
                        <td><Graded g={r.gauge}>{signed(r.chg_3m, 2)}</Graded></td>
                        <td className="l"><Badge kind={PHASE_KIND[r.phase] ?? ""}>{r.phase}</Badge></td><td>{r.asof.slice(0, 7)}</td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
                <p className="note muted">100 = long-term trend. Expansion: above 100 and rising. Slowdown: above 100 and falling.
                  Contraction: below 100 and falling. Recovery: below 100 and rising.</p>
              </>
            ) : <p className="note muted">No OECD data yet.</p>}

            <h2>Rates: US and euro area</h2>
            {d.rates ? <RatesCard r={d.rates} /> : <p className="note muted">No rates data yet.</p>}

            <h2>Futures positioning (CFTC)</h2>
            {d.cot.length > 0 ? (
              <>
                <div className="card"><DataTable id="cot" csvName="cftc" rows={d.cot} cols={cotCols} rowKey={(r) => `${r.market}:${r.group}`} /></div>
                <p className="note muted">Net position (long − short) as a % of open interest, ranked against the last 3 years. Asset
                  managers are slow, trend-following money. Leveraged funds (hedge funds) and managed money (CTAs) are fast money;
                  their extremes tend to be contrarian. A &ldquo;3y high&rdquo; or &ldquo;3y low&rdquo; flag means the reading is in the top
                  or bottom 10% of its own 3-year range (a 3y low can still be net long). That isn&apos;t a timing signal on its own,
                  but it tells you which way a reversal would hurt most.</p>
              </>
            ) : <p className="note muted">No CFTC data yet.</p>}

            <h2>Sentiment</h2>
            {d.sentiment ? <SentimentCard s={d.sentiment} /> : <p className="note muted">No sentiment data yet.</p>}
          </>
        );
      }}
    </Loaded>
  );
}

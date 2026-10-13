import { useQuery } from "@tanstack/react-query";
import { api, type PositioningView } from "../api/client";
import { Loaded, PageHead } from "../components/cells";
import { DataTable, type Col } from "../components/DataTable";
import { Graded } from "../components/Gauge";
import { Term } from "../components/Term";
import { Badge } from "../components/ui";
import { date, num, tone } from "../lib/format";

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
              Earnings Insight (weekly), OECD Composite Leading Indicators (monthly, about 2 months&apos; lag) and the CFTC
              Commitments of Traders (weekly; Tuesday positions published on Friday).
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
          </>
        );
      }}
    </Loaded>
  );
}

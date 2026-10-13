import { useQuery } from "@tanstack/react-query";
import { api, type MomentumRow } from "../api/client";
import { Check, Loaded, PageHead, Pct } from "../components/cells";
import { DataTable, type Col } from "../components/DataTable";
import { TickerLink, TickerList } from "../components/TickerLink";
import { date, num } from "../lib/format";

const cols: Col<MomentumRow>[] = [
  { key: "name", label: "Company", align: "l", sort: (r) => r.name ?? r.ticker,
    render: (r) => <><TickerLink symbol={r.ticker} name={r.name} nameFirst />{r.new && <span className="new">NEW</span>}</> },
  { key: "industry", label: "Industry", align: "l", sort: (r) => r.industry,
    render: (r) => <span className="muted" title={r.sector ?? ""}>{r.industry || "–"}</span> },
  { key: "score", label: "Score", sort: (r) => r.score, render: (r) => num(r.score, 0) },
  { key: "r1m", label: "1m", sort: (r) => r.r1m, render: (r) => <Pct v={r.r1m} /> },
  { key: "r3m", label: "3m", sort: (r) => r.r3m, render: (r) => <Pct v={r.r3m} /> },
  { key: "r6m", label: "6m", sort: (r) => r.r6m, render: (r) => <Pct v={r.r6m} /> },
  { key: "r12_1", label: "12-1m", sort: (r) => r.r12_1, render: (r) => <Pct v={r.r12_1} /> },
  { key: "from_high", label: "From 52w high", sort: (r) => r.from_high, render: (r) => <Pct v={r.from_high} /> },
  { key: "vol", label: "Vol 20d/120d", sort: (r) => r.vol_surge, render: (r) => r.vol_surge == null ? "–" : `${num(r.vol_surge, 2)}×` },
  { key: "trend", label: "Trend", sort: (r) => r.trend_ok, render: (r) => <Check v={r.trend_ok} /> },
];

export function Momentum() {
  const q = useQuery({ queryKey: ["momentum"], queryFn: api.momentum, retry: false, staleTime: 5 * 60_000 });
  return (
    <Loaded q={q} title="Momentum leaders">
      {(d) => (
        <>
          <PageHead title="Momentum leaders" asof={d.asof} generated={d.generated}>
            The score (0–100) is the average percentile, within each region, of 12-1-month, 6-month and 3-month returns.
            &ldquo;Trend&rdquo; means price above the 200-day average and the 50-day above the 200-day. <span className="new">NEW</span>{" "}
            marks entries that weren&apos;t in the top {d.top_n} at the snapshot from {d.prev ? date(d.prev) : "– (no earlier snapshot yet)"}.
            Momentum is a starting point for research, not a buy list. Check the story behind each move.
          </PageHead>
          <nav className="jump">{d.regions.map((r) => <a key={r.key} href={`#${r.key}`}>{r.label}</a>)}</nav>
          {d.regions.map((r) => (
            <section key={r.key} id={r.key} className="group">
              <h2>{r.label}</h2>
              {r.clusters.length > 0 && (
                <div className="note">
                  <b>Clusters in the top {d.top_n}:</b>
                  <ul className="clusters">
                    {r.clusters.map((c) => (
                      <li key={`${c.level}:${c.name}`}>
                        {c.name} <span className="muted">({c.level})</span> {c.count} names vs ~{c.expected} expected
                        {c.new > 0 && <>, <span className="new">{c.new} NEW</span></>}: <TickerList symbols={c.tickers} />
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {r.dropped.length > 0 && <p className="note muted">Dropped out of top {d.top_n}: <TickerList symbols={r.dropped} /></p>}
              <div className="card"><DataTable rows={r.rows} cols={cols} rowKey={(x) => x.ticker} /></div>
            </section>
          ))}
        </>
      )}
    </Loaded>
  );
}

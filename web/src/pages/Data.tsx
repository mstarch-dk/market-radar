import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, type CoverageView } from "../api/client";
import { Loaded, PageHead, Signal } from "../components/cells";
import { DataHome } from "../components/DataHome";
import { DataTable, type Col } from "../components/DataTable";
import { TickerList } from "../components/TickerLink";
import { UpdatePanel } from "../components/UpdatePanel";
import { date } from "../lib/format";

type Source = CoverageView["sources"][number];

const cols: Col<Source>[] = [
  { key: "name", label: "Source", align: "l", sort: (s) => s.name, search: (s) => `${s.name} ${s.provider} ${s.feeds}`,
    render: (s) => <div className="wrap"><b>{s.name}</b><br /><span className="muted small">{s.provider} · {s.official ? "official" : "unofficial"} · {s.cadence}</span></div> },
  { key: "feeds", label: "Feeds", align: "l", render: (s) => <div className="wrap">{s.feeds}</div> },
  { key: "coverage", label: "Coverage", align: "l",
    render: (s) => <div className="wrap">{s.coverage}{s.detail && <><br /><span className="muted small">{s.detail}</span></>}</div> },
  { key: "asof", label: "As of", sort: (s) => s.asof, render: (s) => date(s.asof) },
  { key: "age", label: "Age (days)", sort: (s) => s.age_days, help: "max_age",
    render: (s) => <>{s.age_days ?? "–"}{s.max_age != null && <span className="muted"> / {s.max_age}</span>}</> },
  { key: "status", label: "Status", align: "l", sort: (s) => s.status, render: (s) => <Signal s={s.status} />, filter: { kind: "enum" } },
  { key: "update", label: "Last update", align: "l", sort: (s) => s.last_success,
    render: (s) => <div className="wrap">{s.error
      ? <><span className="neg">failed {s.last_attempt?.slice(0, 10)}: {s.error}</span>{s.last_success && <><br /><span className="muted">last success {s.last_success.slice(0, 10)}</span></>}</>
      : s.last_success ? s.last_success.slice(0, 16).replace("T", " ") : <span className="muted">not logged yet</span>}</div> },
];

export function Data() {
  const q = useQuery({ queryKey: ["coverage"], queryFn: api.coverage, retry: false, staleTime: 5 * 60_000 });
  return (
    <>
      <Loaded q={q} title="Data & coverage">
        {(d) => {
          const priceLimit = d.sources.find((s) => s.key === "prices")?.max_age;
          const analystLimit = d.sources.find((s) => s.key === "analyst")?.max_age;
          return (
            <>
              <PageHead title="Data & coverage" asof={d.asof} generated={d.generated} ageDays={d.age_days} stale={d.stale}>
                Every reading in the radar comes from the sources below, and only from them. A &ldquo;Risk-on&rdquo; label means the
                inputs listed here lean risk-on; it says nothing about what isn&apos;t measured (see the blind spots further down).
                A source older than its limit is marked <Signal s="stale" /> and stops counting in the regime vote; an input with no
                data shows as <Signal s="n/a" />. Ages are counted from the data date ({date(d.asof)}); limits are in
                config/settings.yaml (<code>coverage:</code>).
              </PageHead>
              <UpdatePanel />
              <DataHome />
              <h2>Sources</h2>
              <div className="card"><DataTable id="src" csvName="sources" rows={d.sources} cols={cols} rowKey={(s) => s.key} /></div>
              <h2>How the readings are built</h2>
              <p className="note">The full explanation, in Danish, is in the <Link to="/guide/laerebog/afstemningsmodellen">textbook</Link>.</p>
              <ul className="blind">
                <li><b>Regime</b>: a vote of {d.regime.total} indicators (trend, breadth, volatility, credit, rates, dollar, commodities,
                  OECD cycle, FactSet revisions). Only risk-on and risk-off rows count: net = (on − off) / (on + off), above +0.33 is
                  Risk-on, below −0.33 Risk-off. Today {d.regime.current} have current data.</li>
                <li><b>Rotation</b>: relative-rotation graph of weekly relative strength vs ACWI (and vs a home benchmark for groups that
                  have one), from prices only.</li>
                <li><b>Momentum</b>: average percentile of the 12-month (skipping the last month), 6-month and 3-month returns within
                  each region&apos;s stock list, from prices only.</li>
                <li><b>Levels</b>: a trailing ATR stop on dividend-adjusted prices plus Yahoo analyst targets
                  {analystLimit != null && <>; consensus older than {analystLimit} days is not used</>}.</li>
                <li><b>Holdings returns</b>: total return in DKK (dividends gross, reinvested) vs a shadow ACWI position with the same cash flows.</li>
              </ul>
              <h2>Reading the colours</h2>
              <p className="note">Graded readings (RSI, distance to a stop, VIX, breadth, …) are coloured by how close they are to their
                thresholds, in nine steps. The word is always shown, so the colour is never the only cue. Thresholds live in
                config/settings.yaml (<code>gauges:</code>, and <code>regime:</code> for the regime rows).</p>
              <div className="legend-row">
                {[[-4, "warning"], [-3, ""], [-2, ""], [-1, ""], [0, "neutral"], [1, ""], [2, ""], [3, ""], [4, "favourable"]].map(([l, w]) => (
                  <span key={l} className={`gchip lv${Number(l) > 0 ? "+" : ""}${l}`}>{w || " "}</span>
                ))}
              </div>
              <p className="note muted">One-way risk measures (VIX, volatility, beta, crowding) only use the grey-to-red half.</p>
              <h2>What the radar doesn&apos;t see</h2>
              <ul className="blind">{d.blind_spots.map((b) => <li key={b}>{b}</li>)}</ul>
              <h2>Missing tickers ({d.missing_tickers.length})</h2>
              <p className="note">{d.missing_tickers.length > 0
                ? <><TickerList symbols={d.missing_tickers} /><br /><span className="muted">Configured but no prices at all. The ticker may be
                  wrong or not on Yahoo, so check it in universe.yaml.</span></>
                : "None."}</p>
              <h2>Stale tickers ({d.stale_tickers.length})</h2>
              <p className="note">{d.stale_tickers.length > 0
                ? <><TickerList symbols={d.stale_tickers} /><br /><span className="muted">No new price for more than {priceLimit ?? "?"} days.
                  The ticker may be delisted or suspended.</span></>
                : "None."}</p>
              {d.behind_tickers.length > 0 && <>
                <h2>Without the last session ({d.behind_tickers.length})</h2>
                <p className="note"><TickerList symbols={d.behind_tickers} /><br /><span className="muted">No bar
                  for {d.asof}, the benchmark&apos;s last session: an exchange holiday, or Yahoo didn&apos;t have it at
                  the last update. The next update asks again.</span></p>
              </>}
            </>
          );
        }}
      </Loaded>
      {q.isError && <DataHome />}{/* before the first download too: backups, export */}
    </>
  );
}

import { useQuery } from "@tanstack/react-query";
import { api, type MyRow } from "../api/client";
import { Check, Loaded, PageHead, Pct } from "../components/cells";
import { DataTable, type Col } from "../components/DataTable";
import { GaugeDots, Graded, worst } from "../components/Gauge";
import { TickerLink } from "../components/TickerLink";
import { Badge } from "../components/ui";
import { WatchButton } from "../components/WatchButton";
import { ImportPortfolio } from "../components/ImportPortfolio";
import { date, num, pct } from "../lib/format";

const name: Col<MyRow> = { key: "name", label: "Name", align: "l", sort: (r) => r.name ?? r.symbol,
  search: (r) => `${r.name ?? ""} ${r.symbol}`, csv: (r) => r.symbol, csvHeader: "Ticker",
  render: (r) => <TickerLink symbol={r.symbol} name={r.name} nameFirst marker={false} /> };
const common: Col<MyRow>[] = [
  { key: "score", label: "Score", sort: (r) => r.score, render: (r) => <Graded g={r.gauges?.score}>{num(r.score, 0)}</Graded>, help: "score_me",
    filter: { kind: "range", unit: "num" } },
  { key: "r1m", label: "1m", sort: (r) => r.r1m, render: (r) => <Pct v={r.r1m} />, help: "r1m", heat: true },
  { key: "r3m", label: "3m", sort: (r) => r.r3m, render: (r) => <Pct v={r.r3m} />, help: "r3m", heat: true },
  { key: "rel_r3m", label: "Rel 3m", sort: (r) => r.rel_r3m, render: (r) => <Pct v={r.rel_r3m} />, help: "rel_r3m", heat: true },
  { key: "r6m", label: "6m", sort: (r) => r.r6m, render: (r) => <Pct v={r.r6m} />, help: "r6m", heat: true },
  { key: "from_high", label: "From high", sort: (r) => r.from_high, render: (r) => <Graded g={r.gauges?.from_high}>{pct(r.from_high)}</Graded>, help: "from_high" },
  { key: "signals", label: "Signals", help: "signals", sort: (r) => worst(r.gauges), csv: (r) => r.watchouts.map((w) => w.text),
    filter: { kind: "bool", value: (r) => r.watchouts.length > 0 }, name: "Watch-outs",
    render: (r) => <GaugeDots gauges={r.gauges ?? {}} names={SIGNALS} /> },
  { key: "trend", label: "Trend", sort: (r) => r.trend_ok, render: (r) => <Check v={r.trend_ok} />, help: "trend_ok",
    filter: { kind: "bool" }, hidden: true },
];
const SIGNALS = { rsi14: "RSI 14", score: "Momentum score", from_high: "52w high", stop_dist: "Stop", tp_dist: "Target",
  excess_vs_acwi: "vs ACWI (DKK)" };

const flags: Col<MyRow> = { key: "flags", label: "Flags", align: "l", render: (r) => <Flags r={r} />, help: "flags",
  filter: { kind: "enum", value: (r) => [...r.flags, ...(r.levels?.flags ?? [])] }, csv: (r) => r.flags };

function Flags({ r }: { r: MyRow }) {
  const lv = r.levels;
  return (
    <div className="flags">
      {r.flags.map((f) => <Badge key={f}>{f}</Badge>)}
      {lv?.flags.map((f) => <Badge key={f} kind="neg">{f}</Badge>)}
      {lv && (
        <details className="why">
          <summary>why (k {num(lv.k, 2)})</summary>
          <ul className="reasons">
            {lv.reasons.map((x, i) => (
              <li key={i}>
                <span className={x.effect < 0 ? "neg" : x.effect > 0 ? "pos" : "muted"}>{x.effect < 0 ? "▼" : x.effect > 0 ? "▲" : "•"}</span>
                <span><b>{x.signal}</b>: {x.detail}</span>
              </li>
            ))}
            {lv.analyst?.target_mean != null && (
              <li><span className="muted">•</span><span className="muted">Analysts ({date(lv.analyst.fetched)}): {lv.analyst.rec_key ?? "?"},{" "}
                {num(lv.analyst.n_analysts, 0)} opinions, targets {num(lv.analyst.target_low)}–{num(lv.analyst.target_high)},
                mean {num(lv.analyst.target_mean)} ({pct(lv.analyst.upside)})</span></li>
            )}
          </ul>
        </details>
      )}
    </div>
  );
}

const holdingCols: Col<MyRow>[] = [
  name, ...common,
  { key: "since_buy", label: "Since buy (DKK)", sort: (r) => r.since_buy, help: "since_buy",
    render: (r) => <Graded g={r.gauges?.excess_vs_acwi}>{pct(r.since_buy)}</Graded> },
  { key: "bench", label: "ACWI (DKK)", sort: (r) => r.bench_since_buy, help: "bench_since_buy",
    render: (r) => <span className="muted">{pct(r.bench_since_buy)}</span> },
  { key: "stop", label: "Stop", help: "stop", csv: (r) => r.levels?.stop, sort: (r) => r.levels?.stop_pct,
    render: (r) => r.levels?.stop != null ? <>{num(r.levels.stop)} <Graded g={r.gauges?.stop_dist}>{pct(r.levels.stop_pct)}</Graded></> : <span className="muted">–</span> },
  { key: "target", label: "Target", help: "take_profit", csv: (r) => r.levels?.take_profit, sort: (r) => r.levels?.tp_pct,
    render: (r) => r.levels?.take_profit != null ? <>{num(r.levels.take_profit)} <Graded g={r.gauges?.tp_dist}>{pct(r.levels.tp_pct)}</Graded></> : <span className="muted">–</span> },
  flags,
];
const watchCols: Col<MyRow>[] = [
  name, ...common, flags,
  { key: "edit", label: "", name: "Watch", render: (r) => <WatchButton symbol={r.symbol} status={r.status} compact />, csv: false },
];
const soldCols: Col<MyRow>[] = [
  name, ...common,
  { key: "sold", label: "Sold", sort: (r) => r.last_sell_date, render: (r) => date(r.last_sell_date) },
  { key: "since_sell", label: "Since sell", sort: (r) => r.since_sell, render: (r) => <Pct v={r.since_sell} />, help: "since_sell", heat: true },
  flags,
  { key: "edit", label: "", name: "Watch", render: (r) => <WatchButton symbol={r.symbol} status={r.status} compact />, csv: false },
];

const TABLE_ID: Record<string, string> = { Holdings: "held", Watchlist: "watch", "Sold positions": "sold" };

export function Me() {
  const q = useQuery({ queryKey: ["me"], queryFn: api.me, retry: false, staleTime: 60_000 });
  return (
    <Loaded q={q} title="My holdings & watchlist">
      {(d) => {
        const by = (s: string) => d.rows.filter((r) => r.status === s);
        const sections = [
          ["Holdings", by("holding"), holdingCols],
          ["Watchlist", by("watch"), watchCols],
          ["Sold positions", by("sold"), soldCols],
        ] as const;
        return (
          <>
            <PageHead title="My holdings & watchlist" asof={d.asof} generated={d.generated}>
              Computed live from the current prices. The score is each name&apos;s momentum percentile compared with the whole
              stock universe. &ldquo;Since buy&rdquo; is the open position&apos;s total return <b>in DKK</b>, including currency moves
              and dividends (gross, treated as reinvested), using the average-cost method. &ldquo;ACWI (DKK)&rdquo; is a <b>shadow
              position</b>: the same DKK amounts invested in ACWI on the same dates, with sells removing the same fraction.
              &ldquo;Since sell&rdquo; shows how the stock has moved after your last sale. Add names to the watchlist from any ticker page.
            </PageHead>
            {d.rows.length === 0 && <p className="note">No holdings yet. Import them below, or star tickers to build a watchlist.</p>}
            {sections.map(([title, rows, cols]) => rows.length > 0 && (
              <section key={title} className="group">
                <h2>{title} ({rows.length})</h2>
                <div className="card"><DataTable id={TABLE_ID[title] ?? title} csvName={`me-${TABLE_ID[title]}`} rows={[...rows]} cols={[...cols]} rowKey={(r) => r.symbol} /></div>
                {title === "Holdings" && (
                  <p className="note muted">Stop and target are a mechanical rule, not advice. Stop = highest close since entry − k × ATR(14),
                    where k starts at 3 and each signal (▲ more room, ▼ tighter) moves it: momentum score, 50/200-day trend, extension
                    above the 50-day, the radar&apos;s macro regime ({d.regime ?? "unknown"}) and analyst consensus. Target = the lower of
                    2 × the stop width above the price and the analysts&apos; mean target (needs at least 5 analysts). Broad index funds
                    get no levels. Thresholds live in config/settings.yaml (<code>stops:</code>).</p>
                )}
              </section>
            ))}
            <details className="import-details" open={d.rows.length === 0}>
              <summary>Import or re-import your portfolio from Yahoo Finance</summary>
              <ImportPortfolio />
            </details>
          </>
        );
      }}
    </Loaded>
  );
}

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, api, type Profile } from "../api/client";
import { PriceChart, type Level } from "../components/PriceChart";
import {
  AnalystCard, EtfCard, FundamentalsCard, LevelsCard, MomentumCard, PeersCard, RecentCard, Returns, RiskCard, TechnicalsCard, ViewsCard,
} from "../components/sections";
import { Badge, Card } from "../components/ui";
import { WatchButton } from "../components/WatchButton";
import { date, pct, price, tone } from "../lib/format";
import { recent } from "../lib/recent";

const STATUS: Record<string, [string, string]> = { holding: ["You hold this", "pos"], watch: ["On your watchlist", "accent"], sold: ["Sold earlier", ""] };

/** Research memos, comparisons and journal entries about this ticker (the Notebook), when there are any. */
function InNotebook({ symbol }: { symbol: string }) {
  const { data } = useQuery({ queryKey: ["notebook"], queryFn: api.notebook });
  if (!data) return null;
  const sym = symbol.toUpperCase();
  const docs = [
    ...data.research.filter((d) => d.ticker?.toUpperCase() === sym),
    ...data.compare.filter((d) => `-${d.name.slice(11).toUpperCase()}-`.includes(`-${sym}-`)),   // YYYY-MM-DD_A-B-C
    ...data.journal.filter((d) => d.ticker?.toUpperCase() === sym),
  ];
  if (!docs.length) return null;
  return (
    <div className="small nb-ticker">
      In your notebook:{" "}
      {docs.map((d, i) => (
        <span key={`${d.kind}/${d.name}`}>{i > 0 && " · "}
          <Link to={`/notebook/${d.kind}/${encodeURIComponent(d.name)}`}>{d.kind === "journal" ? `${d.meta?.action ?? "decision"} ${d.date}` : d.title}</Link>
          {d.review_due && <> <Badge kind="warn">review due</Badge></>}
        </span>
      ))}
    </div>
  );
}

function Header({ p, onRefresh, refreshing }: { p: Profile; onRefresh: () => void; refreshing: boolean }) {
  const id = p.identity;
  const st = id.my_status ? STATUS[id.my_status] : undefined;
  const regime = p.context.regime.label;
  return (
    <div className="head">
      <div>
        <h1>{id.name ?? id.symbol}</h1>
        <div className="sub">
          <b>{id.symbol}</b> · {[id.exchange, id.quote_type, id.sector, id.industry].filter(Boolean).join(" · ")}
        </div>
        <div className="badges">
          {st && <Badge kind={st[1]}>{st[0]}</Badge>}
          {id.tracked ? <Badge>tracked by the radar</Badge> : <Badge kind="warn" title="Prices are fetched on lookup, not in the daily update">not tracked</Badge>}
          {id.stock_group && <Badge>{id.stock_group} stock group</Badge>}
          {id.etf_group && <Badge>ETF group: {id.etf_group}</Badge>}
          {id.positive_list && id.positive_list !== "?" && <Badge kind={id.positive_list === "yes" ? "pos" : "neg"}>positive list: {id.positive_list}</Badge>}
          {regime && <Badge kind={regime === "Risk-on" ? "pos" : regime === "Risk-off" ? "neg" : "warn"}>regime {regime}</Badge>}
        </div>
        <InNotebook symbol={id.symbol} />
      </div>
      <div className="quote">
        <div className="last num">{price(p.price.last, p.price.currency)}</div>
        <div className={`num ${tone(p.price.change_1d)}`}>{pct(p.price.change_1d, 2)} on {date(p.price.asof)}</div>
        <div className="actions">
          <WatchButton symbol={id.symbol} status={id.my_status} />
          <button className="btn" onClick={onRefresh} disabled={refreshing} title="Re-fetch fundamentals and estimates from Yahoo now">
            {refreshing ? "Refreshing…" : "Refresh Yahoo data"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function Ticker() {
  const { symbol = "" } = useParams();
  const sym = symbol.toUpperCase();
  const qc = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);
  const prof = useQuery({ queryKey: ["profile", sym], queryFn: () => api.profile(sym), retry: false, staleTime: 10 * 60_000 });
  const ser = useQuery({ queryKey: ["series", sym], queryFn: () => api.series(sym), retry: false, staleTime: 10 * 60_000,
    enabled: prof.isSuccess });

  useEffect(() => {
    if (prof.isSuccess) {
      recent.add(sym);
      document.title = `${sym} · Market Radar`;
    }
  }, [prof.isSuccess, sym]);

  const p = prof.data;
  const levels: Level[] = useMemo(() => p ? [
    { price: p.levels.stop, label: "Stop", kind: "stop" },
    { price: p.levels.take_profit, label: "Take-profit", kind: "target" },
    // the analyst mean is drawn separately only when it isn't already the take-profit
    ...(p.analyst.target_mean != null && p.analyst.target_mean !== p.levels.take_profit
      ? [{ price: p.analyst.target_mean, label: "Analyst mean", kind: "analyst" as const }] : []),
  ] : [], [p]);

  if (prof.isPending) return (
    <div className="skeleton" style={{ height: 600, padding: 20 }} aria-busy="true">
      <span className="muted">Loading {sym}… A ticker the radar doesn&apos;t track is downloaded from Yahoo first, which takes a few seconds.</span>
    </div>
  );
  if (prof.isError) {
    const e = prof.error;
    return <div className="error">{e instanceof ApiError && e.status === 404 ? `No Yahoo data for ${sym}. Check the symbol (e.g. NOVO-B.CO, RHM.DE).` : `Couldn't load ${sym}: ${e.message}`}</div>;
  }
  if (!p) return null;

  const refresh = async () => {
    setRefreshing(true);
    try {
      qc.setQueryData(["profile", sym], await api.profile(sym, true));
    } finally {
      setRefreshing(false);
    }
  };

  const isFund = p.etf !== null && p.etf !== undefined;
  return (
    <>
      <Header p={p} onRefresh={refresh} refreshing={refreshing} />
      {(p.context.watchouts ?? []).length > 0 && (
        <div className="watchouts" role="note">
          <span className="wo-title">Watch-outs:</span>
          {(p.context.watchouts ?? []).map((w) => <span key={w.key} className={`gchip lv${w.level}`}>{w.text}</span>)}
        </div>
      )}
      {p.context.notes.length > 0 && (
        <div className="notes" role="note"><ul>{p.context.notes.map((n) => <li key={n}>{n}</li>)}</ul></div>
      )}
      <div className="grid">
        <Card title="Chart" wide className="chart-card">
          {ser.data ? <PriceChart series={ser.data} levels={levels} currency={p.price.currency} />
            : ser.isError ? <p className="empty">Chart data unavailable.</p>
            : <div className="skeleton chart" />}
        </Card>
        <Returns p={p} />
        <MomentumCard p={p} />
        <TechnicalsCard p={p} />
        <LevelsCard p={p} />
        <RiskCard p={p} />
        {isFund ? <EtfCard p={p} /> : <AnalystCard p={p} />}
        {isFund ? null : <FundamentalsCard p={p} />}
        <PeersCard p={p} />
        <ViewsCard p={p} />
        <RecentCard p={p} />
        {p.identity.summary && (
          <Card title="About" meta={p.identity}>
            <p className="summary">{p.identity.summary}</p>
            {p.identity.website && <a href={p.identity.website} target="_blank" rel="noreferrer">{p.identity.website}</a>}
          </Card>
        )}
      </div>
      <div className="sources">
        Sources: {[p.price, p.momentum, p.analyst, p.fundamentals, ...(p.etf ? [p.etf] : []), p.peers]
          .map((s) => `${s.source} (${s.status}${s.asof ? `, ${date(s.asof)}` : ""})`)
          .filter((v, i, a) => a.indexOf(v) === i).join(" · ")}.
        {Object.keys(p.context.errors).length > 0 && <> Yahoo errors: {Object.entries(p.context.errors).map(([k, v]) => `${k}: ${v}`).join("; ")}.</>}
        {" "}Generated {p.generated.replace("T", " ")}. Analysis, not advice.
      </div>
    </>
  );
}

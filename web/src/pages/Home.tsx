import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { regimeKind } from "../components/cells";
import { Search } from "../components/Search";
import { SoonStrip } from "../components/SoonStrip";
import { tickerPath } from "../components/TickerLink";
import { Badge } from "../components/ui";
import { date } from "../lib/format";
import { NAV } from "../lib/nav";
import { recent } from "../lib/recent";


export function Home() {
  const { data } = useQuery({ queryKey: ["context"], queryFn: api.context });
  const seen = recent.list();
  const groups = [
    ["Holdings", data?.tickers.filter((t) => t.status === "holding") ?? []],
    ["Watchlist", data?.tickers.filter((t) => t.status === "watch") ?? []],
  ] as const;
  const regime = data?.regime;
  return (
    <div className="home">
      <h1>Market Radar</h1>
      <p className="lead">
        Look up any stock or ETF on Yahoo Finance, or open a dashboard below.
        {regime?.label && <> Current regime: <Badge kind={regimeKind(regime.label)}>{regime.label}</Badge>
          {regime.asof && <span className="muted"> (as of {date(regime.asof)})</span>}.</>}
      </p>
      <Search autoFocus />
      <SoonStrip />
      {NAV.map((g) => (
        <div key={g.id}>
          <div className="section-title">{g.label}</div>
          <div className="tiles home-tiles">
            {g.pages.map((p) => (
              <Link key={p.path} to={p.path} className="tile"><b>{p.label}</b><span>{p.blurb}</span></Link>
            ))}
          </div>
        </div>
      ))}
      {seen.length > 0 && (
        <>
          <div className="section-title">Recently viewed</div>
          <div className="chips">{seen.map((s) => <Link key={s} className="chip" to={tickerPath(s)}>{s}</Link>)}</div>
        </>
      )}
      {groups.map(([label, list]) => list.length > 0 && (
        <div key={label}>
          <div className="section-title">{label}</div>
          <div className="chips">
            {list.map((t) => (
              <Link key={t.symbol} className="chip" to={tickerPath(t.symbol)}>
                {t.symbol}{t.name && t.name !== t.symbol && <small>{t.name}</small>}
              </Link>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

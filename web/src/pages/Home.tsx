import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { regimeKind } from "../components/cells";
import { Search } from "../components/Search";
import { tickerPath } from "../components/TickerLink";
import { Badge } from "../components/ui";
import { date } from "../lib/format";
import { recent } from "../lib/recent";

const SECTIONS = [
  ["/regime", "Regime", "Risk-on/off vote, breadth, credit, volatility"],
  ["/rotation", "Sector rotation", "US & European sectors, regions vs ACWI"],
  ["/themes", "Themes & factors", "Theme ETFs with UCITS alternatives, factors"],
  ["/momentum", "Momentum", "Leaders per region, clusters, new entrants"],
  ["/positioning", "Positioning & cycle", "FactSet revisions, OECD CLI, CFTC"],
  ["/me", "My holdings & watchlist", "Returns vs ACWI, stops and targets"],
  ["/data", "Data & coverage", "Sources, freshness, blind spots"],
] as const;

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
      <div className="tiles">
        {SECTIONS.map(([to, title, sub]) => (
          <Link key={to} to={to} className="tile"><b>{title}</b><span>{sub}</span></Link>
        ))}
      </div>
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

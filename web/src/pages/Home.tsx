import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Search } from "../components/Search";
import { recent } from "../lib/recent";

export function Home() {
  const { data } = useQuery({ queryKey: ["context"], queryFn: api.context });
  const seen = recent.list();
  const groups = [
    ["Holdings", data?.tickers.filter((t) => t.status === "holding") ?? []],
    ["Watchlist", data?.tickers.filter((t) => t.status === "watch") ?? []],
  ] as const;
  return (
    <div className="home">
      <h1>Look up a ticker</h1>
      <p className="lead">
        Price development, momentum, technicals, analyst estimates, valuation and peers for any stock or ETF on Yahoo Finance.
        {data?.regime.label && <> Current regime: <b>{data.regime.label}</b>.</>}
      </p>
      <Search autoFocus />
      {seen.length > 0 && (
        <>
          <div className="section-title">Recently viewed</div>
          <div className="chips">{seen.map((s) => <Link key={s} className="chip" to={`/ticker/${encodeURIComponent(s)}`}>{s}</Link>)}</div>
        </>
      )}
      {groups.map(([label, list]) => list.length > 0 && (
        <div key={label}>
          <div className="section-title">{label}</div>
          <div className="chips">
            {list.map((t) => (
              <Link key={t.symbol} className="chip" to={`/ticker/${encodeURIComponent(t.symbol)}`}>
                {t.symbol}{t.name && t.name !== t.symbol && <small>{t.name}</small>}
              </Link>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

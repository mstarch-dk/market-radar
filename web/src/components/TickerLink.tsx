import { Link } from "react-router-dom";

export const tickerPath = (symbol: string) => `/ticker/${encodeURIComponent(symbol)}`;

/** Every ticker in the app links to its profile page. `name` is shown muted after the symbol (or, with
 *  `nameFirst`, the name leads and the symbol follows, as in the dashboard tables). */
export function TickerLink({ symbol, name, nameFirst, className }: {
  symbol: string;
  name?: string | null;
  nameFirst?: boolean;
  className?: string;
}) {
  const showName = name && name !== symbol;
  if (nameFirst && showName) {
    return (
      <Link to={tickerPath(symbol)} className={`tlink ${className ?? ""}`} title={symbol}>
        {name} <span className="sym">{symbol}</span>
      </Link>
    );
  }
  return (
    <>
      <Link to={tickerPath(symbol)} className={`tlink ${className ?? ""}`}>{symbol}</Link>
      {showName && <> <span className="muted small trunc" title={name}>{name}</span></>}
    </>
  );
}

/** A comma-separated list of linked tickers. */
export function TickerList({ symbols }: { symbols: string[] }) {
  return (
    <>
      {symbols.map((s, i) => (
        <span key={s}>{i > 0 && ", "}<TickerLink symbol={s} /></span>
      ))}
    </>
  );
}

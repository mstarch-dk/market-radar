import { Link } from "react-router-dom";
import type { TickerSummary } from "../api/client";
import { date, num, pct, price, tone } from "../lib/format";
import { useTickers } from "../lib/tickers";
import { QUAD_KIND } from "./quadrants";
import { Sparkline } from "./Sparkline";
import { HoverCard } from "./Tip";
import { Badge } from "./ui";
import { WatchButton } from "./WatchButton";

export const tickerPath = (symbol: string) => `/ticker/${encodeURIComponent(symbol)}`;

const STATUS_LABEL: Record<string, [string, string]> = { holding: ["held", "pos"], watch: ["watch", "accent"], sold: ["sold", ""] };

function Card({ symbol, t }: { symbol: string; t?: TickerSummary }) {
  if (!t || t.last == null) {
    return (
      <div className="tcard">
        <div className="tcard-head"><b>{symbol}</b>{t?.my_status && <Badge kind={STATUS_LABEL[t.my_status]?.[1]}>{STATUS_LABEL[t.my_status]?.[0]}</Badge>}</div>
        <p className="muted small">Not tracked by the radar: the profile downloads it from Yahoo on first open.</p>
        <Link to={tickerPath(symbol)} className="small">Open profile →</Link>
      </div>
    );
  }
  return (
    <div className="tcard">
      <div className="tcard-head">
        <div><b>{t.name ?? symbol}</b><div className="muted small">{symbol}{t.group && ` · ${t.group}`}{t.kind && ` · ${t.kind === "etf" ? "ETF" : "stock"}`}</div></div>
        {t.my_status && <Badge kind={STATUS_LABEL[t.my_status]?.[1]}>{t.my_status === "holding" ? "you hold this" : STATUS_LABEL[t.my_status]?.[0]}</Badge>}
      </div>
      <div className="tcard-quote">
        <span className="num big">{price(t.last, t.currency)}</span>
        <span className={`num ${tone(t.change_1d)}`}>{pct(t.change_1d, 2)}</span>
        <span className="muted small">{date(t.asof)}</span>
      </div>
      <Sparkline values={t.spark} width={230} height={40} />
      <div className="tcard-stats">
        <span>1m <b className={tone(t.r1m)}>{pct(t.r1m)}</b></span>
        <span>3m <b className={tone(t.r3m)}>{pct(t.r3m)}</b></span>
        {t.score != null && <span>score <b>{num(t.score, 0)}</b></span>}
        {t.quadrant && <Badge kind={QUAD_KIND[t.quadrant]}>{t.quadrant}</Badge>}
      </div>
      <div className="tcard-foot">
        <WatchButton symbol={symbol} status={t.my_status} compact />
        <Link to={tickerPath(symbol)} className="small">Open profile →</Link>
      </div>
    </div>
  );
}

/** Every ticker in the app links to its profile, previews it on hover (price, returns, score, 6-month sparkline,
 *  your status) and shows a small "held"/"watch" marker. `name` is shown muted after the symbol (or, with
 *  `nameFirst`, the name leads and the symbol follows, as in the dashboard tables). */
export function TickerLink({ symbol, name, nameFirst, className, marker = true }: {
  symbol: string;
  name?: string | null;
  nameFirst?: boolean;
  className?: string;
  marker?: boolean;
}) {
  const all = useTickers();
  const t = all.get(symbol);
  const showName = name && name !== symbol;
  const st = marker && t?.my_status && t.my_status !== "sold" ? STATUS_LABEL[t.my_status] : undefined;
  const link = nameFirst && showName
    ? <Link to={tickerPath(symbol)} className={`tlink ${className ?? ""}`}>{name} <span className="sym">{symbol}</span></Link>
    : <Link to={tickerPath(symbol)} className={`tlink ${className ?? ""}`}>{symbol}</Link>;
  return (
    <>
      <HoverCard content={() => <Card symbol={symbol} t={t} />}>{link}</HoverCard>
      {st && <span className={`own ${st[1]}`} title={st[0]}>{st[0]}</span>}
      {!nameFirst && showName && <> <span className="muted small trunc" title={name}>{name}</span></>}
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

import { Link } from "react-router-dom";
import { byWeek, inDays, LEVEL_KIND, when, type Item } from "../lib/agenda";
import { date, num, pct } from "../lib/format";
import { DataTable, type Col } from "./DataTable";
import { Term } from "./Term";
import { TickerLink } from "./TickerLink";
import { Badge } from "./ui";

const KIND_LABEL: Record<Item["kind"], string> = {
  earnings: "Earnings", ex_dividend: "Ex-dividend", review: "Review", time_stop: "Time stop" };
const STATUS_LABEL: Record<Item["status"], string> = { holding: "held", watch: "watched", own: "yours" };
const SOURCE_LABEL = { yahoo_detail: "Yahoo calendar", yahoo_screener: "Yahoo screener" } as const;

/** The item's subject: the ticker (a link to its profile); for your own dates also a link to where they live. */
export function Subject({ i }: { i: Item }) {
  if (i.status !== "own" && i.symbol) return <TickerLink symbol={i.symbol} name={i.name} />;
  const where = <Link to={i.link}>{i.kind === "review" ? (i.name ?? "journal entry") : "proposal"}</Link>;
  return i.symbol ? <><TickerLink symbol={i.symbol} /> · {where}</> : where;
}

export function LevelBadge({ level }: { level: Item["level"] }) {
  return <Badge kind={LEVEL_KIND[level]}>{level}</Badge>;
}

/** Why the item stands out, as the API words it (the same text on the page, in the CLI and in the brief). */
export function Reasons({ i }: { i: Item }) {
  if (i.reasons.length === 0) return <span className="muted">–</span>;
  return <span className="badges reasons">{i.reasons.map((r) => <span key={r.key} className="badge">{r.text}</span>)}</span>;
}

/** The date and how sure it is: Yahoo's window as a range, the source and the day it was read. */
export function When({ i, detail = false }: { i: Item; detail?: boolean }) {
  const e = i.earnings;
  return (
    <span>
      <b>{when(i)}</b> <span className="muted">{inDays(i.days)}</span>
      {e && detail && (
        <span className="small muted cal-src">
          {" · "}{e.is_range ? <Term k="cal_unconfirmed">expected window</Term> : "expected date"}, {SOURCE_LABEL[e.source]}
          {e.read_on && <>, read {date(e.read_on)}</>}
          {e.moved_from && <>, <span className="warn-text">moved from {date(e.moved_from)}</span></>}
        </span>
      )}
    </span>
  );
}

const cols: Col<Item>[] = [
  { key: "date", label: "Date", align: "l", sort: (i) => i.date, csv: (i) => when(i), render: (i) => <When i={i} /> },
  { key: "name", label: "Name", align: "l", sort: (i) => i.symbol ?? i.name ?? "", csv: (i) => i.symbol ?? i.name ?? "",
    render: (i) => <Subject i={i} /> },
  { key: "kind", label: "What", align: "l", sort: (i) => i.kind, csv: (i) => KIND_LABEL[i.kind],
    render: (i) => <>{KIND_LABEL[i.kind]} <span className="small muted">{STATUS_LABEL[i.status]}</span></> },
  { key: "level", label: "Level", help: "cal_level", align: "l", sort: (i) => ["high", "normal", "info"].indexOf(i.level),
    csv: (i) => i.level, render: (i) => <LevelBadge level={i.level} /> },
  { key: "weight", label: "Weight", sort: (i) => i.weight, render: (i) => i.weight == null ? <span className="muted">–</span> : pct(i.weight, 1, false) },
  { key: "eps", label: "EPS est.", help: "cal_eps", sort: (i) => i.earnings?.eps_avg, render: (i) => i.earnings?.eps_avg == null
    ? <span className="muted">–</span>
    : <span title={`low ${num(i.earnings.eps_low)} · high ${num(i.earnings.eps_high)}`}>{num(i.earnings.eps_avg)}</span> },
  { key: "reasons", label: "Why", align: "l", csv: (i) => i.reasons.map((r) => r.text).join("; "), render: (i) => <Reasons i={i} /> },
];

/** The agenda: one table per ISO week, in date order. */
export function AgendaList({ items, empty }: { items: Item[]; empty: string }) {
  const weeks = byWeek(items);
  if (weeks.length === 0) return <p className="small muted">{empty}</p>;
  return (
    <>
      {weeks.map((w) => (
        <div key={w.key} className="cal-week">
          <h3>Week {w.week} <span className="small muted">from {date(w.monday)}</span></h3>
          <DataTable id={`cal${w.key}`} csvName={`calendar-${w.key}`} rows={w.items} cols={cols} rowKey={(i) => i.id} toolbar={false} />
        </div>
      ))}
    </>
  );
}

/** One item that needs attention, as a card: what, when, how sure, and why. */
export function SoonCard({ i }: { i: Item }) {
  return (
    <div className={`tile cal-card lv-${i.level}`}>
      <span><LevelBadge level={i.level} /> {KIND_LABEL[i.kind]} · {STATUS_LABEL[i.status]}</span>
      <b><Subject i={i} /></b>
      <When i={i} detail />
      <Reasons i={i} />
    </div>
  );
}

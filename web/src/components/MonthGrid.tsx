import { Link } from "react-router-dom";
import { monthGrid, monthsOf, when, type Item } from "../lib/agenda";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function monthName(m: string): string {
  return new Date(`${m}-01T00:00:00Z`).toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });
}

/** The window's months as plain CSS grids (no chart library): a dot per item on each day it falls on, coloured by
 *  level. A range (Yahoo's expected window) runs across its days, drawn lighter, so it never reads as one date.
 *  Weeks wholly before today or after the window are left out. */
export function MonthGrid({ items, today, days }: { items: Item[]; today: string; days: number }) {
  const last = monthsOf(today, days).at(-1)!;
  const end = new Date(Date.parse(`${today}T00:00:00Z`) + days * 86_400_000).toISOString().slice(0, 10);
  return (
    <div className="cal-months">
      {monthsOf(today, days).map((m) => (
        <section key={m} className="cal-month" aria-label={monthName(m)}>
          <h3>{monthName(m)}</h3>
          <div className="cal-grid" role="grid">
            {WEEKDAYS.map((d) => <div key={d} className="cal-wd" role="columnheader">{d}</div>)}
            {monthGrid(items, m, today).filter((w) => w.at(-1)!.date >= today && w[0]!.date <= end).flat().map((c, idx) => (
              <div key={c.date} role="gridcell"
                className={`cal-day ${c.inMonth ? "" : "out"} ${c.today ? "today" : ""} ${c.date < today || c.date > end ? "past" : ""}`}>
                <span className="cal-n">{+c.date.slice(8, 10)}</span>
                {c.inMonth && c.entries.map(({ item: i, part }) => (
                  <Link key={i.id} to={i.link}
                    className={`cal-dot lv-${i.level} ${part === "day" ? "" : `range ${part}`}`}
                    title={`${i.symbol ?? i.name ?? ""} · ${when(i)} · ${i.level}${i.reasons.length ? ` · ${i.reasons.map((r) => r.text).join("; ")}` : ""}`}>
                    {part === "day" || part === "start" || idx % 7 === 0 || c.date.endsWith("-01") ? (i.symbol ?? i.kind.replace("_", " ")) : " "}
                  </Link>
                ))}
              </div>
            ))}
          </div>
          {m === last && <p className="small muted">Window ends {when({ date: end, date_end: null })}.</p>}
        </section>
      ))}
    </div>
  );
}

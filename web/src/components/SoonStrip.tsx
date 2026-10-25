import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { inDays, soonItems, when } from "../lib/agenda";
import { DEFAULT_SEL, formatSel } from "../lib/portfolioSel";
import { Reasons, Subject } from "./AgendaList";

/** Home's "Soon" strip: the calendar's high items of the next days for your real portfolios, the same `soon` list
 *  and the same request as the Calendar page's default view. Hidden when there is none, or no calendar yet. */
export function SoonStrip() {
  const q = useQuery({ queryKey: ["calendar", formatSel(DEFAULT_SEL)], queryFn: () => api.calendar(DEFAULT_SEL),
    retry: false, staleTime: 60_000 });
  const items = q.data ? soonItems(q.data) : [];
  if (items.length === 0) return null;
  return (
    <div className="soon-strip">
      <div className="section-title">Soon <Link className="small" to="/calendar">calendar →</Link></div>
      <div className="tiles home-tiles">
        {items.map((i) => (
          <div key={i.id} className="tile cal-card lv-high">
            <b><Subject i={i} /></b>
            <span>{i.kind === "earnings" ? "Earnings" : i.kind.replace("_", " ")} {when(i)} · {inDays(i.days)}</span>
            <Reasons i={i} />
          </div>
        ))}
      </div>
    </div>
  );
}

import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api, type AgendaView } from "../api/client";
import { AgendaList, SoonCard } from "../components/AgendaList";
import { Loaded, PageHead } from "../components/cells";
import { MonthGrid } from "../components/MonthGrid";
import { PortfolioPicker, usePortfolioSel } from "../components/PortfolioPicker";
import { Tabs, useTabParam } from "../components/Tabs";
import { Term } from "../components/Term";
import { TickerLink } from "../components/TickerLink";
import { filterItems, KINDS, soonItems, type Kind, type Who } from "../lib/agenda";
import { pageChapter, useGuideTree } from "../lib/guide";
import { formatSel, isDefaultSel } from "../lib/portfolioSel";

const VIEWS = ["agenda", "month"] as const;
const WHO: [Who, string][] = [["all", "Held & watched"], ["holding", "Held"], ["watch", "Watched"]];

/** The held/watched filter and the kinds shown, in the URL (`?who=`, `?kinds=`), so a view can be bookmarked. */
function useFilters(): [Who, Set<Kind>, (w: Who) => void, (k: Kind) => void] {
  const [params, setParams] = useSearchParams();
  const who = WHO.find(([w]) => w === params.get("who"))?.[0] ?? "all";
  const raw = params.get("kinds");
  const kinds = new Set<Kind>(raw === null ? KINDS.map(([k]) => k) : KINDS.map(([k]) => k).filter((k) => raw.split(",").includes(k)));
  const put = (key: string, v: string | null) => setParams((p) => {
    const next = new URLSearchParams(p);
    if (v === null) next.delete(key); else next.set(key, v);
    return next;
  }, { replace: true });
  const setWho = (w: Who) => put("who", w === "all" ? null : w);
  const toggle = (k: Kind) => {
    const next = new Set(kinds);
    if (next.has(k)) next.delete(k); else next.add(k);
    put("kinds", next.size === KINDS.length ? null : KINDS.map(([x]) => x).filter((x) => next.has(x)).join(","));
  };
  return [who, kinds, setWho, toggle];
}

function Soon({ d }: { d: AgendaView }) {
  const items = soonItems(d);
  return (
    <section className="group">
      <h2><Term k="cal_level">{`Next ${d.soon_days} days`}</Term></h2>
      {items.length === 0
        ? <p className="small">Nothing that needs attention in the next {d.soon_days} days.
          {d.no_date.length > 0 && <span className="muted"> ({d.no_date.length} stock(s) have no known date: see below.)</span>}</p>
        : <div className="tiles cal-soon">{items.map((i) => <SoonCard key={i.id} i={i} />)}</div>}
    </section>
  );
}

function NoDate({ d }: { d: AgendaView }) {
  if (d.no_date.length === 0 && d.excluded_funds === 0) return null;
  return (
    <section className="group">
      <h2>No date known</h2>
      {d.no_date.length > 0 ? (
        <ul className="small cal-nodate">
          {d.no_date.map((n) => (
            <li key={n.symbol}><TickerLink symbol={n.symbol} name={n.name} /> <span className="muted">
              {n.status === "holding" ? "held" : "watched"} · {n.reason}</span></li>
          ))}
        </ul>
      ) : <p className="small muted">Every held and watched stock has a date.</p>}
      {d.excluded_funds > 0 && <p className="small muted">{d.excluded_funds} fund(s) left out: funds don&apos;t report earnings.</p>}
    </section>
  );
}

/** The calendar: what is coming for the names you hold and watch, and which of it needs a look first. */
export function Calendar() {
  const [sel, setSel] = usePortfolioSel();
  const q = useQuery({ queryKey: ["calendar", formatSel(sel)], queryFn: () => api.calendar(sel), retry: false, staleTime: 60_000 });
  const [view, setView] = useTabParam(VIEWS, "agenda");
  const [who, kinds, setWho, toggle] = useFilters();
  const guide = useGuideTree().data;
  const chapter = guide ? pageChapter(guide.page_links, "/calendar") : null;
  return (
    <Loaded q={q} title="Calendar">
      {(d) => {
        const shown = filterItems(d.items, who, kinds);
        return (
          <>
            <PageHead title="Calendar" asof={d.asof} generated={d.generated}>
              The coming {d.days} days for the stocks you <b>hold and watch</b>: earnings and ex-dividend dates, your
              journal&apos;s review dates and your proposals&apos; time stops. Each item says <b>why</b> it is highlighted, by
              stated rules (how much of your money is at stake, how close the price is to your review level, fading
              momentum, estimate cuts, how sure the date is). The dates are Yahoo&apos;s, not confirmed by the companies; a
              window is shown as a window. Analysis, not advice.
            </PageHead>
            <p><PortfolioPicker sel={sel} onChange={setSel} />
              {!isDefaultSel(sel) && <span className="small warn-text"> Showing the chosen portfolios, not only yours.</span>}</p>
            <Soon d={d} />
            <section className="group">
              <div className="cal-controls">
                <Tabs tabs={[["agenda", "Agenda"], ["month", "Month"]]} value={view} onChange={setView} label="Calendar view" />
                <div className="seg" role="group" aria-label="Held or watched">
                  {WHO.map(([w, l]) => <button key={w} type="button" aria-pressed={who === w} onClick={() => setWho(w)}>{l}</button>)}
                </div>
                <div className="seg" role="group" aria-label="Kinds">
                  {KINDS.map(([k, l]) => <button key={k} type="button" aria-pressed={kinds.has(k)} onClick={() => toggle(k)}>{l}</button>)}
                </div>
              </div>
              {view === "agenda"
                ? <AgendaList items={shown} empty={d.items.length === 0 ? `Nothing dated in the next ${d.days} days.` : "No items match the filters."} />
                : <MonthGrid items={shown} today={d.today} days={d.days} />}
            </section>
            <NoDate d={d} />
            {(d.notes.length > 0 || chapter) && (
              <section className="group">
                <h2>Notes</h2>
                <ul className="small muted perf-notes">
                  {d.notes.map((n) => <li key={n}>{n}</li>)}
                  {chapter && <li><Link to={`/guide/${chapter}`}>How the calendar works (guide)</Link></li>}
                </ul>
              </section>
            )}
          </>
        );
      }}
    </Loaded>
  );
}

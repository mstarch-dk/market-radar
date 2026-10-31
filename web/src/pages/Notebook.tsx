import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError, type NotebookEntry, type NotebookListing } from "../api/client";
import { PageHead } from "../components/cells";
import { DataTable, type Col } from "../components/DataTable";
import { Markdown, useScrollToHash } from "../components/Markdown";
import { TickerLink } from "../components/TickerLink";
import { Badge } from "../components/ui";
import { date } from "../lib/format";

/** The notebook: what the Claude skills write (briefs, research memos, comparisons, the decision journal and its
 *  reviews), read-only. Writing stays with the skills in Claude Code. */

const TABS = [
  ["briefs", "Briefs"],
  ["research", "Research"],
  ["journal", "Journal"],
] as const;
type Tab = (typeof TABS)[number][0];

const TAB_OF: Record<string, Tab> = {
  briefs: "briefs", research: "research", compare: "research", proposals: "research", proposal_reviews: "research",
  scout: "research", journal: "journal", reviews: "journal",
};
const docPath = (e: Pick<NotebookEntry, "kind" | "name">) => `/notebook/${e.kind}/${encodeURIComponent(e.name)}`;
const STATUS_KIND: Record<string, string> = { open: "accent", closed: "", invalidated: "neg" };

export default function Notebook() {
  const { kind, name } = useParams();
  return kind && name ? <Document kind={kind} name={name} /> : <Listing />;
}

function useListing() {
  return useQuery({ queryKey: ["notebook"], queryFn: api.notebook });
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="note muted">{children}</p>;
}

function DocList({ rows, empty }: { rows: NotebookEntry[]; empty: React.ReactNode }) {
  if (!rows.length) return <Empty>{empty}</Empty>;
  return (
    <ul className="nb-list">
      {rows.map((r) => (
        <li key={r.name}>
          <Link to={docPath(r)}><b>{r.title}</b></Link>
          <span className="muted small"> · {r.date.length === 10 ? date(r.date) : r.date}</span>
          {r.ticker && r.kind === "research" && <> · <TickerLink symbol={r.ticker} /></>}
          {r.problem && <span className="warn-text small"> · {r.problem}</span>}
        </li>
      ))}
    </ul>
  );
}

const journalCols: Col<NotebookEntry>[] = [
  { key: "date", label: "Date", sort: (e) => e.date, render: (e) => date(e.date) },
  { key: "ticker", label: "Ticker", align: "l", sort: (e) => e.ticker ?? "", search: (e) => `${e.ticker ?? ""} ${e.title}`,
    render: (e) => (e.ticker ? <TickerLink symbol={e.ticker} />
      : e.meta?.type === "hypothesis" ? <Badge>hypotheses</Badge> : <span className="muted">–</span>) },
  { key: "action", label: "Action", align: "l", sort: (e) => e.meta?.action ?? "", filter: { kind: "enum", value: (e) => e.meta?.action ?? "(none)" },
    render: (e) => e.meta?.action ?? <span className="muted">–</span> },
  { key: "account", label: "Account", align: "l", sort: (e) => e.meta?.account ?? "", filter: { kind: "enum", value: (e) => e.meta?.account ?? "(none)" },
    render: (e) => e.meta?.account ?? <span className="muted">–</span> },
  { key: "horizon", label: "Horizon", align: "l", render: (e) => e.meta?.horizon ?? <span className="muted">–</span> },
  { key: "status", label: "Status", align: "l", sort: (e) => e.meta?.status ?? "", filter: { kind: "enum", value: (e) => e.meta?.status ?? "(none)" },
    render: (e) => (e.meta?.status ? <Badge kind={STATUS_KIND[e.meta.status] ?? ""}>{e.meta.status}</Badge> : <span className="muted">–</span>) },
  { key: "review", label: "Review by", sort: (e) => e.meta?.review_by ?? "",
    render: (e) => <>{e.meta?.review_by ? date(e.meta.review_by) : <span className="muted">–</span>}{e.review_due && <> <Badge kind="warn">review due</Badge></>}</> },
  { key: "title", label: "Entry", align: "l", render: (e) => (
    <div className="wrap"><Link to={docPath(e)}>{e.title}</Link>{e.problem && <><br /><span className="warn-text small">{e.problem}</span></>}</div>
  ) },
];

function Listing() {
  const q = useListing();
  const [params, setParams] = useSearchParams();
  const tab: Tab = (TABS.find(([t]) => t === params.get("tab"))?.[0]) ?? "briefs";
  const setTab = (t: Tab) => {
    const next = new URLSearchParams(params);
    next.set("tab", t);
    setParams(next, { replace: true });
  };
  const nb: NotebookListing | undefined = q.data;
  const counts: Record<Tab, number> = {
    briefs: nb?.briefs.length ?? 0,
    research: (nb?.research.length ?? 0) + (nb?.compare.length ?? 0) + (nb?.proposals.length ?? 0) + (nb?.scout.length ?? 0),
    journal: (nb?.journal.length ?? 0) + (nb?.reviews.length ?? 0),
  };
  const due = nb?.journal.filter((e) => e.review_due).length ?? 0;
  return (
    <>
      <PageHead title="Notebook">
        What the Claude skills have written for you: market briefs, research memos and comparisons, and your decision
        journal. These are your own files in <code>briefs/</code>, <code>research/</code> and <code>journal/</code>: local,
        never committed. They are read-only here; you write them with the skills in Claude Code.
      </PageHead>
      <div className="seg nb-tabs" role="tablist">
        {TABS.map(([t, label]) => (
          <button key={t} type="button" role="tab" aria-pressed={t === tab} aria-selected={t === tab} onClick={() => setTab(t)}>
            {label}{nb && <span className="muted"> {counts[t]}</span>}{t === "journal" && due > 0 && <> <Badge kind="warn">{due} due</Badge></>}
          </button>
        ))}
      </div>
      {q.isPending && <div className="skeleton" style={{ height: 240 }} aria-busy="true" />}
      {q.isError && <div className="error">Couldn&apos;t load the notebook: {q.error.message}</div>}
      {nb && tab === "briefs" && <Briefs nb={nb} />}
      {nb && tab === "research" && (
        <>
          <h2>Research memos</h2>
          <DocList rows={nb.research} empty={<>None yet. Write one with <code>/research &lt;ticker&gt;</code> in Claude Code.</>} />
          <h2>Comparisons</h2>
          <DocList rows={nb.compare} empty={<>None yet. Compare tickers with <code>/compare &lt;t1&gt; &lt;t2&gt; …</code> in Claude Code.</>} />
          <h2>Proposals</h2>
          <DocList rows={nb.proposals} empty={<>None yet. Ask for a basket with <code>/propose-portfolio &lt;portfolio&gt; &lt;amount&gt;</code> in
            Claude Code: it is tested against ACWI and the alternatives.</>} />
          <h2>Scout reports</h2>
          <DocList rows={nb.scout} empty={<>None yet. Run <code>/scout</code> in Claude Code: it searches what investors and the media
            are starting to talk about and gives you a short list of hypotheses to adopt or dismiss.</>} />
          {nb.proposal_reviews.length > 0 && <>
            <h2>Proposal reviews</h2>
            <DocList rows={nb.proposal_reviews} empty="" />
          </>}
        </>
      )}
      {nb && tab === "journal" && (
        <>
          <h2>Decisions</h2>
          {nb.journal.length
            ? <div className="card"><DataTable id="journal" csvName="journal" rows={nb.journal} cols={journalCols} rowKey={(e) => e.name} /></div>
            : <Empty>No decisions recorded yet. Log one with <code>/journal buy &lt;ticker&gt; …</code> (or sell, add, trim, pass) in
              Claude Code: it asks for your thesis, horizon and exit rule, and snapshots the radar&apos;s numbers.</Empty>}
          <h2>Monthly reviews</h2>
          <DocList rows={nb.reviews} empty={<>No reviews yet. Run <code>/journal review</code> once a month: it checks open theses
            against the radar.</>} />
        </>
      )}
    </>
  );
}

function Briefs({ nb }: { nb: NotebookListing }) {
  const latest = nb.briefs[0];
  if (!latest) {
    return <Empty>No briefs yet. Run <code>/market-brief</code> in Claude Code; the monthly scheduled task also writes one on the
      1st of each month.</Empty>;
  }
  return (
    <>
      <h2>Earlier briefs</h2>
      <DocList rows={nb.briefs.slice(1)} empty="None: this is the first." />
      <h2>Latest</h2>
      <Doc kind={latest.kind} name={latest.name} embedded />
    </>
  );
}

function Document({ kind, name }: { kind: string; name: string }) {
  const tab = TAB_OF[kind] ?? "briefs";
  return (
    <>
      <p className="small"><Link to={`/notebook?tab=${tab}`}>← Notebook</Link></p>
      <Doc kind={kind} name={name} />
    </>
  );
}

function Doc({ kind, name, embedded }: { kind: string; name: string; embedded?: boolean }) {
  const { hash } = useLocation();
  const q = useQuery({ queryKey: ["notebook-doc", kind, name], queryFn: () => api.notebookDocument(kind, name), retry: false });
  useScrollToHash(embedded ? null : q.data, hash);
  if (q.isPending) return <div className="skeleton" style={{ height: 400 }} aria-busy="true" />;
  if (q.isError) {
    return <div className="error">{q.error instanceof ApiError && q.error.status === 404
      ? <>That document doesn&apos;t exist (any more). <Link to="/notebook">Back to the notebook</Link></>
      : <>Couldn&apos;t load it: {q.error.message}</>}</div>;
  }
  const d = q.data;
  const m = d.meta;
  return (
    <article className={`prose nb-doc ${embedded ? "card" : ""}`}>
      {m && (
        <dl className="nb-facts">
          {m.ticker && <><dt>Ticker</dt><dd><TickerLink symbol={m.ticker} /></dd></>}
          {m.action && <><dt>Action</dt><dd>{m.action}</dd></>}
          {m.account && <><dt>Account</dt><dd>{m.account}</dd></>}
          {m.horizon && <><dt>Horizon</dt><dd>{m.horizon}</dd></>}
          {m.status && <><dt>Status</dt><dd><Badge kind={STATUS_KIND[m.status] ?? ""}>{m.status}</Badge></dd></>}
          {m.review_by && <><dt>Review by</dt><dd>{date(m.review_by)}{d.review_due && <> <Badge kind="warn">review due</Badge></>}</dd></>}
          {m.views && m.views.length > 0 && <><dt>Market views</dt><dd><Link to="/views">{m.views.map(String).join(", ")}</Link></dd></>}
        </dl>
      )}
      {d.problem && <p className="warn-text small">{d.problem}</p>}
      {d.ticker && !m && <p className="small muted">Ticker: <TickerLink symbol={d.ticker} /></p>}
      <Markdown markdown={d.markdown} headings={d.headings} />
    </article>
  );
}

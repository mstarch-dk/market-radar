import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type ViewIn, type ViewRow, type ViewTemplate, type ViewsPage } from "../api/client";
import { PageHead } from "../components/cells";
import { TickerLink } from "../components/TickerLink";
import { Badge } from "../components/ui";
import { EMPTY_VIEW, toViewIn, ViewEditor } from "../components/ViewEditor";
import { date, pct } from "../lib/format";
import { dots, STATE_KIND, VERDICT_KIND } from "../lib/views";

const HORIZON: Record<string, string> = { "3m": "3 months", "6m": "6 months", "12m": "1 year", "3y": "3 years" };

function value(kind: string | null | undefined, v: number | null | undefined): string {
  if (v === null || v === undefined) return "–";
  if (kind === "fred" || kind === "cli") return `${v > 0 ? "+" : ""}${v.toFixed(2)}`;
  return pct(v);
}

function exposureText(e: ViewIn["exposures"][number]) {
  return e.kind === "etf" || e.kind === "ticker" ? <TickerLink symbol={e.key} marker={false} /> : <>{e.kind} {e.key}</>;
}

function ViewCard({ v, onEdit }: { v: ViewRow; onEdit: () => void }) {
  const qc = useQueryClient();
  const [undo, setUndo] = useState<ViewRow | null>(null);
  const done = (page: ViewsPage) => {
    qc.setQueryData(["views"], page);
    qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === "views-align" || q.queryKey[0] === "profile" });
  };
  const archive = useMutation({
    mutationFn: () => api.editView(v.id, { ...toViewIn(v), status: v.status === "active" ? "archived" : "active" }),
    onSuccess: done,
  });
  const del = useMutation({ mutationFn: () => api.deleteView(v.id), onSuccess: (row) => { setUndo(row); qc.invalidateQueries({ queryKey: ["views"] }); } });
  const restore = useMutation({ mutationFn: (row: ViewRow) => api.restoreView(row), onSuccess: (p) => { setUndo(null); done(p); } });
  if (undo) {
    return <div className="card view-card gone">Deleted &ldquo;{undo.statement}&rdquo;.{" "}
      <button type="button" className="btn small" onClick={() => restore.mutate(undo)}>Undo</button></div>;
  }
  const ev = v.evidence;
  return (
    <article className={`card view-card ${v.status === "archived" ? "archived" : ""}`}>
      <div className="vc-head">
        <h3>{v.statement}</h3>
        {ev && <Badge kind={VERDICT_KIND[ev.verdict]} title="What the radar's data did over the last three months">
          data: {ev.verdict}</Badge>}
      </div>
      <div className="vc-meta small muted">
        <span title={`Conviction ${v.conviction} of 5`} className="dots">{dots(v.conviction)}</span>
        <span>{HORIZON[v.horizon]}</span>
        <span>since {date(v.created_at)}</span>
        {v.origin?.startsWith("scout:") && (
          <Badge title={`Adopted from a /scout candidate (${v.origin}); its frozen basket is followed on the Evidence page`}>
            from scout {date(v.origin.split(":")[1])}</Badge>
        )}
        {v.status === "archived" && <Badge>archived</Badge>}
      </div>
      {v.exposures.length > 0 && (
        <div className="vc-exp">
          {v.exposures.map((e, i) => (
            <span key={i} className={`chip ${e.effect > 0 ? "pos" : "neg"}`}>{e.effect > 0 ? "helps" : "hurts"} {exposureText(e)}</span>
          ))}
        </div>
      )}
      {ev && ev.items.length > 0 && (
        <table className="t vc-ev">
          <tbody>
            {ev.items.map((i) => (
              <tr key={i.indicator}>
                <td>{i.label}</td>
                <td className="muted small">should {i.expect === "up" ? "rise" : "fall"}</td>
                <td className="num">{value(i.kind, i.value)}</td>
                <td><Badge kind={STATE_KIND[i.state]}>{i.state}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {ev && ev.items.length === 0 && <p className="small muted">No indicators: the radar can&apos;t check this view against data.</p>}
      {v.rationale && <p className="small"><b>Why:</b> {v.rationale}</p>}
      {v.falsifier && <p className="small"><b>Would change my mind:</b> {v.falsifier}</p>}
      <div className="tx-actions">
        <button type="button" className="btn small" onClick={onEdit}>Edit</button>
        <button type="button" className="btn small" onClick={() => archive.mutate()}>{v.status === "active" ? "Archive" : "Re-activate"}</button>
        <button type="button" className="linkish small neg" onClick={() => del.mutate()}>Delete</button>
      </div>
    </article>
  );
}

function Templates({ templates, used, onPick }: { templates: ViewTemplate[]; used: Set<string>; onPick: (t: ViewTemplate) => void }) {
  const areas = [...new Set(templates.map((t) => t.area))];
  return (
    <details className="card templates" open={used.size === 0}>
      <summary><b>Start from a ready-made view</b> <span className="muted small">opposite views sit side by side: pick the one you actually believe, or neither</span></summary>
      {areas.map((a) => {
        const list = templates.filter((t) => t.area === a);
        const seen = new Set<string>();
        const ordered = list.flatMap((t) => {
          if (seen.has(t.key)) return [];
          seen.add(t.key);
          const pair = t.pair ? list.find((x) => x.key === t.pair) : undefined;
          if (pair) seen.add(pair.key);
          return pair ? [t, pair] : [t];
        });
        return (
          <section key={a}>
            <h3>{a}</h3>
            <div className="tpl-grid">
              {ordered.map((t) => (
                <div key={t.key} className={`tpl ${t.pair ? "paired" : ""}`}>
                  <p>{t.statement}</p>
                  <button type="button" className="btn small" disabled={used.has(t.key)} onClick={() => onPick(t)}>
                    {used.has(t.key) ? "Added" : "Use this"}</button>
                </div>
              ))}
            </div>
          </section>
        );
      })}
    </details>
  );
}

export function Views() {
  const q = useQuery({ queryKey: ["views"], queryFn: api.views });
  const [editing, setEditing] = useState<{ initial: ViewIn; id?: number } | null>(null);
  if (q.isPending) return <><PageHead title="My market views" /><div className="skeleton" style={{ height: 300 }} /></>;
  if (q.isError) return <><PageHead title="My market views" /><div className="error">Couldn&apos;t load: {q.error.message}</div></>;
  const d = q.data;
  const active = d.views.filter((v) => v.status === "active");
  const archived = d.views.filter((v) => v.status === "archived");
  const used = new Set(d.views.map((v) => v.template).filter((t): t is string => Boolean(t)));
  const fromTemplate = (t: ViewTemplate): ViewIn => ({
    ...EMPTY_VIEW, statement: t.statement, falsifier: t.falsifier ?? null, template: t.key,
    exposures: t.exposures, indicators: t.indicators,
  });
  return (
    <>
      <PageHead title="My market views">
        <b>{d.disclaimer}</b> Write down where you think the world is heading, how sure you are and what would change your
        mind. Each view says what it helps or hurts, so the ticker pages, the Momentum and Discover tables and the Claude
        skills (/research, /compare, /market-brief, /journal) can show how a name lines up with it.
      </PageHead>
      {editing ? (
        <ViewEditor key={editing.id ?? "new"} initial={editing.initial} id={editing.id} catalogue={d.catalogue} onDone={() => setEditing(null)} />
      ) : (
        <div className="tx-actions" style={{ marginBottom: 12 }}>
          <button type="button" className="btn primary" onClick={() => setEditing({ initial: EMPTY_VIEW })}>Write your own view</button>
        </div>
      )}
      {!editing && <Templates templates={d.templates} used={used} onPick={(t) => setEditing({ initial: fromTemplate(t) })} />}
      <h2>Active views ({active.length})</h2>
      {active.length === 0 && <p className="muted">No views yet. Start from a ready-made one above or write your own.</p>}
      <div className="views-grid">
        {active.map((v) => <ViewCard key={v.id} v={v} onEdit={() => setEditing({ initial: toViewIn(v), id: v.id })} />)}
      </div>
      {archived.length > 0 && (
        <details className="archived-views">
          <summary>Archived views ({archived.length})</summary>
          <div className="views-grid">
            {archived.map((v) => <ViewCard key={v.id} v={v} onEdit={() => setEditing({ initial: toViewIn(v), id: v.id })} />)}
          </div>
        </details>
      )}
    </>
  );
}

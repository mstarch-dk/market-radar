import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type RuleIn, type RuleRow, type RulesCatalogue, type RulesPage, type RuleTemplate } from "../api/client";
import { ActionCheck } from "../components/ActionCheck";
import { PageHead } from "../components/cells";
import { EMPTY_RULE, RuleEditor, toRuleIn } from "../components/RuleEditor";
import { RuleVerdicts } from "../components/RuleVerdicts";
import { Badge } from "../components/ui";
import { date, pct } from "../lib/format";
import { paramText, SEVERITY_KIND } from "../lib/rules";

function scopeText(s: RuleIn["scope"], names: Map<number, string>): string {
  const p = s?.portfolios ?? "real";
  const base = p === "real" ? "your real portfolios" : p === "all" ? "all portfolios" : p.map((i) => names.get(i) ?? `#${i}`).join(", ");
  return [base, s?.kind && `kind ${s.kind}`, s?.tag && `tag ${s.tag}`, s?.style && `${s.style} positions`].filter(Boolean).join(" · ");
}

function RuleCard({ r, catalogue, names, onEdit }: {
  r: RuleRow; catalogue: RulesCatalogue; names: Map<number, string>; onEdit: () => void;
}) {
  const qc = useQueryClient();
  const [undo, setUndo] = useState<RuleRow | null>(null);
  const done = (page: RulesPage) => { qc.setQueryData(["rules"], page); qc.invalidateQueries({ queryKey: ["me"] }); };
  const archive = useMutation({
    mutationFn: () => api.editRule(r.id, { ...toRuleIn(r), status: r.status === "active" ? "archived" : "active" }),
    onSuccess: done,
  });
  const del = useMutation({ mutationFn: () => api.deleteRule(r.id), onSuccess: (row) => { setUndo(row); qc.invalidateQueries({ queryKey: ["rules"] }); } });
  const restore = useMutation({ mutationFn: (row: RuleRow) => api.restoreRule(row), onSuccess: (p) => { setUndo(null); done(p); } });
  if (undo) {
    return <div className="card view-card gone">Deleted &ldquo;{undo.statement}&rdquo;.{" "}
      <button type="button" className="btn small" onClick={() => restore.mutate(undo)}>Undo</button></div>;
  }
  const kind = catalogue.kinds.find((k) => k.key === r.kind);
  return (
    <article className={`card view-card ${r.status === "archived" ? "archived" : ""}`}>
      <div className="vc-head">
        <h3>{r.statement}</h3>
        <Badge kind={SEVERITY_KIND[r.severity]}>{r.severity}</Badge>
      </div>
      <div className="vc-meta small muted">
        <span>{kind?.label ?? r.kind}</span>
        <span>{scopeText(r.scope, names)}</span>
        <span>since {date(r.created_at)}</span>
        {r.status === "archived" && <Badge>archived</Badge>}
      </div>
      {r.kind === "judgment"
        ? <p className="small muted">The radar can&apos;t check this one: it is shown as a question with every check, and Claude weighs it in the skills.</p>
        : <p className="small">{paramText(kind, r.params)}</p>}
      {r.rationale && <p className="small"><b>Why:</b> {r.rationale}</p>}
      <div className="tx-actions">
        <button type="button" className="btn small" onClick={onEdit}>Edit</button>
        <button type="button" className="btn small" onClick={() => archive.mutate()}>{r.status === "active" ? "Archive" : "Re-activate"}</button>
        <button type="button" className="linkish small neg" onClick={() => del.mutate()}>Delete</button>
      </div>
    </article>
  );
}

function Templates({ templates, used, onPick }: { templates: RuleTemplate[]; used: Set<string>; onPick: (t: RuleTemplate) => void }) {
  return (
    <details className="card templates" open={used.size === 0}>
      <summary><b>Start from a template</b> <span className="muted small">generic starting points: change the numbers and the why to your own</span></summary>
      <div className="tpl-grid">
        {templates.map((t) => (
          <div key={t.key} className="tpl">
            <p>{t.statement}</p>
            {t.rationale && <p className="small muted">{t.rationale}</p>}
            <button type="button" className="btn small" disabled={used.has(t.key)} onClick={() => onPick(t)}>
              {used.has(t.key) ? "Added" : "Use this"}</button>
          </div>
        ))}
      </div>
    </details>
  );
}

function Replay() {
  const [on, setOn] = useState(false);
  const q = useQuery({ queryKey: ["rules-replay"], queryFn: api.rulesReplay, enabled: on });
  return (
    <details className="card" onToggle={(e) => setOn((e.target as HTMLDetailsElement).open)}>
      <summary><b>Would my rules have helped?</b> <span className="muted small">today&apos;s rules on your own past trades</span></summary>
      {q.isPending && on && <div className="skeleton" style={{ height: 120 }} />}
      {q.isError && <p className="small neg">Couldn&apos;t replay: {q.error.message}</p>}
      {q.data && (
        <>
          <p className="small muted">{q.data.note} {q.data.n_trades} trades.</p>
          {q.data.rules.length === 0 ? <p className="small muted">No checkable rules to replay.</p> : (
            <table className="t">
              <thead><tr><th>Rule</th><th>Side</th><th className="num">Flagged</th><th className="num">Afterwards vs ACWI</th>
                <th className="num">Let through</th><th className="num">Afterwards vs ACWI</th><th className="num">Unknown</th></tr></thead>
              <tbody>
                {q.data.rules.map((x) => (
                  <tr key={`${x.rule_id}-${x.side}`}>
                    <td>{x.statement}
                      {x.flagged.length > 0 && <div className="small muted">{x.flagged.map((f) =>
                        `${f.date} ${f.symbol} (${f.rel === null || f.rel === undefined ? "–" : pct(f.rel)})`).join(" · ")}</div>}
                    </td>
                    <td>{x.side}s</td>
                    <td className="num">{x.n_flagged}</td>
                    <td className="num">{x.flagged_rel === null || x.flagged_rel === undefined ? "–" : pct(x.flagged_rel)}</td>
                    <td className="num">{x.n_passed}</td>
                    <td className="num">{x.passed_rel === null || x.passed_rel === undefined ? "–" : pct(x.passed_rel)}</td>
                    <td className="num">{x.n_unknown}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="small muted">A flagged buy that then lagged ACWI, or a flagged sale that then rose, is a trade the rule
            would have saved you from; with so few trades this shows what happened, not that a rule works.</p>
        </>
      )}
    </details>
  );
}

export function Rules() {
  const q = useQuery({ queryKey: ["rules"], queryFn: api.rules });
  const { data: portfolios = [] } = useQuery({ queryKey: ["portfolios"], queryFn: api.portfolios });
  const [params] = useSearchParams();
  const [editing, setEditing] = useState<{ initial: RuleIn; id?: number } | null>(null);
  if (q.isPending) return <><PageHead title="My trading rules" /><div className="skeleton" style={{ height: 300 }} /></>;
  if (q.isError) return <><PageHead title="My trading rules" /><div className="error">Couldn&apos;t load: {q.error.message}</div></>;
  const d = q.data;
  const names = new Map(portfolios.map((p) => [p.id, p.name]));
  const active = d.rules.filter((r) => r.status === "active");
  const archived = d.rules.filter((r) => r.status === "archived");
  const used = new Set(d.rules.map((r) => r.template).filter((t): t is string => Boolean(t)));
  const fromTemplate = (t: RuleTemplate): RuleIn => ({
    ...EMPTY_RULE, statement: t.statement, kind: t.kind, params: t.params, scope: t.scope, severity: t.severity,
    rationale: t.rationale ?? null, template: t.key,
  });
  const edit = (r: RuleRow) => setEditing({ initial: toRuleIn(r), id: r.id });
  return (
    <>
      <PageHead title="My trading rules">
        <b>{d.disclaimer}</b> Write down the rules you want to trade by, while things are calm. Then test an action against
        them: each rule says whether it breaks, comes close or complies, with the numbers, and what would make it comply.
        The Portfolio editor, the holdings table, the monthly brief and the Claude skills (/journal, /propose-portfolio,
        /rules) read the same rules.
      </PageHead>

      {d.standing && (
        <section className="card">
          <h2>Breaks right now</h2>
          {d.standing.rows.length === 0
            ? <p className="small muted">Nothing you hold breaks or comes close to your rules about holdings (prices to {d.standing.asof}).</p>
            : <RuleVerdicts rows={d.standing.rows} />}
          {d.standing.notes.map((n) => <p key={n} className="small muted">{n}</p>)}
        </section>
      )}

      <ActionCheck catalogue={d.catalogue} ticker={params.get("ticker") ?? ""} />

      {editing ? (
        <RuleEditor key={editing.id ?? "new"} initial={editing.initial} id={editing.id} catalogue={d.catalogue} onDone={() => setEditing(null)} />
      ) : (
        <div className="tx-actions" style={{ margin: "12px 0" }}>
          <button type="button" className="btn primary" onClick={() => setEditing({ initial: EMPTY_RULE })}>Write your own rule</button>
        </div>
      )}
      {!editing && <Templates templates={d.templates} used={used} onPick={(t) => setEditing({ initial: fromTemplate(t) })} />}

      <h2>Active rules ({active.length})</h2>
      {active.length === 0 && <p className="muted">No rules yet. Start from a template above or write your own.</p>}
      <div className="views-grid">
        {active.map((r) => <RuleCard key={r.id} r={r} catalogue={d.catalogue} names={names} onEdit={() => edit(r)} />)}
      </div>
      {archived.length > 0 && (
        <details className="archived-views">
          <summary>Archived rules ({archived.length})</summary>
          <div className="views-grid">
            {archived.map((r) => <RuleCard key={r.id} r={r} catalogue={d.catalogue} names={names} onEdit={() => edit(r)} />)}
          </div>
        </details>
      )}
      {active.length > 0 && <Replay />}
    </>
  );
}

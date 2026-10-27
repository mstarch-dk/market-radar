import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type RuleIn, type RuleKind, type RulesCatalogue, type RulesPage, type RuleRow } from "../api/client";

type Scope = NonNullable<RuleIn["scope"]>;
type Exposure = { kind: string; key: string };

const EXPOSURE_LABEL: Record<string, string> = {
  etf: "ETF / theme", sector: "Sector", industry: "Industry", region: "Region / country", ticker: "Ticker",
};
const SEVERITY: Record<RuleIn["severity"] & string, string> = {
  hard: "Hard: I don't break it", soft: "Soft: only with a reason", reminder: "Reminder: worth a thought",
};
const ACCOUNT: Record<string, string> = { ask: "Aktiesparekonto", frie_midler: "Frie midler", pension: "Pension", other: "Other" };

export const EMPTY_RULE: RuleIn = {
  statement: "", kind: "max_position_weight", params: {}, scope: { portfolios: "real" }, severity: "soft",
  rationale: null, template: null, status: "active",
};

/** The editable fields of a stored rule (what the API accepts back). */
export const toRuleIn = (r: RuleRow): RuleIn => ({
  statement: r.statement, kind: r.kind, params: r.params ?? {}, scope: r.scope, severity: r.severity,
  rationale: r.rationale ?? null, template: r.template ?? null, status: r.status,
});

/** A kind's parameters with their defaults (a new kind starts from these). */
export const defaults = (k: RuleKind | undefined): Record<string, unknown> =>
  Object.fromEntries((k?.params ?? []).filter((p) => p.default !== null && p.default !== undefined).map((p) => [p.key, p.default]));

/** Write or edit one trading rule: the statement in your words, what kind of rule it is and its numbers, which
 *  portfolios it covers, how strict you are about it and why you have it. */
export function RuleEditor({ initial, id, catalogue, onDone }: {
  initial: RuleIn; id?: number; catalogue: RulesCatalogue; onDone: () => void;
}) {
  const qc = useQueryClient();
  const { data: portfolios = [] } = useQuery({ queryKey: ["portfolios"], queryFn: api.portfolios });
  const [r, setR] = useState<RuleIn>(initial);
  const kind = catalogue.kinds.find((k) => k.key === r.kind);
  const scope: Scope = r.scope ?? { portfolios: "real" };
  const params = (r.params ?? {}) as Record<string, unknown>;
  const set = <K extends keyof RuleIn>(k: K, v: RuleIn[K]) => setR((x) => ({ ...x, [k]: v }));
  const setParam = (k: string, v: unknown) => set("params", { ...params, [k]: v });
  const setScope = (s: Partial<Scope>) => set("scope", { ...scope, ...s });
  const save = useMutation({
    mutationFn: () => (id ? api.editRule(id, r) : api.addRule(r)),
    onSuccess: (page: RulesPage) => { qc.setQueryData(["rules"], page); qc.invalidateQueries({ queryKey: ["me"] }); onDone(); },
  });
  const pickedIds = Array.isArray(scope.portfolios) ? scope.portfolios : [];
  const exposures = (params.exposures as Exposure[] | undefined) ?? [];
  const setExp = (i: number, e: Partial<Exposure>) => setParam("exposures", exposures.map((x, j) => (j === i ? { ...x, ...e } : x)));
  const options = (k: string): [string, string][] =>
    k === "etf" ? catalogue.etfs.map((e) => [e.ticker ?? "", `${e.ticker} · ${e.name}`])
      : k === "sector" ? catalogue.sectors.map((s) => [s, s])
      : k === "region" ? catalogue.regions.map((s) => [s, s]) : [];

  return (
    <form className="card view-editor" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <h2>{id ? "Edit rule" : "New rule"}</h2>
      <div className="tx-grid">
        <label className="full">The rule, in your words
          <textarea rows={2} value={r.statement} onChange={(e) => set("statement", e.target.value)} required
            placeholder="e.g. No single stock above 10 % of my portfolios" />
        </label>
        <label>What the radar checks
          <select value={r.kind} onChange={(e) => {
            const k = catalogue.kinds.find((x) => x.key === e.target.value);
            setR((x) => ({ ...x, kind: e.target.value, params: defaults(k) }));
          }}>
            {catalogue.kinds.map((k) => <option key={k.key} value={k.key}>{k.label}</option>)}
          </select>
        </label>
        <label>How strict
          <select value={r.severity} onChange={(e) => set("severity", e.target.value as RuleIn["severity"])}>
            {Object.entries(SEVERITY).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </label>
        {kind?.params.filter((p) => p.type !== "exposures").map((p) => (
          <label key={p.key}>{p.label}
            {p.type === "choice" ? (
              <select value={String(params[p.key] ?? p.default ?? "")}
                onChange={(e) => setParam(p.key, typeof p.default === "number" ? Number(e.target.value) : e.target.value)}>
                {(p.choices ?? []).map((c) => <option key={String(c)} value={String(c)}>{ACCOUNT[String(c)] ?? String(c)}</option>)}
              </select>
            ) : p.type === "tickers" ? (
              <input value={((params[p.key] as string[] | undefined) ?? []).join(", ")} placeholder="e.g. ACWI"
                onChange={(e) => setParam(p.key, e.target.value.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean))} />
            ) : (
              <input type="number" step="any" min={p.min ?? undefined} max={p.max ?? undefined}
                value={params[p.key] === undefined || params[p.key] === null ? "" : String(params[p.key])}
                onChange={(e) => setParam(p.key, e.target.value === "" ? null : Number(e.target.value))} />
            )}
          </label>
        ))}
        {kind?.needs && <p className="full small muted">Reads: {kind.needs}.</p>}
      </div>

      {kind?.params.some((p) => p.type === "exposures") && (
        <>
          <h3>What counts towards the cap (any of)</h3>
          <p className="small muted">The same vocabulary as your market views: an ETF also matches every stock whose returns
            relative to ACWI move with it.</p>
          {exposures.map((x, i) => (
            <div key={i} className="view-row">
              <select value={x.kind} onChange={(e) => setExp(i, { kind: e.target.value, key: "" })} aria-label="Kind">
                {catalogue.exposure_kinds.map((k) => <option key={k} value={k}>{EXPOSURE_LABEL[k] ?? k}</option>)}
              </select>
              <input value={x.key} onChange={(e) => setExp(i, { key: e.target.value })} list={`rexp-${i}`} aria-label="Exposure"
                placeholder={x.kind === "industry" ? "e.g. Semiconductors" : x.kind === "ticker" ? "e.g. NVDA" : ""} />
              <datalist id={`rexp-${i}`}>{options(x.kind).map(([val, l]) => <option key={val} value={val}>{l}</option>)}</datalist>
              <button type="button" className="linkish small" onClick={() => setParam("exposures", exposures.filter((_, j) => j !== i))}>remove</button>
            </div>
          ))}
          <button type="button" className="btn small" onClick={() => setParam("exposures", [...exposures, { kind: "etf", key: "" }])}>
            + Add exposure</button>
        </>
      )}

      <h3>Which portfolios</h3>
      <div className="tx-grid">
        <label>Portfolios
          <select value={Array.isArray(scope.portfolios) ? "chosen" : scope.portfolios ?? "real"}
            onChange={(e) => setScope({ portfolios: e.target.value === "chosen" ? [] : e.target.value as "real" | "all" })}>
            <option value="real">Your real portfolios</option>
            <option value="all">All, virtual ones too</option>
            <option value="chosen">Chosen portfolios</option>
          </select>
        </label>
        <label>Account kind
          <select value={scope.kind ?? ""} onChange={(e) => setScope({ kind: (e.target.value || null) as Scope["kind"] })}>
            <option value="">Any</option>
            {catalogue.account_kinds.map((k) => <option key={k} value={k}>{ACCOUNT[k] ?? k}</option>)}
          </select>
        </label>
        <label>Style
          <select value={scope.style ?? ""} onChange={(e) => setScope({ style: (e.target.value || null) as Scope["style"] })}>
            <option value="">Any position</option>
            {catalogue.styles.map((s) => <option key={s} value={s}>{s} positions</option>)}
          </select>
        </label>
        <label>Tag <span className="hint">(optional)</span>
          <input value={scope.tag ?? ""} onChange={(e) => setScope({ tag: e.target.value || null })} />
        </label>
        {Array.isArray(scope.portfolios) && (
          <div className="full">
            {portfolios.filter((p) => !p.archived).map((p) => (
              <label key={p.id} className="small confirm">
                <input type="checkbox" checked={pickedIds.includes(p.id)} onChange={(e) => setScope({
                  portfolios: e.target.checked ? [...pickedIds, p.id] : pickedIds.filter((x) => x !== p.id) })} />
                {" "}{p.name}{p.mode === "virtual" ? " (virtual)" : ""}
              </label>
            ))}
          </div>
        )}
        {scope.style && <p className="full small muted">A style-scoped rule reads the style you give a test action, else
          the <code>style:</code> in the ticker&apos;s open journal entry; without either it shows as unknown.</p>}
      </div>

      <label className="full">Why I have this rule <span className="hint">(the lesson behind it)</span>
        <textarea rows={2} value={r.rationale ?? ""} onChange={(e) => set("rationale", e.target.value || null)} />
      </label>

      <div className="tx-actions">
        <button type="submit" className="btn primary"
          disabled={!r.statement.trim() || exposures.some((x) => !x.key.trim()) || save.isPending
            || (Array.isArray(scope.portfolios) && pickedIds.length === 0)}>
          {save.isPending ? "Saving…" : "Save rule"}</button>
        <button type="button" className="btn" onClick={onDone}>Cancel</button>
        {save.isError && <span className="small neg">{save.error.message}</span>}
      </div>
    </form>
  );
}

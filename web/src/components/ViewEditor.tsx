import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type ViewIn, type ViewRow, type ViewsCatalogue, type ViewsPage } from "../api/client";

type Exposure = ViewIn["exposures"][number];
type Indicator = ViewIn["indicators"][number];

const KIND_LABEL: Record<Exposure["kind"], string> = {
  etf: "ETF / theme", sector: "Sector", industry: "Industry", region: "Region / country", ticker: "Ticker",
};
const CONVICTION = ["", "1 · a hunch", "2 · leaning", "3 · fairly sure", "4 · confident", "5 · very sure"];
const HORIZON: Record<ViewIn["horizon"], string> = { "3m": "3 months", "6m": "6 months", "12m": "1 year", "3y": "3 years" };

export const EMPTY_VIEW: ViewIn = {
  statement: "", conviction: 3, horizon: "12m", rationale: null, falsifier: null, template: null, status: "active",
  exposures: [], indicators: [],
};

/** The editable fields of a stored view (what the API accepts back). */
export const toViewIn = (v: ViewRow): ViewIn => ({
  statement: v.statement, conviction: v.conviction, horizon: v.horizon, rationale: v.rationale ?? null,
  falsifier: v.falsifier ?? null, template: v.template ?? null, status: v.status, exposures: v.exposures, indicators: v.indicators,
});

/** Write or edit one market view: the statement, how sure you are and for how long, why, what would change your
 *  mind, what it helps or hurts (exposures) and which readings would confirm it (indicators). */
export function ViewEditor({ initial, id, catalogue, onDone }: {
  initial: ViewIn; id?: number; catalogue: ViewsCatalogue; onDone: () => void;
}) {
  const qc = useQueryClient();
  const [v, setV] = useState<ViewIn>(initial);
  const set = <K extends keyof ViewIn>(k: K, val: ViewIn[K]) => setV((x) => ({ ...x, [k]: val }));
  const save = useMutation({
    mutationFn: () => (id ? api.editView(id, v) : api.addView(v)),
    onSuccess: (page: ViewsPage) => {
      qc.setQueryData(["views"], page);
      qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === "views-align" || q.queryKey[0] === "profile" });
      onDone();
    },
  });
  const setExp = (i: number, e: Partial<Exposure>) => set("exposures", v.exposures.map((x, j) => (j === i ? { ...x, ...e } : x)));
  const setInd = (i: number, e: Partial<Indicator>) => set("indicators", v.indicators.map((x, j) => (j === i ? { ...x, ...e } : x)));
  const options = (k: Exposure["kind"]) =>
    k === "etf" ? catalogue.etfs.map((e) => [e.ticker, `${e.ticker} · ${e.name}`])
      : k === "sector" ? catalogue.sectors.map((s) => [s, s])
      : k === "region" ? catalogue.regions.map((s) => [s, s]) : [];

  return (
    <form className="card view-editor" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <h2>{id ? "Edit view" : "New view"}</h2>
      <div className="tx-grid">
        <label className="full">Statement
          <textarea rows={2} value={v.statement} onChange={(e) => set("statement", e.target.value)} required
            placeholder="e.g. European defence spending keeps rising for years" />
        </label>
        <label>How sure are you?
          <select value={v.conviction} onChange={(e) => set("conviction", Number(e.target.value))}>
            {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{CONVICTION[n]}</option>)}
          </select>
        </label>
        <label>Over what horizon?
          <select value={v.horizon} onChange={(e) => set("horizon", e.target.value as ViewIn["horizon"])}>
            {Object.entries(HORIZON).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </label>
        <label className="full">Why do you believe it? <span className="hint">(optional)</span>
          <textarea rows={2} value={v.rationale ?? ""} onChange={(e) => set("rationale", e.target.value || null)} />
        </label>
        <label className="full">What would change your mind?
          <textarea rows={2} value={v.falsifier ?? ""} onChange={(e) => set("falsifier", e.target.value || null)}
            placeholder="The observation that would make you drop this view" />
        </label>
      </div>

      <h3>What it helps or hurts</h3>
      <p className="small muted">An ETF also matches every stock whose returns relative to ACWI move with it.</p>
      {v.exposures.map((x, i) => (
        <div key={i} className="view-row">
          <select value={x.effect} onChange={(e) => setExp(i, { effect: Number(e.target.value) as Exposure["effect"] })} aria-label="Effect">
            <option value={1}>helps</option><option value={-1}>hurts</option>
          </select>
          <select value={x.kind} onChange={(e) => setExp(i, { kind: e.target.value as Exposure["kind"], key: "" })} aria-label="Kind">
            {Object.entries(KIND_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <input value={x.key} onChange={(e) => setExp(i, { key: e.target.value })} list={`exp-${i}`} aria-label="Exposure"
            placeholder={x.kind === "industry" ? "e.g. Banks" : x.kind === "ticker" ? "e.g. NOVO-B.CO" : x.kind === "region" ? "e.g. europe or Denmark" : ""} />
          <datalist id={`exp-${i}`}>{options(x.kind).map(([val, l]) => <option key={val} value={val}>{l}</option>)}</datalist>
          <button type="button" className="linkish small" onClick={() => set("exposures", v.exposures.filter((_, j) => j !== i))}>remove</button>
        </div>
      ))}
      <button type="button" className="btn small" onClick={() => set("exposures", [...v.exposures, { kind: "etf", key: "", effect: 1 }])}>
        + Add exposure</button>

      <h3>What would show it in the data</h3>
      {v.indicators.map((x, i) => (
        <div key={i} className="view-row">
          <select value={x.indicator} onChange={(e) => setInd(i, { indicator: e.target.value })} aria-label="Indicator">
            {catalogue.indicators.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
          </select>
          <select value={x.expect} onChange={(e) => setInd(i, { expect: e.target.value as Indicator["expect"] })} aria-label="Direction">
            <option value="up">should rise</option><option value="down">should fall</option>
          </select>
          <button type="button" className="linkish small" onClick={() => set("indicators", v.indicators.filter((_, j) => j !== i))}>remove</button>
        </div>
      ))}
      <button type="button" className="btn small"
        onClick={() => set("indicators", [...v.indicators, { indicator: catalogue.indicators[0]?.key ?? "", expect: "up" }])}>
        + Add indicator</button>

      <div className="tx-actions">
        <button type="submit" className="btn primary" disabled={!v.statement.trim() || v.exposures.some((x) => !x.key.trim()) || save.isPending}>
          {save.isPending ? "Saving…" : "Save view"}</button>
        <button type="button" className="btn" onClick={onDone}>Cancel</button>
        {save.isError && <span className="small neg">{save.error.message}</span>}
      </div>
    </form>
  );
}

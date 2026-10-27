import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, type ActionIn, type CheckResult, type RulesCatalogue } from "../api/client";
import { actionProblem, type AmountMode, toAction } from "../lib/rules";
import { RuleVerdicts } from "./RuleVerdicts";
import { SymbolPicker } from "./SymbolPicker";

const HORIZON: Record<string, string> = { "1m": "1 month", "3m": "3 months", "6m": "6 months", "12m": "1 year", "3y": "3 years" };

/** Test an action against your rules: buy or sell, a ticker, a portfolio, an amount (DKK, shares, or a share of
 *  the position for a sale), and optionally the style and horizon. Nothing is saved or sent anywhere. */
export function ActionCheck({ catalogue, ticker = "" }: { catalogue: RulesCatalogue; ticker?: string }) {
  const { data: portfolios = [] } = useQuery({ queryKey: ["portfolios"], queryFn: api.portfolios });
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [sym, setSym] = useState(ticker);
  const [portfolio, setPortfolio] = useState<number | null>(null);
  const [mode, setMode] = useState<AmountMode>("dkk");
  const [amount, setAmount] = useState("");
  const [style, setStyle] = useState<ActionIn["style"]>(null);
  const [horizon, setHorizon] = useState<ActionIn["horizon"]>(null);
  const run = useMutation({ mutationFn: (a: ActionIn) => api.checkRules(a) });
  const problem = actionProblem({ side, ticker: sym, mode, amount });
  const result: CheckResult | undefined = run.data;
  const active = portfolios.filter((p) => !p.archived);

  return (
    <section className="card action-check">
      <h2>Test an action</h2>
      <form className="tx-grid" onSubmit={(e) => {
        e.preventDefault();
        if (!problem) run.mutate(toAction({ side, ticker: sym, portfolio, mode, amount, style, horizon }));
      }}>
        <label>Buy or sell
          <select value={side} onChange={(e) => { setSide(e.target.value as "buy" | "sell"); if (e.target.value === "buy" && mode === "fraction") setMode("dkk"); }}>
            <option value="buy">Buy</option><option value="sell">Sell</option>
          </select>
        </label>
        <label>Ticker <SymbolPicker value={sym} onChange={setSym} /></label>
        <label>Portfolio
          <select value={portfolio ?? ""} onChange={(e) => setPortfolio(e.target.value ? Number(e.target.value) : null)}>
            <option value="">The default portfolio</option>
            {active.map((p) => <option key={p.id} value={p.id}>{p.name}{p.mode === "virtual" ? " (virtual)" : ""}</option>)}
          </select>
        </label>
        <label>Amount
          <span className="row">
            <input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal"
              placeholder={mode === "fraction" ? "0.5 = half" : mode === "shares" ? "shares" : "DKK"} />
            <select value={mode} onChange={(e) => setMode(e.target.value as AmountMode)} aria-label="Unit">
              <option value="dkk">DKK</option><option value="shares">shares</option>
              {side === "sell" && <option value="fraction">of the position</option>}
            </select>
          </span>
        </label>
        <label>Style <span className="hint">(optional)</span>
          <select value={style ?? ""} onChange={(e) => setStyle((e.target.value || null) as ActionIn["style"])}>
            <option value="">From its journal entry</option>
            {catalogue.styles.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label>Horizon <span className="hint">(optional)</span>
          <select value={horizon ?? ""} onChange={(e) => setHorizon((e.target.value || null) as ActionIn["horizon"])}>
            <option value="">From its journal entry</option>
            {catalogue.horizons.map((h) => <option key={h} value={h}>{HORIZON[h] ?? h}</option>)}
          </select>
        </label>
        <div className="full tx-actions">
          <button type="submit" className="btn primary" disabled={Boolean(problem) || run.isPending}>
            {run.isPending ? "Checking…" : "Check against my rules"}</button>
          {problem && amount && <span className="small muted">{problem}</span>}
          {run.isError && <span className="small neg">{run.error.message}</span>}
        </div>
      </form>
      {result && (
        <div className="check-result">
          <p className="small">
            <b>{result.action.side === "buy" ? "Buy" : "Sell"} {result.action.symbol}</b>{result.action.name ? ` (${result.action.name})` : ""} in{" "}
            {result.action.portfolio}:{" "}
            {result.action.amount_dkk === null || result.action.amount_dkk === undefined ? "value unknown"
              : `${Math.round(result.action.amount_dkk).toLocaleString("da-DK")} DKK`}
            {result.action.quantity ? `, ${Number(result.action.quantity.toFixed(4))} shares` : ""}
            {result.action.price ? ` at ${result.action.price.toFixed(2)} ${result.action.currency ?? ""}` : ""}
            {result.action.style ? ` · ${result.action.style}${result.action.style_from === "journal" ? " (from the journal)" : ""}` : ""}
            <span className="muted"> · prices to {result.asof}</span>
          </p>
          {result.notes.map((n) => <p key={n} className="small muted">{n}</p>)}
          <RuleVerdicts rows={result.verdicts} />
        </div>
      )}
    </section>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { api, type Portfolio as PortfolioT, type TxIn, type TxRow } from "../api/client";
import { DataTable } from "../components/DataTable";
import { ImportsList, ImportWizard } from "../components/ImportWizard";
import { usePortfolioSel } from "../components/PortfolioPicker";
import { AccountsPanel, KINDS } from "../components/PortfoliosPanel";
import { describeTx, posCols, txCols } from "../components/portfolioTables";
import { Tabs, useTabParam } from "../components/Tabs";
import { PORTFOLIO_KEYS, TxForm } from "../components/TxForm";
import { num } from "../lib/format";
import { DEFAULT_SEL, formatSel, isDefaultSel, type PortfolioSel } from "../lib/portfolioSel";

const TABS = ["positions", "transactions", "imports", "accounts"] as const;
type Tab = (typeof TABS)[number];

/** Trades that came in before portfolios sit in "Main": a nudge to move them into the right account. */
function MoveFromMain({ portfolios, tx, onMoved }: { portfolios: PortfolioT[]; tx: TxRow[]; onMoved: () => void }) {
  const main = portfolios.find((p) => p.name === "Main" && p.mode === "real" && p.n_tx > 0);
  const targets = portfolios.filter((p) => p.mode === "real" && !p.archived && p.id !== main?.id);
  const [to, setTo] = useState<number | "">("");
  const [symbol, setSymbol] = useState("");
  const move = useMutation({ mutationFn: () => api.moveRows(main!.id, { to: Number(to), symbols: symbol ? [symbol] : null }),
    onSuccess: () => { setSymbol(""); onMoved(); } });
  if (!main || targets.length === 0) return null;
  const symbols = [...new Set(tx.filter((t) => t.portfolio_id === main.id && t.symbol).map((t) => t.symbol!))].sort();
  return (
    <div className="notes pf-banner" role="status">
      <span>{main.n_tx} trades are in <b>Main</b>, not yet in one of your accounts. Move</span>
      <select value={symbol} onChange={(e) => setSymbol(e.target.value)} aria-label="Which trades">
        <option value="">all of them</option>
        {symbols.map((s) => <option key={s} value={s}>the {s} trades</option>)}
      </select>
      <span>to</span>
      <select value={to} onChange={(e) => setTo(e.target.value ? Number(e.target.value) : "")} aria-label="Move to">
        <option value="">choose…</option>
        {targets.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      <button type="button" className="btn small" disabled={to === "" || move.isPending} onClick={() => move.mutate()}>Move</button>
      {move.isError && <span className="small neg">{move.error.message}</span>}
      {move.data && <span className="small pos">Moved {move.data.moved}.</span>}
    </div>
  );
}

/** One chip per account (and "All"), with its value in DKK: choosing one shows only that account below. */
function AccountsStrip({ accounts, sel, onChange }: { accounts: PortfolioT[]; sel: PortfolioSel; onChange: (s: PortfolioSel) => void }) {
  const cmp = useQuery({ queryKey: ["comparison", "real", ""], queryFn: () => api.compare(undefined, undefined), retry: false });
  const value = new Map(cmp.data?.rows.filter((r) => r.portfolio).map((r) => [r.portfolio!.id, r.stats?.value_dkk ?? null]));
  const chosen = "ids" in sel ? sel.ids : [];
  const values = accounts.filter((p) => p.n_tx > 0).map((p) => value.get(p.id));
  const total = cmp.data && values.every((v) => v != null) ? values.reduce((a, v) => a! + v!, 0) : null;
  const chip = (key: string, on: boolean, onClick: () => void, title: string, sub: string, v: number | null | undefined) => (
    <button key={key} type="button" className={`acct-chip ${on ? "on" : ""}`} aria-pressed={on} onClick={onClick}>
      <b>{title}</b>
      <span className="muted small">{sub}</span>
      <span className="small">{v != null ? `${num(v, 0)} DKK` : <span className="muted">–</span>}</span>
    </button>
  );
  return (
    <div className="acct-strip" role="group" aria-label="Account">
      {chip("all", isDefaultSel(sel), () => onChange(DEFAULT_SEL), "All accounts", `${accounts.length} accounts`, total)}
      {accounts.map((p) => chip(String(p.id), chosen.length === 1 && chosen[0] === p.id, () => onChange({ ids: [p.id], tags: [] }),
        p.name, `${KINDS[p.kind][0]}${p.archived ? " · archived" : ""}`, p.n_tx ? value.get(p.id) : null))}
    </div>
  );
}

/** Your accounts (the real portfolios): positions, transactions, imports and the accounts themselves, in tabs.
 *  Virtual portfolios (simulations, A/B tests, forks) are on the Experiments page. */
export function Portfolio() {
  const qc = useQueryClient();
  const [sel, setSel] = usePortfolioSel();
  const key = formatSel(sel);
  const { data: portfolios } = useQuery({ queryKey: ["portfolios"], queryFn: api.portfolios });
  const pos = useQuery({ queryKey: ["positions", key], queryFn: () => api.positions(sel) });
  const tx = useQuery({ queryKey: ["transactions", key], queryFn: () => api.transactions(sel) });
  const empty = tx.data !== undefined && tx.data.length === 0;
  const [tab, setTab] = useTabParam(TABS, "positions");
  const [form, setForm] = useState<{ edit: TxRow | null; type?: TxIn["type"] } | null>(null);
  const [byPortfolio, setByPortfolio] = useState(false);
  const [undo, setUndo] = useState<TxRow | null>(null);
  const [showImport, setShowImport] = useState(false);

  const refresh = () => PORTFOLIO_KEYS.forEach((k) => qc.invalidateQueries({ queryKey: k }));
  const del = useMutation({ mutationFn: api.deleteTx, onSuccess: (row) => { setUndo(row); refresh(); } });
  const restore = useMutation({ mutationFn: api.restoreTx, onSuccess: () => { setUndo(null); refresh(); } });

  // a virtual portfolio (or a mix, or a tag group) belongs on the Experiments page
  const byId = new Map((portfolios ?? []).map((p) => [p.id, p]));
  const virtualSel = !isDefaultSel(sel) && portfolios !== undefined
    && ("scope" in sel || sel.tags.length > 0 || sel.ids.some((id) => byId.get(id)?.mode !== "real"));
  if (virtualSel) return <Navigate to={`/experiments?pf=${formatSel(sel)}`} replace />;

  const accounts = (portfolios ?? []).filter((p) => p.mode === "real" && (!p.archived || ("ids" in sel && sel.ids.includes(p.id))));
  const chosen = "ids" in sel && sel.ids.length === 1 ? sel.ids[0] : null;
  const p = pos.data;
  const openForm = (f: { edit: TxRow | null; type?: TxIn["type"] }) => { setForm(f); setTab("transactions"); };
  const counts: Record<Tab, number | null> = { positions: p?.total.length ?? null, transactions: tx.data?.length ?? null,
    imports: null, accounts: accounts.length };

  return (
    <>
      <div className="page-head">
        <h1>Portfolio</h1>
        <div className="note">Your accounts. Their trades are the source of truth: positions, average cost (fees
          included) and returns are worked out from them. Simulations, A/B tests and forks live on{" "}
          <Link to="/experiments">Experiments</Link>. Everything is stored on this computer only.</div>
      </div>
      {portfolios && <AccountsStrip accounts={accounts} sel={sel} onChange={setSel} />}
      {isDefaultSel(sel) && tx.data && portfolios && <MoveFromMain portfolios={portfolios} tx={tx.data} onMoved={refresh} />}

      <Tabs label="Portfolio" value={tab} onChange={setTab} tabs={[
        ["positions", <>Positions{counts.positions != null && <span className="muted"> {counts.positions}</span>}</>],
        ["transactions", <>Transactions{counts.transactions != null && <span className="muted"> {counts.transactions}</span>}</>],
        ["imports", "Imports"],
        ["accounts", <>Accounts<span className="muted"> {counts.accounts}</span></>],
      ]} />

      {tab === "positions" && (
        <section className="group">
          {empty && (
            <div className="card empty-portfolio">
              <h2>No trades yet</h2>
              <p>Add your trades one by one, or import them. Either way you can correct anything later.</p>
              <div className="head-actions">
                <button type="button" className="btn primary" onClick={() => openForm({ edit: null })}>Add your first trade</button>
                <button type="button" className="btn" onClick={() => { setShowImport(true); setTab("imports"); }}>Import from your broker or Yahoo Finance</button>
              </div>
            </div>
          )}
          {p && p.total.length > 0 && (
            <>
              <div className="tab-bar">
                {chosen == null && (
                  <span className="seg small-seg" role="group" aria-label="Positions">
                    <button type="button" aria-pressed={!byPortfolio} onClick={() => setByPortfolio(false)}>Total</button>
                    <button type="button" aria-pressed={byPortfolio} onClick={() => setByPortfolio(true)}>By account</button>
                  </span>
                )}
              </div>
              <div className="card">
                <DataTable id={byPortfolio && chosen == null ? "pp" : "pt"} csvName="positions"
                  rows={byPortfolio && chosen == null ? p.by_portfolio : p.total}
                  cols={posCols(byPortfolio && chosen == null, "Account")} rowKey={(r) => `${r.symbol}|${r.portfolio_id ?? ""}`} />
              </div>
            </>
          )}
          {p && p.cash.some((c) => c.funding === "ledger") && (
            <p className="small">Cash: {p.cash.filter((c) => c.funding === "ledger").map((c, i) => (
              <span key={c.portfolio_id}>{i > 0 && " · "}{c.portfolio} <b>{c.cash_dkk != null ? `${num(c.cash_dkk, 0)} DKK` : "unknown"}</b>
                {c.problems.length > 0 && <span className="warn-text"> ({c.problems[0]})</span>}</span>
            ))}</p>
          )}
          {p && Object.keys(p.warnings).length > 0 && (
            <ul className="small warn-text">{Object.entries(p.warnings).flatMap(([s, ws]) => ws.map((w) => <li key={s + w}><b>{s}</b>: {w}</li>))}</ul>
          )}
          {p && p.total.length > 0 && (
            <p className="small muted">Values use the last traded close in each stock&apos;s own currency. Returns in DKK against
              ACWI: per holding on <Link to="/me">My holdings &amp; watchlist</Link>, per account over time on{" "}
              <Link to={`/returns${isDefaultSel(sel) ? "" : `?pf=${formatSel(sel)}`}`}>Returns</Link>.</p>
          )}
        </section>
      )}

      {tab === "transactions" && (
        <section className="group">
          <div className="tab-bar">
            <button type="button" className="btn primary" onClick={() => setForm({ edit: null })}>Add a trade</button>
            <button type="button" className="btn" onClick={() => setForm({ edit: null, type: "DEPOSIT" })}>Add a cash row</button>
            <a className="btn" href={api.exportUrl(sel)}>Download {isDefaultSel(sel) ? "your" : "these"} transactions (CSV)</a>
          </div>
          {undo && (
            <div className="notes undo" role="status">
              Deleted the {describeTx(undo)}.{" "}
              <button type="button" className="btn small" onClick={() => restore.mutate(undo)} disabled={restore.isPending}>Undo</button>
              <button type="button" className="linkish small" onClick={() => setUndo(null)}>dismiss</button>
            </div>
          )}
          {form && <TxForm key={form.edit?.id ?? `new-${form.type ?? "BUY"}`} edit={form.edit} type={form.type} portfolio={chosen}
            scope="real" onDone={() => setForm(null)} />}
          {empty && !form && <p className="note">No transactions yet. Add one above, or <button type="button" className="linkish"
            onClick={() => { setShowImport(true); setTab("imports"); }}>import a file</button>.</p>}
          {tx.data && tx.data.length > 0 && (
            <div className="card"><DataTable id="tx" csvName="transactions" rows={[...tx.data].reverse()} rowKey={(t) => String(t.id)}
              cols={txCols({ portfolioLabel: "Account", showPortfolio: chosen == null, onEdit: (t) => setForm({ edit: t }),
                onDelete: (t) => del.mutate(t.id), busy: del.isPending })} /></div>
          )}
        </section>
      )}

      {tab === "imports" && (
        <section className="group">
          {showImport
            ? <ImportWizard onDone={() => setShowImport(false)} />
            : (
              <div className="tab-bar">
                <button type="button" className="btn primary" onClick={() => setShowImport(true)}>Import a file…</button>
                <span className="small muted">A broker export (Nordnet, Saxo, Danske Bank) or any spreadsheet; nothing is saved
                  before the last step, and an import can be undone.</span>
              </div>
            )}
          <ImportsList />
        </section>
      )}

      {tab === "accounts" && <section className="group"><AccountsPanel /></section>}
    </>
  );
}

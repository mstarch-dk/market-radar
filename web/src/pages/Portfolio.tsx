import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type PositionRow, type TxRow } from "../api/client";
import { AccountsPanel } from "../components/AccountsPanel";
import { Pct } from "../components/cells";
import { DataTable, type Col } from "../components/DataTable";
import { ImportsList, ImportWizard } from "../components/ImportWizard";
import { TickerLink } from "../components/TickerLink";
import { PORTFOLIO_KEYS, TxForm } from "../components/TxForm";
import { date, num, price } from "../lib/format";

const posCols = (byAccount: boolean): Col<PositionRow>[] => [
  { key: "symbol", label: "Holding", align: "l", sort: (p) => p.name ?? p.symbol, search: (p) => `${p.symbol} ${p.name ?? ""}`,
    csv: (p) => p.symbol, csvHeader: "Ticker", render: (p) => <TickerLink symbol={p.symbol} name={p.name} nameFirst marker={false} /> },
  ...(byAccount ? [{ key: "account", label: "Account", align: "l" as const, sort: (p: PositionRow) => p.account,
    filter: { kind: "enum" as const }, render: (p: PositionRow) => p.account ?? <span className="muted">(none)</span> }] : []),
  { key: "qty", label: "Shares", sort: (p) => p.quantity, render: (p) => num(p.quantity, p.quantity % 1 ? 4 : 0) },
  { key: "avg", label: "Average cost", sort: (p) => p.avg_price, render: (p) => price(p.avg_price, p.currency) },
  { key: "last", label: "Last", sort: (p) => p.last, render: (p) => price(p.last, p.currency) },
  { key: "value", label: "Value", sort: (p) => p.value, render: (p) => price(p.value, p.currency) },
  { key: "unreal", label: "Unrealised", sort: (p) => p.unrealized, render: (p) => <Pct v={p.unrealized} />, heat: true },
  { key: "first", label: "Since", sort: (p) => p.first_trade, render: (p) => date(p.first_trade) },
];

export function Portfolio() {
  const qc = useQueryClient();
  const pos = useQuery({ queryKey: ["positions"], queryFn: api.positions });
  const tx = useQuery({ queryKey: ["transactions"], queryFn: api.transactions });
  const [form, setForm] = useState<{ edit: TxRow | null } | null>(null);
  const [byAccount, setByAccount] = useState(false);
  const [undo, setUndo] = useState<TxRow | null>(null);
  const [showImport, setShowImport] = useState(false);

  const refresh = () => PORTFOLIO_KEYS.forEach((k) => qc.invalidateQueries({ queryKey: k }));
  const del = useMutation({ mutationFn: api.deleteTx, onSuccess: (row) => { setUndo(row); refresh(); } });
  const restore = useMutation({ mutationFn: api.restoreTx, onSuccess: () => { setUndo(null); refresh(); } });

  const txCols: Col<TxRow>[] = [
    { key: "date", label: "Date", align: "l", sort: (t) => t.date, render: (t) => date(t.date) },
    { key: "type", label: "Type", align: "l", sort: (t) => t.type, filter: { kind: "enum" },
      render: (t) => <span className={t.type === "BUY" ? "pos" : "neg"}>{t.type === "BUY" ? "Buy" : "Sell"}</span> },
    { key: "symbol", label: "Ticker", align: "l", sort: (t) => t.symbol, search: (t) => `${t.symbol} ${t.note ?? ""}`,
      filter: { kind: "enum" }, render: (t) => <TickerLink symbol={t.symbol} marker={false} /> },
    { key: "qty", label: "Shares", sort: (t) => t.quantity, render: (t) => num(t.quantity, t.quantity % 1 ? 4 : 0) },
    { key: "price", label: "Price", sort: (t) => t.price, render: (t) => num(t.price, 2) },
    { key: "fee", label: "Fee", sort: (t) => t.fee, render: (t) => (t.fee ? num(t.fee, 2) : <span className="muted">–</span>) },
    { key: "account", label: "Account", align: "l", sort: (t) => t.account, filter: { kind: "enum" },
      render: (t) => t.account ?? <span className="muted">(none)</span> },
    { key: "source", label: "From", align: "l", sort: (t) => t.source, filter: { kind: "enum" }, render: (t) => <span className="muted small">{t.source}</span> },
    { key: "note", label: "Note", align: "l", render: (t) => <span className="muted small">{t.note}</span>, hidden: true },
    { key: "actions", label: "", csv: false, render: (t) => (
      <span className="row-actions">
        <button type="button" className="linkish small" onClick={() => setForm({ edit: t })}>Edit</button>
        <button type="button" className="linkish small neg" disabled={del.isPending}
          onClick={() => { if (window.confirm(`Delete this ${t.type.toLowerCase()} of ${t.quantity} ${t.symbol} on ${t.date}?`)) del.mutate(t.id); }}>
          Delete
        </button>
      </span>
    ) },
  ];

  const p = pos.data;
  const empty = tx.data !== undefined && tx.data.length === 0;
  return (
    <>
      <div className="page-head">
        <h1>Portfolio</h1>
        <div className="note">Your trades are the source of truth: positions, average cost (fees included) and returns are
          worked out from them. Everything is stored on this computer only.</div>
        <div className="head-actions">
          <button type="button" className="btn primary" onClick={() => setForm({ edit: null })}>Add a trade</button>
          <button type="button" className="btn" onClick={() => setShowImport((v) => !v)}>Import…</button>
          <a className="btn" href="/api/portfolio/export.csv">Download all trades (CSV)</a>
        </div>
      </div>

      {undo && (
        <div className="notes undo" role="status">
          Deleted the {undo.type.toLowerCase()} of {undo.quantity} {undo.symbol} on {undo.date}.{" "}
          <button type="button" className="btn small" onClick={() => restore.mutate(undo)} disabled={restore.isPending}>Undo</button>
          <button type="button" className="linkish small" onClick={() => setUndo(null)}>dismiss</button>
        </div>
      )}
      {form && <TxForm edit={form.edit} onDone={() => setForm(null)} />}
      {showImport && <ImportWizard onDone={() => setShowImport(false)} />}

      {empty && !form && (
        <div className="card empty-portfolio">
          <h2>No trades yet</h2>
          <p>Add your trades one by one, or import them. Either way you can correct anything later.</p>
          <div className="head-actions">
            <button type="button" className="btn primary" onClick={() => setForm({ edit: null })}>Add your first trade</button>
            <button type="button" className="btn" onClick={() => setShowImport(true)}>Import from your broker or Yahoo Finance</button>
          </div>
        </div>
      )}

      {p && p.total.length > 0 && (
        <section className="group">
          <h2>Positions <span className="seg small-seg" role="group">
            <button type="button" aria-pressed={!byAccount} onClick={() => setByAccount(false)}>Total</button>
            <button type="button" aria-pressed={byAccount} onClick={() => setByAccount(true)}>By account</button>
          </span></h2>
          <div className="card">
            <DataTable id={byAccount ? "pa" : "pt"} csvName="positions" rows={byAccount ? p.by_account : p.total}
              cols={posCols(byAccount)} rowKey={(r) => `${r.symbol}|${r.account ?? ""}`} />
          </div>
          {Object.keys(p.warnings).length > 0 && (
            <ul className="small warn-text">{Object.entries(p.warnings).flatMap(([s, ws]) => ws.map((w) => <li key={s + w}><b>{s}</b>: {w}</li>))}</ul>
          )}
          <p className="small muted">Values use the last traded close in each stock&apos;s own currency. Returns in DKK against
            ACWI are on <Link to="/me">My holdings &amp; watchlist</Link>.</p>
        </section>
      )}

      {tx.data && tx.data.length > 0 && (
        <section className="group">
          <h2>Trades ({tx.data.length})</h2>
          <div className="card"><DataTable id="tx" csvName="trades" rows={[...tx.data].reverse()} cols={txCols} rowKey={(t) => String(t.id)} /></div>
        </section>
      )}

      <section className="group"><ImportsList /></section>
      <section className="group"><AccountsPanel /></section>
    </>
  );
}

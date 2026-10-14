import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type Portfolio as PortfolioT, type PositionRow, type TxRow } from "../api/client";
import { Pct } from "../components/cells";
import { DataTable, type Col } from "../components/DataTable";
import { ImportsList, ImportWizard } from "../components/ImportWizard";
import { TickerLink } from "../components/TickerLink";
import { PortfolioPicker, usePortfolioSel } from "../components/PortfolioPicker";
import { PortfoliosPanel } from "../components/PortfoliosPanel";
import { PORTFOLIO_KEYS, TxForm } from "../components/TxForm";
import { date, num, price } from "../lib/format";
import { formatSel, isDefaultSel } from "../lib/portfolioSel";

const TYPE_LABEL: Record<TxRow["type"], string> = { BUY: "Buy", SELL: "Sell", DEPOSIT: "Deposit", WITHDRAW: "Withdrawal",
  DIVIDEND: "Dividend", FEE: "Fee", INTEREST: "Interest" };
const IN_TYPES = new Set(["BUY", "DEPOSIT", "DIVIDEND", "INTEREST"]);
const describe = (t: TxRow) => t.quantity != null
  ? `${TYPE_LABEL[t.type].toLowerCase()} of ${t.quantity} ${t.symbol} on ${t.date}`
  : `${TYPE_LABEL[t.type].toLowerCase()} of ${t.amount} ${t.currency ?? "DKK"} on ${t.date}`;

const posCols = (byPortfolio: boolean): Col<PositionRow>[] => [
  { key: "symbol", label: "Holding", align: "l", sort: (p) => p.name ?? p.symbol, search: (p) => `${p.symbol} ${p.name ?? ""}`,
    csv: (p) => p.symbol, csvHeader: "Ticker", render: (p) => <TickerLink symbol={p.symbol} name={p.name} nameFirst marker={false} /> },
  ...(byPortfolio ? [{ key: "portfolio", label: "Portfolio", align: "l" as const, sort: (p: PositionRow) => p.portfolio,
    filter: { kind: "enum" as const }, render: (p: PositionRow) => p.portfolio ?? <span className="muted">–</span> }] : []),
  { key: "qty", label: "Shares", sort: (p) => p.quantity, render: (p) => num(p.quantity, p.quantity % 1 ? 4 : 0) },
  { key: "avg", label: "Average cost", sort: (p) => p.avg_price, render: (p) => price(p.avg_price, p.currency) },
  { key: "last", label: "Last", sort: (p) => p.last, render: (p) => price(p.last, p.currency) },
  { key: "value", label: "Value", sort: (p) => p.value, render: (p) => price(p.value, p.currency) },
  { key: "unreal", label: "Unrealised", sort: (p) => p.unrealized, render: (p) => <Pct v={p.unrealized} />, heat: true },
  { key: "first", label: "Since", sort: (p) => p.first_trade, render: (p) => date(p.first_trade) },
];

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

export function Portfolio() {
  const qc = useQueryClient();
  const [sel, setSel] = usePortfolioSel();
  const key = formatSel(sel);
  const pos = useQuery({ queryKey: ["positions", key], queryFn: () => api.positions(sel) });
  const tx = useQuery({ queryKey: ["transactions", key], queryFn: () => api.transactions(sel) });
  const { data: portfolios = [] } = useQuery({ queryKey: ["portfolios"], queryFn: api.portfolios });
  const [form, setForm] = useState<{ edit: TxRow | null } | null>(null);
  const [byPortfolio, setByPortfolio] = useState(false);
  const [undo, setUndo] = useState<TxRow | null>(null);
  const [showImport, setShowImport] = useState(false);

  const refresh = () => PORTFOLIO_KEYS.forEach((k) => qc.invalidateQueries({ queryKey: k }));
  const chosen = "ids" in sel && sel.ids.length === 1 && sel.tags.length === 0 ? sel.ids[0] : null;
  const del = useMutation({ mutationFn: api.deleteTx, onSuccess: (row) => { setUndo(row); refresh(); } });
  const restore = useMutation({ mutationFn: api.restoreTx, onSuccess: () => { setUndo(null); refresh(); } });

  const txCols: Col<TxRow>[] = [
    { key: "date", label: "Date", align: "l", sort: (t) => t.date, render: (t) => date(t.date) },
    { key: "type", label: "Type", align: "l", sort: (t) => t.type, filter: { kind: "enum" },
      render: (t) => <span className={IN_TYPES.has(t.type) ? "pos" : "neg"}>{TYPE_LABEL[t.type]}</span> },
    { key: "symbol", label: "Ticker", align: "l", sort: (t) => t.symbol, search: (t) => `${t.symbol ?? ""} ${t.note ?? ""}`,
      filter: { kind: "enum" }, render: (t) => (t.symbol ? <TickerLink symbol={t.symbol} marker={false} /> : <span className="muted">–</span>) },
    { key: "qty", label: "Shares", sort: (t) => t.quantity,
      render: (t) => (t.quantity != null ? num(t.quantity, t.quantity % 1 ? 4 : 0) : <span className="muted">–</span>) },
    { key: "price", label: "Price", sort: (t) => t.price ?? t.amount,
      render: (t) => (t.price != null ? num(t.price, 2) : t.amount != null ? `${num(t.amount, 2)} ${t.currency ?? "DKK"}` : "–") },
    { key: "fee", label: "Fee", sort: (t) => t.fee, render: (t) => (t.fee ? num(t.fee, 2) : <span className="muted">–</span>) },
    { key: "portfolio", label: "Portfolio", align: "l", sort: (t) => t.portfolio, filter: { kind: "enum" }, render: (t) => t.portfolio },
    { key: "source", label: "From", align: "l", sort: (t) => t.source, filter: { kind: "enum" }, render: (t) => <span className="muted small">{t.source}</span> },
    { key: "note", label: "Note", align: "l", render: (t) => <span className="muted small">{t.note}</span>, hidden: true },
    { key: "actions", label: "", csv: false, render: (t) => (
      <span className="row-actions">
        <button type="button" className="linkish small" onClick={() => setForm({ edit: t })}>Edit</button>
        <button type="button" className="linkish small neg" disabled={del.isPending}
          onClick={() => { if (window.confirm(`Delete this ${describe(t)}?`)) del.mutate(t.id); }}>
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
          worked out from them, per portfolio. Real portfolios are your accounts; virtual ones (simulations, tests) only
          show when you pick them. Everything is stored on this computer only.</div>
        <div className="head-actions">
          <button type="button" className="btn primary" onClick={() => setForm({ edit: null })}>Add a trade or cash row</button>
          <button type="button" className="btn" onClick={() => setShowImport((v) => !v)}>Import…</button>
          <a className="btn" href={api.exportUrl(sel)}>Download {isDefaultSel(sel) ? "your" : "these"} trades (CSV)</a>
        </div>
        <PortfolioPicker sel={sel} onChange={setSel} />
      </div>
      {isDefaultSel(sel) && tx.data && <MoveFromMain portfolios={portfolios} tx={tx.data} onMoved={refresh} />}

      {undo && (
        <div className="notes undo" role="status">
          Deleted the {describe(undo)}.{" "}
          <button type="button" className="btn small" onClick={() => restore.mutate(undo)} disabled={restore.isPending}>Undo</button>
          <button type="button" className="linkish small" onClick={() => setUndo(null)}>dismiss</button>
        </div>
      )}
      {form && <TxForm edit={form.edit} portfolio={chosen} onDone={() => setForm(null)} />}
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
            <button type="button" aria-pressed={!byPortfolio} onClick={() => setByPortfolio(false)}>Total</button>
            <button type="button" aria-pressed={byPortfolio} onClick={() => setByPortfolio(true)}>By portfolio</button>
          </span></h2>
          <div className="card">
            <DataTable id={byPortfolio ? "pp" : "pt"} csvName="positions" rows={byPortfolio ? p.by_portfolio : p.total}
              cols={posCols(byPortfolio)} rowKey={(r) => `${r.symbol}|${r.portfolio_id ?? ""}`} />
          </div>
          {p.cash.some((c) => c.funding === "ledger") && (
            <p className="small">Cash: {p.cash.filter((c) => c.funding === "ledger").map((c, i) => (
              <span key={c.portfolio_id}>{i > 0 && " · "}{c.portfolio} <b>{c.cash_dkk != null ? `${num(c.cash_dkk, 0)} DKK` : "unknown"}</b>
                {c.problems.length > 0 && <span className="warn-text"> ({c.problems[0]})</span>}</span>
            ))}</p>
          )}
          {Object.keys(p.warnings).length > 0 && (
            <ul className="small warn-text">{Object.entries(p.warnings).flatMap(([s, ws]) => ws.map((w) => <li key={s + w}><b>{s}</b>: {w}</li>))}</ul>
          )}
          <p className="small muted">Values use the last traded close in each stock&apos;s own currency. Returns in DKK against
            ACWI: per holding on <Link to="/me">My holdings &amp; watchlist</Link>, per portfolio over time on{" "}
            <Link to={`/returns${isDefaultSel(sel) ? "" : `?pf=${formatSel(sel)}`}`}>Returns</Link>.</p>
        </section>
      )}

      {tx.data && tx.data.length > 0 && (
        <section className="group">
          <h2>Trades ({tx.data.length})</h2>
          <div className="card"><DataTable id="tx" csvName="trades" rows={[...tx.data].reverse()} cols={txCols} rowKey={(t) => String(t.id)} /></div>
        </section>
      )}

      <section className="group"><ImportsList /></section>
      <section className="group"><PortfoliosPanel /></section>
    </>
  );
}

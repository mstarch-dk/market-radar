import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiError, api, type Issue, type TxIn, type TxRow } from "../api/client";
import { num } from "../lib/format";
import { SymbolPicker } from "./SymbolPicker";

const today = () => new Date().toISOString().slice(0, 10);

export const PORTFOLIO_KEYS = [["transactions"], ["positions"], ["context"], ["me"], ["tickers"], ["profile"], ["portfolios"],
  ["performance"], ["comparison"]];

type TxType = TxIn["type"];
const TYPES: [TxType, string][] = [["BUY", "Buy"], ["SELL", "Sell"], ["DEPOSIT", "Deposit"], ["WITHDRAW", "Withdrawal"],
  ["DIVIDEND", "Dividend"], ["FEE", "Fee"], ["INTEREST", "Interest"]];
const isTrade = (t: TxType) => t === "BUY" || t === "SELL";

/** Add or edit one row: a trade, or a cash row (deposit, withdrawal, dividend, fee, interest; amounts in DKK).
 *  The API checks it while you type (errors block, warnings need a tick) and shows what a trade does to the position
 *  in its portfolio; the price is prefilled with that day's close, in the stock's own currency. `portfolio`
 *  preselects a portfolio for a new row (default: the default portfolio). */
export function TxForm({ edit, portfolio, onDone }: { edit?: TxRow | null; portfolio?: number | null; onDone: () => void }) {
  const qc = useQueryClient();
  const { data: portfolios = [] } = useQuery({ queryKey: ["portfolios"], queryFn: api.portfolios });
  const [tx, setTx] = useState<TxIn>(() => edit
    ? { symbol: edit.symbol ?? "", date: edit.date, type: edit.type, quantity: edit.quantity ?? null, price: edit.price ?? null,
        fee: edit.fee, amount: edit.amount ?? null, currency: edit.currency ?? null, fx_rate: edit.fx_rate ?? null,
        portfolio_id: edit.portfolio_id, note: edit.note ?? null, confirm: false }
    : { symbol: "", date: today(), type: "BUY", quantity: null, price: null, fee: 0, amount: null, fx_rate: null,
        portfolio_id: portfolio ?? null, note: null, confirm: false });
  useEffect(() => {        // a new row goes into the default portfolio unless one is chosen
    if (tx.portfolio_id == null && portfolios.length) {
      const d = portfolios.find((p) => p.is_default) ?? portfolios.find((p) => p.mode === "real" && !p.archived);
      if (d) setTx((t) => ({ ...t, portfolio_id: d.id }));
    }
  }, [portfolios, tx.portfolio_id]);
  const [priceTouched, setPriceTouched] = useState(!!edit);
  const [confirm, setConfirm] = useState(false);
  const set = (patch: Partial<TxIn>) => { setTx((t) => ({ ...t, ...patch })); setConfirm(false); };
  const trade = isTrade(tx.type);
  const needsSymbol = trade || tx.type === "DIVIDEND";
  const pf = portfolios.find((p) => p.id === tx.portfolio_id);

  // that day's close: prefills the price until it is typed in, and shows the currency and the DKK rate
  const pc = useQuery({ queryKey: ["price-check", tx.symbol, tx.date], queryFn: () => api.priceCheck(tx.symbol ?? "", tx.date),
    enabled: trade && !!tx.symbol && !!tx.date, retry: false });
  useEffect(() => {
    if (trade && !priceTouched && pc.data?.close != null) setTx((t) => ({ ...t, price: Math.round(pc.data!.close! * 100) / 100 }));
  }, [pc.data, priceTouched, trade]);

  // live check (debounced)
  const [debounced, setDebounced] = useState(tx);
  useEffect(() => { const h = setTimeout(() => setDebounced(tx), 400); return () => clearTimeout(h); }, [tx]);
  const ready = isTrade(debounced.type)
    ? !!debounced.symbol && (debounced.quantity ?? 0) > 0 && (debounced.price ?? 0) > 0
    : (debounced.amount ?? 0) > 0 && (debounced.type !== "DIVIDEND" || !!debounced.symbol);
  const check = useQuery({ queryKey: ["validate", debounced, edit?.id], queryFn: () => api.validateTx(debounced, edit?.id),
    enabled: ready, retry: false });

  const save = useMutation({
    mutationFn: () => (edit ? api.editTx(edit.id, { ...tx, confirm }) : api.addTx({ ...tx, confirm })),
    onSuccess: () => { PORTFOLIO_KEYS.forEach((k) => qc.invalidateQueries({ queryKey: k })); onDone(); },
  });
  const issues: Issue[] = save.error instanceof ApiError && save.error.issues.length ? save.error.issues : check.data?.issues ?? [];
  const errors = issues.filter((i) => i.level === "error");
  const warnings = issues.filter((i) => i.level === "warning");
  const eff = check.data?.effect;
  const ccy = pc.data?.currency ?? check.data?.price?.currency;
  const fieldIssue = (f: string) => issues.find((i) => i.field === f);
  const n = (v: string) => (v === "" ? null : Number(v));

  return (
    <form className="card tx-form" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <h2>{edit ? `Edit row #${edit.id}` : trade ? "Add a trade" : "Add a cash row"}</h2>
      <div className="tx-grid">
        <label>Type
          <select value={tx.type} onChange={(e) => set({ type: e.target.value as TxType })}>
            <optgroup label="Trade">{TYPES.filter(([t]) => isTrade(t)).map(([t, l]) => <option key={t} value={t}>{l}</option>)}</optgroup>
            <optgroup label="Cash (DKK)">{TYPES.filter(([t]) => !isTrade(t)).map(([t, l]) => <option key={t} value={t}>{l}</option>)}</optgroup>
          </select>
        </label>
        {needsSymbol && <label className="wide">Ticker<SymbolPicker value={tx.symbol ?? ""} onChange={(s) => set({ symbol: s })} autoFocus={!edit} /></label>}
        <label>Date<input type="date" value={tx.date} max={today()} onChange={(e) => set({ date: e.target.value })} /></label>
        {trade ? (
          <>
            <label>Quantity<input type="number" min="0" step="any" value={tx.quantity ?? ""} onChange={(e) => set({ quantity: n(e.target.value) })}
              className={fieldIssue("quantity") ? "bad" : ""} /></label>
            <label>Price per share {ccy && <span className="muted">({ccy})</span>}
              <input type="number" min="0" step="any" value={tx.price ?? ""} className={fieldIssue("price") ? "bad" : ""}
                onChange={(e) => { setPriceTouched(true); set({ price: n(e.target.value) }); }} />
              {pc.data?.close != null && <span className="hint">close {pc.data.close_date}: {num(pc.data.close, 2)} {ccy}</span>}
            </label>
            <label>Fee {ccy && <span className="muted">({ccy})</span>}<input type="number" min="0" step="any" value={tx.fee || ""}
              onChange={(e) => set({ fee: Number(e.target.value) })} /></label>
            {ccy && ccy !== "DKK" && (
              <label>DKK per {ccy === "GBp" ? "penny" : ccy} <span className="muted">(optional)</span>
                <input type="number" min="0" step="any" value={tx.fx_rate ?? ""} className={fieldIssue("fx_rate") ? "bad" : ""}
                  placeholder={pc.data?.fx != null ? num(pc.data.fx, 4) : "no rate"} onChange={(e) => set({ fx_rate: n(e.target.value) })} />
                <span className="hint">the rate you traded at; empty: Yahoo&apos;s rate that day</span>
              </label>
            )}
          </>
        ) : (
          <label>Amount <span className="muted">(DKK)</span>
            <input type="number" min="0" step="any" value={tx.amount ?? ""} className={fieldIssue("amount") ? "bad" : ""}
              onChange={(e) => set({ amount: n(e.target.value), currency: "DKK" })} />
          </label>
        )}
        <label>Portfolio
          <select value={tx.portfolio_id ?? ""} onChange={(e) => set({ portfolio_id: e.target.value ? Number(e.target.value) : null })}
            className={fieldIssue("portfolio") ? "bad" : ""}>
            {tx.portfolio_id == null && <option value="">(the default: Main)</option>}
            {portfolios.filter((p) => !p.archived || p.id === tx.portfolio_id).map((p) => (
              <option key={p.id} value={p.id}>{p.name}{p.mode === "virtual" ? " (virtual)" : ""}</option>
            ))}
          </select>
          {pf?.mode === "virtual" && <span className="hint">virtual: it can only spend what was deposited</span>}
        </label>
        <label className="wide">Note<input value={tx.note ?? ""} onChange={(e) => set({ note: e.target.value || null })} placeholder="optional" /></label>
      </div>

      {eff && eff.before && eff.after && (
        <p className="small effect">
          {eff.symbol}: {num(eff.before.quantity, 0)} → <b>{num(eff.after.quantity, 0)}</b> shares
          {eff.after.avg_price != null && <>, average cost {num(eff.before.avg_price, 2)} → <b>{num(eff.after.avg_price, 2)}</b> {ccy}</>}
        </p>
      )}
      {errors.map((i) => <p key={i.message} className="small neg">✗ {i.message}</p>)}
      {warnings.map((i) => <p key={i.message} className="small warn-text">⚠ {i.message}</p>)}
      {warnings.length > 0 && errors.length === 0 && (
        <label className="small confirm"><input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} />
          I checked this; save anyway</label>
      )}
      {save.isError && !(save.error instanceof ApiError && save.error.issues.length) && <p className="small neg">{save.error.message}</p>}
      <div className="tx-actions">
        <button type="submit" className="btn primary" disabled={save.isPending || errors.length > 0 || (warnings.length > 0 && !confirm) || !ready}>
          {save.isPending ? "Saving…" : edit ? "Save changes" : trade ? "Add trade" : "Add row"}
        </button>
        <button type="button" className="btn" onClick={onDone}>Cancel</button>
      </div>
    </form>
  );
}

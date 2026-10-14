import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiError, api, type Issue, type TxIn, type TxRow } from "../api/client";
import { num } from "../lib/format";
import { SymbolPicker } from "./SymbolPicker";

const today = () => new Date().toISOString().slice(0, 10);

export const PORTFOLIO_KEYS = [["transactions"], ["positions"], ["context"], ["me"], ["tickers"], ["profile"]];

/** Add or edit one trade. The API checks it while you type (errors block, warnings need a tick) and shows what it
 *  does to the position; the price is prefilled with that day's close, in the stock's own currency. */
export function TxForm({ edit, onDone }: { edit?: TxRow | null; onDone: () => void }) {
  const qc = useQueryClient();
  const { data: accounts = [] } = useQuery({ queryKey: ["accounts"], queryFn: api.accounts });
  const [tx, setTx] = useState<TxIn>(() => edit
    ? { symbol: edit.symbol, date: edit.date, type: edit.type, quantity: edit.quantity, price: edit.price, fee: edit.fee,
        account: edit.account ?? null, note: edit.note ?? null, confirm: false }
    : { symbol: "", date: today(), type: "BUY", quantity: 0, price: 0, fee: 0, account: null, note: null, confirm: false });
  const [priceTouched, setPriceTouched] = useState(!!edit);
  const [confirm, setConfirm] = useState(false);
  const set = (patch: Partial<TxIn>) => { setTx((t) => ({ ...t, ...patch })); setConfirm(false); };

  // that day's close: prefills the price until it is typed in, and shows the currency
  const pc = useQuery({ queryKey: ["price-check", tx.symbol, tx.date], queryFn: () => api.priceCheck(tx.symbol, tx.date),
    enabled: !!tx.symbol && !!tx.date, retry: false });
  useEffect(() => {
    if (!priceTouched && pc.data?.close != null) setTx((t) => ({ ...t, price: Math.round(pc.data!.close! * 100) / 100 }));
  }, [pc.data, priceTouched]);

  // live check (debounced)
  const [debounced, setDebounced] = useState(tx);
  useEffect(() => { const h = setTimeout(() => setDebounced(tx), 400); return () => clearTimeout(h); }, [tx]);
  const ready = !!debounced.symbol && debounced.quantity > 0 && debounced.price > 0;
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

  return (
    <form className="card tx-form" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <h2>{edit ? `Edit trade #${edit.id}` : "Add a trade"}</h2>
      <div className="tx-grid">
        <label className="wide">Ticker<SymbolPicker value={tx.symbol} onChange={(s) => set({ symbol: s })} autoFocus={!edit} /></label>
        <label>Date<input type="date" value={tx.date} max={today()} onChange={(e) => set({ date: e.target.value })} /></label>
        <label>Type
          <div className="seg" role="group">
            {(["BUY", "SELL"] as const).map((t) => (
              <button key={t} type="button" aria-pressed={tx.type === t} onClick={() => set({ type: t })}>{t === "BUY" ? "Buy" : "Sell"}</button>
            ))}
          </div>
        </label>
        <label>Quantity<input type="number" min="0" step="any" value={tx.quantity || ""} onChange={(e) => set({ quantity: Number(e.target.value) })}
          className={fieldIssue("quantity") ? "bad" : ""} /></label>
        <label>Price per share {ccy && <span className="muted">({ccy})</span>}
          <input type="number" min="0" step="any" value={tx.price || ""} className={fieldIssue("price") ? "bad" : ""}
            onChange={(e) => { setPriceTouched(true); set({ price: Number(e.target.value) }); }} />
          {pc.data?.close != null && <span className="hint">close {pc.data.close_date}: {num(pc.data.close, 2)} {ccy}</span>}
        </label>
        <label>Fee {ccy && <span className="muted">({ccy})</span>}<input type="number" min="0" step="any" value={tx.fee || ""}
          onChange={(e) => set({ fee: Number(e.target.value) })} /></label>
        <label>Account
          <select value={tx.account ?? ""} onChange={(e) => set({ account: e.target.value || null })}>
            <option value="">(none)</option>
            {accounts.map((a) => <option key={a.name} value={a.name}>{a.name}</option>)}
          </select>
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
          {save.isPending ? "Saving…" : edit ? "Save changes" : "Add trade"}
        </button>
        <button type="button" className="btn" onClick={onDone}>Cancel</button>
      </div>
    </form>
  );
}

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, type FeeRule, type FeeSchedule, type Portfolio } from "../api/client";
import { usePortfolioActions } from "./PortfoliosPanel";

const MARKETS: [FeeRule["market"], string][] = [["DK", "Denmark"], ["NORDIC", "Nordic"], ["US", "USA"], ["EU", "Europe"],
  ["UK", "UK"], ["OTHER", "Other markets"]];

/** One line: the schedule's preset and date, "custom", or "none". */
export function feeSummary(s: FeeSchedule | null | undefined): string {
  if (!s) return "none";
  return `${s.preset ?? "custom"}${s.as_of ? ` (${s.as_of})` : ""}`;
}

const n = (v: string) => (v.trim() === "" ? null : Number(v));

/** Edit an account's broker fee schedule: start from a preset (a broker's public price list, dated) or from scratch,
 *  then adjust each market's percentage, minimum and maximum. */
export function FeeScheduleEditor({ portfolio, onDone }: { portfolio: Portfolio; onDone: () => void }) {
  const { data: presets = [] } = useQuery({ queryKey: ["fee-presets"], queryFn: api.feePresets, staleTime: Infinity });
  const a = usePortfolioActions();
  const [s, setS] = useState<FeeSchedule>(portfolio.fee_schedule ?? { markets: [], preset: null, as_of: null, fx_pct: null, note: null });
  const preset = presets.find((p) => p.id === s.preset);
  const edited = (patch: Partial<FeeSchedule>) => setS((x) => ({ ...x, ...patch }));
  const setRule = (i: number, patch: Partial<FeeRule>) =>
    edited({ markets: s.markets.map((r, j) => (j === i ? { ...r, ...patch } : r)) });
  const unused = MARKETS.filter(([m]) => !s.markets.some((r) => r.market === m));
  const save = (schedule: FeeSchedule | null) => a.save(portfolio, { fee_schedule: schedule }, onDone);

  return (
    <div className="fee-editor">
      <label className="small">Start from
        <select value="" onChange={(e) => {
          const p = presets.find((x) => x.id === e.target.value);
          if (p) setS({ ...p.schedule, preset: p.id, as_of: p.as_of });
        }} aria-label="Fee preset">
          <option value="">choose a broker…</option>
          {presets.map((p) => <option key={p.id} value={p.id}>{p.label} (price list {p.as_of})</option>)}
        </select>
      </label>
      {preset && (
        <p className="small muted">From {preset.label}&apos;s price list as of {preset.as_of} (<a href={preset.source_url}
          target="_blank" rel="noreferrer">source</a>). {preset.note} Check it against your broker&apos;s current price list.</p>
      )}
      <table className="t fee-rules">
        <thead><tr><th className="l">Market</th><th>% of value</th><th>Minimum</th><th>Maximum</th><th className="l">in</th><th /></tr></thead>
        <tbody>
          {s.markets.map((r, i) => (
            <tr key={r.market}>
              <td className="l">{MARKETS.find(([m]) => m === r.market)?.[1]}</td>
              <td><input type="number" min="0" step="any" value={r.pct} aria-label={`${r.market} percent`}
                onChange={(e) => setRule(i, { pct: Number(e.target.value) })} /></td>
              <td><input type="number" min="0" step="any" value={r.min ?? ""} aria-label={`${r.market} minimum`}
                onChange={(e) => setRule(i, { min: n(e.target.value) })} /></td>
              <td><input type="number" min="0" step="any" value={r.max ?? ""} placeholder="none" aria-label={`${r.market} maximum`}
                onChange={(e) => setRule(i, { max: n(e.target.value) })} /></td>
              <td className="l"><input className="ccy" value={r.currency ?? "DKK"} maxLength={3} aria-label={`${r.market} currency`}
                onChange={(e) => setRule(i, { currency: e.target.value.toUpperCase() })} /></td>
              <td><button type="button" className="linkish small neg" onClick={() => edited({ markets: s.markets.filter((_, j) => j !== i) })}
                aria-label={`Remove ${r.market}`}>×</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {unused.length > 0 && (
        <select value="" className="small" aria-label="Add a market" onChange={(e) => {
          const m = e.target.value as FeeRule["market"];
          if (m) edited({ markets: [...s.markets, { market: m, pct: 0, min: null, max: null, currency: "DKK" }] });
        }}>
          <option value="">+ a market…</option>
          {unused.map(([m, l]) => <option key={m} value={m}>{l}</option>)}
        </select>
      )}
      <p className="small">
        <label>Currency exchange surcharge <input type="number" min="0" step="any" value={s.fx_pct ?? ""} className="pct"
          onChange={(e) => edited({ fx_pct: n(e.target.value) })} aria-label="FX surcharge percent" /> %</label>{" "}
        <span className="muted">shown next to the estimate, not added to it: when you enter the rate you traded at, the
          broker&apos;s spread is already in it.</span>
      </p>
      <p className="small muted">A market without a rule uses &quot;Other markets&quot;; without either, no fee is estimated.</p>
      {a.error && <p className="small neg">{a.error.message}</p>}
      <div className="tx-actions">
        <button type="button" className="btn primary small" disabled={a.saving}
          onClick={() => save(s.markets.length ? s : null)}>Save fees</button>
        {portfolio.fee_schedule && <button type="button" className="btn small" onClick={() => save(null)}>Remove the schedule</button>}
        <button type="button" className="btn small" onClick={onDone}>Cancel</button>
      </div>
    </div>
  );
}

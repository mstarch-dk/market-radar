import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";
import { api } from "../api/client";

/** Import a Yahoo Finance portfolio export (CSV) from the browser: holdings, sold positions and watchlist. */
export function ImportPortfolio() {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const m = useMutation({
    mutationFn: async (file: File) => api.importPortfolio(await file.text()),
    onSuccess: () => qc.invalidateQueries(),
  });
  const r = m.data;
  return (
    <div className="card import-card">
      <h2>Import your portfolio from Yahoo Finance</h2>
      <ol className="small">
        <li>On <a href="https://finance.yahoo.com/portfolios" target="_blank" rel="noreferrer">finance.yahoo.com/portfolios</a>,
          open your portfolio and choose <b>Export</b>. This saves a file called something like <code>quotes.csv</code>.</li>
        <li>Click the button below and pick that file. It stays on this computer.</li>
      </ol>
      <input ref={input} type="file" accept=".csv,text/csv" hidden
        onChange={(e) => { const f = e.target.files?.[0]; if (f) m.mutate(f); e.target.value = ""; }} />
      <button type="button" className="btn primary" disabled={m.isPending} onClick={() => input.current?.click()}>
        {m.isPending ? "Importing…" : "Choose the exported CSV file"}
      </button>
      {m.isError && <p className="small neg">{m.error.message}</p>}
      {r && (
        <div className="small">
          <p className="pos">Imported {r.holdings} holdings, {r.sold} sold positions and {r.watch} watchlist names.
            Prices for new names are fetched at the next data update.</p>
          {Object.keys(r.warnings).length > 0 && (
            <ul className="muted">{Object.entries(r.warnings).flatMap(([sym, ws]) => ws.map((w) => <li key={sym + w}><b>{sym}</b>: {w}</li>))}</ul>
          )}
        </div>
      )}
      <p className="small muted">Importing again replaces the previous import. Watchlist changes you made in this app are kept.</p>
    </div>
  );
}

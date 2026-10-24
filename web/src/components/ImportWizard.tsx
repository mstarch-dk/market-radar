import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api, type ImportParams, type ImportRow } from "../api/client";
import { date, num } from "../lib/format";
import { DataTable, type Col } from "./DataTable";
import { PORTFOLIO_KEYS } from "./TxForm";
import { Badge } from "./ui";

const FIELDS: [string, string][] = [["date", "Date"], ["type", "Buy/sell"], ["symbol", "Symbol"], ["isin", "ISIN"],
  ["name", "Name"], ["quantity", "Quantity"], ["price", "Price"], ["fee", "Fee"], ["currency", "Currency"],
  ["account", "Account (→ portfolio)"], ["ext_ref", "Trade ID"], ["cash_amount", "Cash amount (DKK)"]];

function status(r: ImportRow) {
  if (r.skip) return <span className="muted small">skipped: {r.skip}</span>;
  if (r.duplicate) return <span className="muted small">already stored</span>;
  const e = r.issues.find((i) => i.level === "error");
  if (e) return <span className="neg small">✗ {e.message}</span>;
  const w = r.issues.find((i) => i.level === "warning");
  if (w) return <span className="warn-text small">⚠ {w.message}</span>;
  return <span className="pos small">new</span>;
}

const rowCols: Col<ImportRow>[] = [
  { key: "row", label: "Line", sort: (r) => r.row, render: (r) => r.row },
  { key: "date", label: "Date", align: "l", sort: (r) => r.date, render: (r) => date(r.date) },
  { key: "type", label: "Type", align: "l", sort: (r) => r.type, render: (r) => r.type ?? "–" },
  { key: "ident", label: "In the file", align: "l", sort: (r) => r.ident, search: (r) => `${r.ident} ${r.symbol ?? ""}`,
    render: (r) => <span className="small">{r.ident}</span> },
  { key: "symbol", label: "Symbol", align: "l", sort: (r) => r.symbol, render: (r) => r.symbol ?? "–" },
  { key: "qty", label: "Shares", sort: (r) => r.quantity, render: (r) => num(r.quantity, r.quantity && r.quantity % 1 ? 4 : 0) },
  { key: "price", label: "Price / amount", sort: (r) => r.price ?? r.amount,
    render: (r) => (r.price != null ? num(r.price, 2) : r.amount != null ? `${num(r.amount, 2)} DKK` : "–") },
  { key: "fee", label: "Fee", sort: (r) => r.fee, render: (r) => (r.fee ? num(r.fee, 2) : "–") },
  { key: "portfolio", label: "Portfolio", align: "l", sort: (r) => r.portfolio, render: (r) => r.portfolio ?? <span className="muted">the chosen one</span> },
  { key: "status", label: "Will be", align: "l", render: status,
    sort: (r) => (r.skip ? 4 : r.duplicate ? 3 : r.issues.some((i) => i.level === "error") ? 0 : r.issues.length ? 1 : 2),
    filter: { kind: "enum", value: (r) => (r.skip ? "skipped" : r.duplicate ? "already stored"
      : r.issues.some((i) => i.level === "error") ? "error" : r.issues.length ? "warning" : "new") } },
];

/** Import trades from a broker export or any spreadsheet: pick the file → check the columns → confirm the
 *  symbols → review every row → import. Nothing is saved before the last step, and an import can be undone. */
export function ImportWizard({ onDone }: { onDone?: () => void }) {
  const qc = useQueryClient();
  const [file, setFile] = useState<{ name: string; data: ArrayBuffer } | null>(null);
  const [paste, setPaste] = useState("");
  const [preset, setPreset] = useState("");
  const [portfolio, setPortfolio] = useState<number | undefined>();
  const [mapping, setMapping] = useState<Record<string, string> | undefined>();
  const [symbols, setSymbols] = useState<Record<string, string>>({});
  const [confirm, setConfirm] = useState(false);
  const [checkedSymbols, setCheckedSymbols] = useState(false);
  const { data: presets = [] } = useQuery({ queryKey: ["import-presets"], queryFn: api.importPresets });
  const { data: portfolios = [] } = useQuery({ queryKey: ["portfolios"], queryFn: api.portfolios });

  const params: ImportParams = { filename: file?.name ?? "pasted.csv", preset: preset || undefined, portfolio, mapping, symbols };
  const pv = useQuery({
    queryKey: ["import-preview", file?.name, file?.data.byteLength, preset, portfolio, mapping, symbols],
    queryFn: () => api.importPreview(file!.data, params), enabled: !!file, retry: false,
  });
  const commit = useMutation({
    mutationFn: () => api.importCommit(file!.data, { ...params, confirm }),
    onSuccess: () => { PORTFOLIO_KEYS.concat([["imports"]]).forEach((k) => qc.invalidateQueries({ queryKey: k })); },
  });

  const reset = () => { setFile(null); setMapping(undefined); setSymbols({}); setConfirm(false); setCheckedSymbols(false); commit.reset(); };
  const load = async (f: File) => { reset(); setFile({ name: f.name, data: await f.arrayBuffer() }); };
  const usePaste = () => { reset(); setFile({ name: "pasted.csv", data: new TextEncoder().encode(paste).buffer as ArrayBuffer }); };

  const p = pv.data;
  const uncertain = p?.symbols.filter((m) => !m.certain) ?? [];
  const c = p?.counts;
  const canCommit = !!p && c!.errors === 0 && c!.new > 0 && (c!.warnings === 0 || confirm) && (uncertain.length === 0 || checkedSymbols);

  if (commit.data) {
    return (
      <div className="card wizard">
        <h2>Imported</h2>
        <p className="pos">{commit.data.added} trades added{commit.data.skipped ? `, ${commit.data.skipped} already stored` : ""}
          {commit.data.replaced ? ` (replacing ${commit.data.replaced} from the previous ${commit.data.source} import)` : ""}.</p>
        <p className="small muted">You can undo the whole import under "Past imports".</p>
        <div className="tx-actions"><button className="btn" type="button" onClick={reset}>Import another file</button>
          {onDone && <button className="btn" type="button" onClick={onDone}>Close</button>}</div>
      </div>
    );
  }

  return (
    <div className="card wizard">
      <h2>Import trades</h2>
      <ol className="steps small">
        <li className={!file ? "on" : ""}>Choose a file</li><li className={file && !p ? "on" : ""}>Check the columns</li>
        <li className={p && uncertain.length ? "on" : ""}>Confirm the symbols</li><li className={p && !uncertain.length ? "on" : ""}>Review and import</li>
      </ol>

      <div className="wiz-row">
        <label className="btn primary file-btn">Choose a file (CSV or Excel)
          <input type="file" accept=".csv,.txt,.tsv,.xlsx,text/csv" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) void load(f); e.target.value = ""; }} />
        </label>
        <span className="small muted">From Saxo, Nordnet, Danske Bank, Yahoo Finance, or any spreadsheet with dates, quantities and prices.</span>
      </div>
      <details className="small">
        <summary>…or paste rows from a spreadsheet</summary>
        <textarea rows={5} value={paste} onChange={(e) => setPaste(e.target.value)} placeholder={"Date;Type;Symbol;Quantity;Price\n05-01-2026;Buy;NOVO-B.CO;10;612,40"} />
        <button type="button" className="btn small" disabled={!paste.trim()} onClick={usePaste}>Use these rows</button>
      </details>

      {file && (
        <div className="wiz-row">
          <span className="small"><b>{file.name}</b></span>
          <label className="small">Format
            <select value={preset} onChange={(e) => { setPreset(e.target.value); setMapping(undefined); }}>
              <option value="">detect</option>
              {presets.map((x) => <option key={x.key} value={x.key}>{x.label}{x.verified ? "" : " (unverified)"}</option>)}
            </select>
          </label>
          <label className="small">Into portfolio
            <select value={portfolio ?? ""} onChange={(e) => setPortfolio(e.target.value ? Number(e.target.value) : undefined)}>
              <option value="">the default{(() => { const d = portfolios.find((x) => x.is_default); return d ? ` (${d.name})` : ""; })()}</option>
              {portfolios.filter((x) => !x.archived).map((x) => (
                <option key={x.id} value={x.id}>{x.name}{x.mode === "virtual" ? " (virtual)" : ""}</option>
              ))}
            </select>
          </label>
        </div>
      )}
      {pv.isPending && file && <p className="small muted">Reading the file and matching symbols…</p>}
      {pv.isError && <p className="neg small">{pv.error instanceof ApiError ? pv.error.message : String(pv.error)}</p>}

      {p && (
        <>
          <h3>Columns {p.preset_label ? <>— recognised as <b>{p.preset_label}</b>{p.verified === false && <Badge kind="warn">unverified format: check the rows below</Badge>}</>
            : <span className="muted">— no known format; pick which column is which</span>}</h3>
          <div className="mapping">
            {FIELDS.map(([f, label]) => (
              <label key={f} className="small">{label}
                <select value={p.mapping[f] ?? ""} onChange={(e) => {
                  const m = { ...p.mapping };
                  if (e.target.value) m[f] = e.target.value; else delete m[f];
                  setMapping(m);
                }}>
                  <option value="">—</option>
                  {p.columns.map((col) => <option key={col} value={col}>{col}</option>)}
                </select>
              </label>
            ))}
          </div>

          {p.symbols.length > 0 && (
            <>
              <h3>Symbols ({p.symbols.length})</h3>
              <table className="t dt symbols">
                <thead><tr><th className="l">In the file</th><th className="l">Yahoo symbol</th><th className="l">Found by</th></tr></thead>
                <tbody>
                  {p.symbols.map((m) => {
                    const how = m.candidates.find((x) => x.symbol === m.chosen)?.how;
                    return (
                      <tr key={m.ident}>
                        <td className="l">{m.ident}{m.name && m.name !== m.ident && <div className="muted small">{m.name}</div>}</td>
                        <td className="l">
                          <select value={m.chosen ?? ""} onChange={(e) => setSymbols({ ...symbols, [m.ident]: e.target.value })}>
                            {!m.chosen && <option value="">choose…</option>}
                            {m.candidates.map((x) => <option key={x.symbol} value={x.symbol}>{x.symbol}{x.exchange ? ` (${x.exchange})` : ""}{x.name ? ` – ${x.name}` : ""}</option>)}
                            {m.chosen && !m.candidates.some((x) => x.symbol === m.chosen) && <option value={m.chosen}>{m.chosen}</option>}
                          </select>
                          <button type="button" className="linkish small" onClick={() => {
                            const s = window.prompt(`Yahoo symbol for ${m.ident} (e.g. NOVO-B.CO):`, m.chosen ?? "")?.trim().toUpperCase();
                            if (s) setSymbols({ ...symbols, [m.ident]: s });
                          }}>other…</button>
                        </td>
                        <td className="l small">{m.certain ? <span className="pos">{how ?? "chosen"}</span> : <span className="warn-text">{how ? `${how}: please check` : m.search_failed ? "Yahoo search failed: choose by hand" : "not found"}</span>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </>
          )}

          <h3>Rows</h3>
          <p className="small">{c!.new} new · {c!.duplicates} already stored · {c!.skipped} skipped
            {c!.errors > 0 && <span className="neg"> · {c!.errors} with errors</span>}
            {c!.warnings > 0 && <span className="warn-text"> · {c!.warnings} with warnings</span>}
            {p.snapshot && <span className="muted"> · this export replaces your previous {p.preset_label} import into this portfolio</span>}</p>
          {p.new_portfolios.length > 0 && (
            <p className="small warn-text">The file names {p.new_portfolios.length === 1 ? "a portfolio" : "portfolios"} you don&apos;t have yet:{" "}
              <b>{p.new_portfolios.join(", ")}</b>. {p.new_portfolios.length === 1 ? "It is" : "They are"} created as real portfolios on import
              (rename one to match your account, or map the account column to nothing to import into the chosen portfolio).</p>
          )}
          <div className="card inner"><DataTable id="imp" rows={p.rows} cols={rowCols} rowKey={(r) => String(r.row)} /></div>

          {uncertain.length > 0 && (
            <label className="small confirm"><input type="checkbox" checked={checkedSymbols} onChange={(e) => setCheckedSymbols(e.target.checked)} />
              I checked the {uncertain.length} symbol match{uncertain.length > 1 ? "es" : ""} marked "please check"</label>
          )}
          {c!.warnings > 0 && c!.errors === 0 && (
            <label className="small confirm"><input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} />
              I checked the rows with warnings; import them anyway</label>
          )}
          {commit.isError && <p className="neg small">{commit.error.message}</p>}
          <div className="tx-actions">
            <button type="button" className="btn primary" disabled={!canCommit || commit.isPending} onClick={() => commit.mutate()}>
              {commit.isPending ? "Importing…" : `Import ${c!.new} trade${c!.new === 1 ? "" : "s"}`}
            </button>
            <button type="button" className="btn" onClick={() => { reset(); onDone?.(); }}>Cancel</button>
          </div>
        </>
      )}
    </div>
  );
}

/** Past imports, with Undo (removes everything an import added; a backup of the database is kept). */
export function ImportsList() {
  const qc = useQueryClient();
  const { data = [] } = useQuery({ queryKey: ["imports"], queryFn: api.imports });
  const undo = useMutation({ mutationFn: api.undoImport,
    onSuccess: () => PORTFOLIO_KEYS.concat([["imports"]]).forEach((k) => qc.invalidateQueries({ queryKey: k })) });
  if (!data.length) return null;
  return (
    <div className="card">
      <h2 className="plain">Past imports</h2>
      <table className="t">
        <thead><tr><th className="l">When</th><th className="l">From</th><th className="l">File</th><th>Added</th><th>Still stored</th><th /></tr></thead>
        <tbody>
          {data.map((i) => (
            <tr key={i.id}>
              <td className="l">{i.at.replace("T", " ").slice(0, 16)}</td><td className="l">{i.source}</td>
              <td className="l small">{i.file_name ?? "–"}</td><td>{i.rows_added}</td><td>{i.rows_now}</td>
              <td>{(i.rows_replaced ?? 0) > 0
                ? <span className="muted small" title={`Undo can't bring back the ${i.rows_replaced} rows this import replaced. Restore the copy taken before it: ${i.backup ?? "backups/"} (in backups/ in the data folder).`}>
                    replaced {i.rows_replaced}: restore {i.backup ? "its backup" : "a backup"}</span>
                : i.rows_now > 0 && <button type="button" className="linkish small neg" disabled={undo.isPending}
                onClick={() => { if (window.confirm(`Undo this import? Its ${i.rows_now} trades will be removed (a backup is kept).`)) undo.mutate(i.id); }}>Undo</button>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {undo.error && <p className="error">{undo.error.message}</p>}
    </div>
  );
}

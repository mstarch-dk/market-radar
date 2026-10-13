import { useEffect, useState } from "react";
import {
  activeFilters, enumOptions, filterRows, sortRows, toCsv, type Filter, type TableState,
} from "../lib/tableState";
import { useHiddenColumns, useTableState } from "../lib/useTableState";
import { colName, defaultHidden, type Col } from "./columns";
import { Popover } from "./Popover";

const fmtBound = (v: number | undefined, unit?: string) =>
  v === undefined ? "" : unit === "pct" ? `${+(v * 100).toFixed(2)}%` : `${+v.toFixed(2)}`;

function summary(f: Filter | undefined, unit?: string): string {
  if (!f) return "";
  if (f.kind === "enum") return f.values.length === 1 ? f.values[0]! : `${f.values.length} selected`;
  if (f.kind === "bool") return f.value ? "yes" : "no";
  if (f.min !== undefined && f.max !== undefined) return `${fmtBound(f.min, unit)} – ${fmtBound(f.max, unit)}`;
  return f.min !== undefined ? `≥ ${fmtBound(f.min, unit)}` : `≤ ${fmtBound(f.max, unit)}`;
}

function EnumEditor<T>({ rows, col, f, set }: { rows: T[]; col: Col<T>; f?: Filter; set: (f?: Filter) => void }) {
  const chosen = new Set(f?.kind === "enum" ? f.values : []);
  const opts = enumOptions(rows, col);
  const toggle = (v: string) => {
    const next = new Set(chosen);
    if (next.has(v)) next.delete(v); else next.add(v);
    set(next.size ? { kind: "enum", values: [...next] } : undefined);
  };
  return (
    <div className="enum-list">
      {opts.length === 0 && <p className="muted small">No values.</p>}
      {opts.map((o) => (
        <label key={o.value}>
          <input type="checkbox" checked={chosen.has(o.value)} onChange={() => toggle(o.value)} />
          <span>{o.value}</span><span className="muted small">{o.count}</span>
        </label>
      ))}
    </div>
  );
}

function BoolEditor({ f, set }: { f?: Filter; set: (f?: Filter) => void }) {
  const cur = f?.kind === "bool" ? (f.value ? "yes" : "no") : "any";
  return (
    <div className="seg" role="group">
      {(["any", "yes", "no"] as const).map((v) => (
        <button key={v} type="button" aria-pressed={cur === v}
          onClick={() => set(v === "any" ? undefined : { kind: "bool", value: v === "yes" })}>
          {v === "any" ? "Any" : v === "yes" ? "✓ Yes" : "✗ No"}
        </button>
      ))}
    </div>
  );
}

function RangeEditor({ f, unit, set, close }: { f?: Filter; unit?: string; set: (f?: Filter) => void; close: () => void }) {
  const k = unit === "pct" ? 100 : 1;
  const r = f?.kind === "range" ? f : undefined;
  const show = (v?: number) => (v === undefined ? "" : String(+(v * k).toFixed(4)));
  const [lo, setLo] = useState(show(r?.min));
  const [hi, setHi] = useState(show(r?.max));
  const apply = () => {
    const parse = (s: string) => (s.trim() === "" || !Number.isFinite(Number(s)) ? undefined : Number(s) / k);
    const min = parse(lo), max = parse(hi);
    set(min === undefined && max === undefined ? undefined : { kind: "range", min, max });
    close();
  };
  return (
    <form className="range-form" onSubmit={(e) => { e.preventDefault(); apply(); }}>
      <label>Min<input inputMode="decimal" value={lo} onChange={(e) => setLo(e.target.value)} placeholder="any" />{unit === "pct" && "%"}</label>
      <label>Max<input inputMode="decimal" value={hi} onChange={(e) => setHi(e.target.value)} placeholder="any" />{unit === "pct" && "%"}</label>
      <button type="submit" className="btn primary small">Apply</button>
      <p className="muted small">Rows without a value are left out while this filter is on.</p>
    </form>
  );
}

/** Search, filter chips, row count, column picker and CSV export for one table (or a group sharing an `id`). */
export function TableToolbar<T>({ id, rows, cols, csvName }: { id: string; rows: T[]; cols: Col<T>[]; csvName?: string }) {
  const [state, setState] = useTableState(id);
  const [hidden, toggleCol, resetCols] = useHiddenColumns(id, defaultHidden(cols));
  const [q, setQ] = useState(state.q);
  useEffect(() => {
    setQ(state.q);
  }, [state.q]);
  useEffect(() => {                                   // write the search to the URL once typing pauses
    if (q === state.q) return;
    const t = setTimeout(() => setState({ ...state, q }), 200);
    return () => clearTimeout(t);
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  const { rows: kept, missing } = filterRows(rows, cols, state);
  const setFilter = (key: string, f?: Filter) => {
    const filters = { ...state.filters };
    if (f) filters[key] = f; else delete filters[key];
    setState({ ...state, filters } as TableState, { push: true });
  };
  const filterable = cols.filter((c) => c.filter);
  const searchable = cols.some((c) => c.search);
  const n = activeFilters(state);

  const exportCsv = () => {
    const vis = cols.filter((c) => !hidden.has(c.key) && (c.csv || c.sort));
    const col = state.sort && cols.find((c) => c.key === state.sort!.key);
    const out = col?.sort ? sortRows(kept, col.sort, state.sort!.asc) : kept;
    const blob = new Blob([toCsv(vis.map(colName), out, vis.map((c) => c.csv ?? c.sort!))], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${csvName ?? id}-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="toolbar" role="toolbar" aria-label="Table tools">
      {searchable && (
        <input type="search" className="tb-search" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)}
          aria-label="Search rows" />
      )}
      {filterable.map((c) => {
        const f = state.filters[c.key];
        return (
          <span key={c.key} className={`chip-wrap ${f ? "active" : ""}`}>
            <Popover label={`Filter ${colName(c)}`} trigger={<>{colName(c)}{f && <b>: {summary(f, c.filter!.unit)}</b>}<span className="caret">▾</span></>}>
              {(close) => c.filter!.kind === "enum" ? <EnumEditor rows={rows} col={c} f={f} set={(x) => setFilter(c.key, x)} />
                : c.filter!.kind === "bool" ? <BoolEditor f={f} set={(x) => { setFilter(c.key, x); close(); }} />
                : <RangeEditor f={f} unit={c.filter!.unit} set={(x) => setFilter(c.key, x)} close={close} />}
            </Popover>
            {f && <button type="button" className="chip-x" aria-label={`Clear ${colName(c)} filter`} onClick={() => setFilter(c.key)}>×</button>}
          </span>
        );
      })}
      {n > 0 && (
        <button type="button" className="linkish small" onClick={() => { setQ(""); setState({ q: "", filters: {}, sort: state.sort }, { push: true }); }}>
          Clear all
        </button>
      )}
      <span className="tb-count muted small">
        {kept.length === rows.length ? `${rows.length} rows` : `Showing ${kept.length} of ${rows.length}`}
        {missing > 0 && ` · ${missing} without data left out`}
      </span>
      <Popover label="Choose columns" className="tb-right" trigger={<>Columns<span className="caret">▾</span></>}>
        {() => (
          <div className="enum-list">
            {cols.map((c, i) => (
              <label key={c.key}>
                <input type="checkbox" checked={!hidden.has(c.key)} disabled={i === 0} onChange={() => toggleCol(c.key)} />
                <span>{colName(c) || c.key}</span>
              </label>
            ))}
            <button type="button" className="linkish small" onClick={resetCols}>Reset</button>
          </div>
        )}
      </Popover>
      <button type="button" className="chip-btn" onClick={exportCsv} title="Download the rows shown as CSV">Export CSV</button>
    </div>
  );
}

import { useMemo, type ReactNode } from "react";
import { filterRows, sortRows } from "../lib/tableState";
import { useHiddenColumns, useTableState } from "../lib/useTableState";
import { defaultHidden, type Col } from "./columns";
import { TableToolbar } from "./TableToolbar";
import { Term } from "./Term";

export type { Col } from "./columns";

function heatStyle(v: unknown, scale: number) {
  if (typeof v !== "number" || !Number.isFinite(v) || v === 0 || scale <= 0) return undefined;
  const pctOf = Math.min(Math.abs(v) / scale, 1) * 16;   // at most a light tint, so the text stays readable
  return { background: `color-mix(in srgb, var(${v > 0 ? "--gm-p3" : "--gm-n3"}) ${pctOf.toFixed(1)}%, transparent)` };
}

/** A sortable, filterable table whose state (sort, search, filters) lives in the URL under `id`. Tables that share
 *  an `id` share that state; give them `toolbar={false}` and render one <TableToolbar> for the group. */
export function DataTable<T>({ id, rows, cols, rowKey, toolbar = true, csvName, highlight, onHover, empty }: {
  id: string;
  rows: T[];
  cols: Col<T>[];
  rowKey: (row: T) => string;
  toolbar?: boolean;
  csvName?: string;
  highlight?: string | null;
  onHover?: (key: string | null) => void;
  empty?: ReactNode;
}) {
  const [state, setState] = useTableState(id);
  const [hidden] = useHiddenColumns(id, defaultHidden(cols));
  const visible = cols.filter((c) => !hidden.has(c.key));
  const shown = useMemo(() => {
    const { rows: kept } = filterRows(rows, cols, state);
    const col = state.sort && cols.find((c) => c.key === state.sort!.key);
    return col?.sort ? sortRows(kept, col.sort, state.sort!.asc) : kept;
  }, [rows, cols, state]);
  const scales = useMemo(() => Object.fromEntries(cols.filter((c) => c.heat && c.sort).map((c) => [c.key,
    Math.max(0, ...rows.map((r) => Math.abs(Number(c.sort!(r)))).filter(Number.isFinite))])), [rows, cols]);

  const click = (c: Col<T>) => {
    if (!c.sort) return;
    // numbers start high-to-low (the usual question is "who leads"), text A-Z
    const sample = rows.map(c.sort).find((v) => v !== null && v !== undefined);
    const asc = state.sort?.key === c.key ? !state.sort.asc : typeof sample === "string";
    setState({ ...state, sort: { key: c.key, asc } });
  };

  return (
    <>
      {toolbar && <TableToolbar id={id} rows={rows} cols={cols} csvName={csvName} />}
      <div className={`scroll dt-wrap ${rows.length > 25 ? "tall" : ""}`}>
        <table className="t dt">
          <thead>
            <tr>
              {visible.map((c) => {
                const sorted = state.sort?.key === c.key;
                return (
                  <th key={c.key} className={`${c.align === "l" ? "l" : ""} ${c.sort ? "sortable" : ""}`}
                    aria-sort={sorted ? (state.sort!.asc ? "ascending" : "descending") : undefined}>
                    <span className="th-inner">
                      {c.sort
                        ? <button type="button" className="th-sort" onClick={() => click(c)}>{c.help ? <Term k={c.help}>{c.label}</Term> : c.label}</button>
                        : c.help ? <Term k={c.help}>{c.label}</Term> : c.label}
                      {sorted && <span className="arrow" aria-hidden>{state.sort!.asc ? "▲" : "▼"}</span>}
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody onMouseLeave={onHover ? () => onHover(null) : undefined}>
            {shown.map((r) => {
              const k = rowKey(r);
              return (
                <tr key={k} className={highlight === k ? "hl" : ""} onMouseEnter={onHover ? () => onHover(k) : undefined}>
                  {visible.map((c) => (
                    <td key={c.key} className={c.align === "l" ? "l" : ""} style={c.heat && c.sort ? heatStyle(c.sort(r), scales[c.key] ?? 0) : undefined}>
                      {c.render(r)}
                    </td>
                  ))}
                </tr>
              );
            })}
            {shown.length === 0 && (
              <tr><td colSpan={visible.length} className="l empty-row">
                {rows.length === 0 ? (empty ?? "No rows.") : <>No rows match.{" "}
                  <button type="button" className="linkish" onClick={() => setState({ q: "", filters: {}, sort: state.sort }, { push: true })}>Clear filters</button></>}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

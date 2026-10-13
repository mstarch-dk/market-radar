import { useMemo, useState, type ReactNode } from "react";

export type SortValue = number | string | boolean | null | undefined;

export type Col<T> = {
  key: string;
  label: ReactNode;
  /** The value the column sorts by; columns without one aren't sortable. */
  sort?: (row: T) => SortValue;
  render: (row: T) => ReactNode;
  align?: "l" | "r";
  title?: string;
};

/** Sort order with missing values always last, whichever the direction ("no data" is never the best or worst). */
export function sortRows<T>(rows: T[], by: (row: T) => SortValue, asc: boolean): T[] {
  const missing = (v: SortValue) => v === null || v === undefined || (typeof v === "number" && !Number.isFinite(v));
  return [...rows].sort((a, b) => {
    const x = by(a), y = by(b);
    if (missing(x) || missing(y)) return missing(x) === missing(y) ? 0 : missing(x) ? 1 : -1;
    const c = typeof x === "string" && typeof y === "string" ? x.localeCompare(y) : Number(x) - Number(y);
    return asc ? c : -c;
  });
}

/** A table whose sortable headers toggle ascending/descending on click; rows start in the API's order. */
export function DataTable<T>({ rows, cols, rowKey, className = "" }: {
  rows: T[];
  cols: Col<T>[];
  rowKey: (row: T) => string;
  className?: string;
}) {
  const [sort, setSort] = useState<{ key: string; asc: boolean } | null>(null);
  const shown = useMemo(() => {
    if (!sort) return rows;
    const col = cols.find((c) => c.key === sort.key);
    return col?.sort ? sortRows(rows, col.sort, sort.asc) : rows;
  }, [rows, cols, sort]);
  const click = (c: Col<T>) => {
    if (!c.sort) return;
    // numbers start high-to-low (the usual question is "who leads"), text A-Z
    const sample = rows.map(c.sort).find((v) => v !== null && v !== undefined);
    const first = typeof sample === "string";
    setSort((s) => (s?.key === c.key ? { key: c.key, asc: !s.asc } : { key: c.key, asc: first }));
  };
  return (
    <div className="scroll">
      <table className={`t dt ${className}`}>
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c.key} className={`${c.align === "l" ? "l" : ""} ${c.sort ? "sortable" : ""}`} title={c.title}
                onClick={() => click(c)}
                aria-sort={sort?.key === c.key ? (sort.asc ? "ascending" : "descending") : undefined}>
                {c.label}{sort?.key === c.key && <span className="arrow">{sort.asc ? "▲" : "▼"}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((r) => (
            <tr key={rowKey(r)}>
              {cols.map((c) => <td key={c.key} className={c.align === "l" ? "l" : ""}>{c.render(r)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Table state (sort, search, filters) and the pure functions that apply it. The state lives in the URL, so a
// filtered view survives reloads, works with the back button and can be bookmarked.

export type SortValue = number | string | boolean | null | undefined;
export type FilterValue = SortValue | string[];

export type Filter =
  | { kind: "enum"; values: string[] }
  | { kind: "bool"; value: boolean }
  | { kind: "range"; min?: number; max?: number };

export type TableState = {
  sort?: { key: string; asc: boolean };
  q: string;
  filters: Record<string, Filter>;
};

/** What a table needs to know about a column to sort, search and filter it. */
export type ColSpec<T> = {
  key: string;
  sort?: (row: T) => SortValue;
  search?: (row: T) => string | null | undefined;
  filter?: { kind: Filter["kind"]; value?: (row: T) => FilterValue; unit?: "pct" | "num" };
};

export const EMPTY: TableState = { q: "", filters: {} };

const missing = (v: unknown): v is null | undefined =>
  v === null || v === undefined || v === "" || (typeof v === "number" && !Number.isFinite(v));

// ---------------- URL encoding ----------------
// ?{id}.sort=r3m:desc  ?{id}.q=semi  ?{id}.f.quadrant=in:Leading|Improving  ?{id}.f.trend=is:yes  ?{id}.f.r3m=range:0.05:

export function parseState(params: URLSearchParams, id: string): TableState {
  const out: TableState = { q: params.get(`${id}.q`) ?? "", filters: {} };
  const sort = params.get(`${id}.sort`);
  if (sort) {
    const i = sort.lastIndexOf(":");
    const key = i > 0 ? sort.slice(0, i) : sort;
    out.sort = { key, asc: sort.slice(i + 1) === "asc" };
  }
  const prefix = `${id}.f.`;
  for (const [k, v] of params) {
    if (!k.startsWith(prefix)) continue;
    const col = k.slice(prefix.length);
    if (v.startsWith("in:")) {
      const values = v.slice(3).split("|").filter(Boolean);
      if (values.length) out.filters[col] = { kind: "enum", values };
    } else if (v === "is:yes" || v === "is:no") {
      out.filters[col] = { kind: "bool", value: v === "is:yes" };
    } else if (v.startsWith("range:")) {
      const [lo = "", hi = ""] = v.slice(6).split(":");
      const min = lo === "" ? undefined : Number(lo);
      const max = hi === "" ? undefined : Number(hi);
      if ((min !== undefined && Number.isFinite(min)) || (max !== undefined && Number.isFinite(max))) {
        out.filters[col] = { kind: "range", min: Number.isFinite(min) ? min : undefined, max: Number.isFinite(max) ? max : undefined };
      }
    }
  }
  return out;
}

/** Writes `state` into a copy of `params`, replacing this table's keys and keeping everything else. */
export function serializeState(params: URLSearchParams, id: string, state: TableState): URLSearchParams {
  const next = new URLSearchParams();
  for (const [k, v] of params) if (!k.startsWith(`${id}.`)) next.append(k, v);
  if (state.sort) next.set(`${id}.sort`, `${state.sort.key}:${state.sort.asc ? "asc" : "desc"}`);
  if (state.q.trim()) next.set(`${id}.q`, state.q);
  for (const [col, f] of Object.entries(state.filters)) {
    const key = `${id}.f.${col}`;
    if (f.kind === "enum" && f.values.length) next.set(key, `in:${f.values.join("|")}`);
    else if (f.kind === "bool") next.set(key, f.value ? "is:yes" : "is:no");
    else if (f.kind === "range" && (f.min !== undefined || f.max !== undefined)) {
      next.set(key, `range:${f.min ?? ""}:${f.max ?? ""}`);
    }
  }
  return next;
}

export const activeFilters = (s: TableState) => Object.keys(s.filters).length + (s.q.trim() ? 1 : 0);

// ---------------- applying it ----------------

function filterValue<T>(c: ColSpec<T>, row: T): FilterValue {
  return c.filter?.value ? c.filter.value(row) : c.sort?.(row);
}

export function enumOptions<T>(rows: T[], c: ColSpec<T>): { value: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const r of rows) {
    const v = filterValue(c, r);
    for (const x of Array.isArray(v) ? v : [v]) {
      if (missing(x)) continue;
      const s = String(x);
      counts.set(s, (counts.get(s) ?? 0) + 1);
    }
  }
  return [...counts].map(([value, count]) => ({ value, count })).sort((a, b) => a.value.localeCompare(b.value));
}

/** Rows that pass the search and every filter. `missing` counts rows dropped only because a filtered column had
 *  no value: a filter never treats "no data" as a number. */
export function filterRows<T>(rows: T[], cols: ColSpec<T>[], state: TableState): { rows: T[]; missing: number } {
  const q = state.q.trim().toLowerCase();
  const byKey = new Map(cols.map((c) => [c.key, c]));
  const active = Object.entries(state.filters).filter(([k]) => byKey.has(k));
  let dropped = 0;
  const out = rows.filter((r) => {
    if (q) {
      const hay = cols.map((c) => c.search?.(r) ?? "").join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    let lacking = false;
    for (const [k, f] of active) {
      const v = filterValue(byKey.get(k)!, r);
      if (f.kind === "enum") {
        const vals = (Array.isArray(v) ? v : [v]).filter((x) => !missing(x)).map(String);
        if (!vals.some((x) => f.values.includes(x))) return false;
      } else if (missing(v) || Array.isArray(v)) {
        lacking = true;
      } else if (f.kind === "bool") {
        if (Boolean(v) !== f.value) return false;
      } else {
        const n = Number(v);
        if ((f.min !== undefined && n < f.min) || (f.max !== undefined && n > f.max)) return false;
      }
    }
    if (lacking) dropped++;
    return !lacking;
  });
  return { rows: out, missing: dropped };
}

/** Sort order with missing values always last, whichever the direction ("no data" is never the best or worst). */
export function sortRows<T>(rows: T[], by: (row: T) => SortValue, asc: boolean): T[] {
  return [...rows].sort((a, b) => {
    const x = by(a), y = by(b);
    if (missing(x) || missing(y)) return missing(x) === missing(y) ? 0 : missing(x) ? 1 : -1;
    const c = typeof x === "string" && typeof y === "string" ? x.localeCompare(y) : Number(x) - Number(y);
    return asc ? c : -c;
  });
}

// ---------------- CSV ----------------

export function csvCell(v: unknown): string {
  if (missing(v)) return "";
  const s = Array.isArray(v) ? v.join("; ") : String(v);
  return /[",\n\r;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function toCsv<T>(header: string[], rows: T[], cells: ((r: T) => unknown)[]): string {
  return [header.map(csvCell).join(","), ...rows.map((r) => cells.map((f) => csvCell(f(r))).join(","))].join("\n") + "\n";
}

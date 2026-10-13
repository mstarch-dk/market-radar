import { useCallback, useMemo, useSyncExternalStore } from "react";
import { useSearchParams } from "react-router-dom";
import { parseState, serializeState, type TableState } from "./tableState";

/** A table's sort/search/filters, read from and written to the URL under the prefix `id`. Sorting and typing
 *  replace the history entry; adding or removing a filter pushes one, so Back undoes it. */
export function useTableState(id: string): [TableState, (next: TableState, opts?: { push?: boolean }) => void] {
  const [params, setParams] = useSearchParams();
  const state = useMemo(() => parseState(params, id), [params, id]);
  const set = useCallback((next: TableState, opts?: { push?: boolean }) => {
    setParams((p) => serializeState(p, id, next), { replace: !opts?.push, preventScrollReset: true });
  }, [id, setParams]);
  return [state, set];
}

// Hidden columns: remembered per browser (a per-viewer convenience), shared live between a page's toolbar and
// its tables through a tiny store.
const storageKey = (id: string) => `radar.cols.${id}`;
const memory = new Map<string, string[]>();
const listeners = new Map<string, Set<() => void>>();

function readHidden(id: string, fallback: string[]): string[] {
  if (memory.has(id)) return memory.get(id)!;
  let v = fallback;
  try {
    const raw = localStorage.getItem(storageKey(id));
    if (raw) v = JSON.parse(raw) as string[];
  } catch {
    /* blocked storage: defaults */
  }
  memory.set(id, v);
  return v;
}

function writeHidden(id: string, v: string[]) {
  memory.set(id, v);
  try {
    localStorage.setItem(storageKey(id), JSON.stringify(v));
  } catch {
    /* private mode: keep it for this visit only */
  }
  listeners.get(id)?.forEach((f) => f());
}

export function useHiddenColumns(id: string, defaults: string[]): [Set<string>, (key: string) => void, () => void] {
  const subscribe = useCallback((f: () => void) => {
    const set = listeners.get(id) ?? new Set();
    set.add(f);
    listeners.set(id, set);
    return () => set.delete(f);
  }, [id]);
  const key = defaults.join("|");
  const hidden = useSyncExternalStore(subscribe, () => readHidden(id, key ? key.split("|") : []));
  const toggle = (k: string) => writeHidden(id, hidden.includes(k) ? hidden.filter((x) => x !== k) : [...hidden, k]);
  const reset = () => writeHidden(id, defaults);
  return [useMemo(() => new Set(hidden), [hidden]), toggle, reset];
}

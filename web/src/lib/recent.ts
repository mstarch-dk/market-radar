// Recently viewed tickers: a per-browser convenience, so storage failures (private mode) are ignored.
const KEY = "radar.recent";

export const recent = {
  list(): string[] {
    try {
      const v: unknown = JSON.parse(localStorage.getItem(KEY) ?? "[]");
      return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string").slice(0, 12) : [];
    } catch {
      return [];
    }
  },
  add(symbol: string): void {
    try {
      localStorage.setItem(KEY, JSON.stringify([symbol, ...recent.list().filter((s) => s !== symbol)].slice(0, 12)));
    } catch {
      /* storage unavailable */
    }
  },
};

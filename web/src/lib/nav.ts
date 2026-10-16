// The app's navigation: three groups of pages (a short group row, and under it the active group's pages).
// Pure data and functions, so the Home tiles, the nav and the tests share one structure.

export type NavPage = { path: string; label: string; blurb: string };
export type NavGroup = { id: "markets" | "mine" | "system"; label: string; pages: NavPage[] };

export const NAV: NavGroup[] = [
  {
    id: "markets", label: "Markets", pages: [
      { path: "/regime", label: "Regime", blurb: "Risk-on/off vote, breadth, credit, volatility" },
      { path: "/rotation", label: "Sector rotation", blurb: "US & European sectors, regions vs ACWI" },
      { path: "/themes", label: "Themes & factors", blurb: "Theme ETFs with UCITS alternatives, factors" },
      { path: "/momentum", label: "Momentum", blurb: "Leaders per region, clusters, new entrants" },
      { path: "/quality", label: "Quality & value", blurb: "Business quality and price from the statements, the A/B test" },
      { path: "/discover", label: "Discover", blurb: "Heat map and screener beyond the radar's lists" },
      { path: "/positioning", label: "Positioning & cycle", blurb: "Revisions, valuation, OECD CLI, CFTC, sentiment" },
    ],
  },
  {
    id: "mine", label: "Mine", pages: [
      { path: "/me", label: "Holdings & watchlist", blurb: "Returns vs ACWI, flags, stops and targets" },
      { path: "/portfolio", label: "Portfolio", blurb: "Your accounts: positions, transactions, imports" },
      { path: "/returns", label: "Returns", blurb: "Returns over time vs ACWI, A/B comparisons" },
      { path: "/experiments", label: "Experiments", blurb: "Virtual portfolios: A/B tests, simulations, forks" },
      { path: "/views", label: "Market views", blurb: "Your beliefs, tested against the data" },
      { path: "/notebook", label: "Notebook", blurb: "Briefs, research memos and your decision journal" },
    ],
  },
  {
    id: "system", label: "System", pages: [
      { path: "/data", label: "Data & coverage", blurb: "Sources, freshness, blind spots" },
      { path: "/ops", label: "Operations", blurb: "Requests, errors, jobs and pauses" },
    ],
  },
];

export const ALL_PAGES = NAV.flatMap((g) => g.pages);

/** The group a path belongs to: a page's own group (sub-paths such as /notebook/journal/x included), a ticker page
 *  counts as Markets; home, the guide and unknown paths have none. */
export function groupOf(pathname: string): NavGroup | null {
  if (pathname.startsWith("/ticker/")) return NAV[0]!;
  return NAV.find((g) => g.pages.some((p) => pathname === p.path || pathname.startsWith(`${p.path}/`))) ?? null;
}

type Store = { get(key: string): string | null; set(key: string, value: string): void };

const KEY = "nav.last";

/** Browser storage that may be missing or refuse (private windows, blocked site data): then nothing is remembered. */
export const browserStore: Store = {
  get: (k) => { try { return window.localStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { window.localStorage.setItem(k, v); } catch { /* not remembered */ } },
};

function read(store: Store): Record<string, string> {
  try {
    const v = JSON.parse(store.get(KEY) ?? "{}");
    return v && typeof v === "object" ? v : {};
  } catch {
    return {};
  }
}

/** Remember the page just opened (with its query string) as its group's last page. */
export function remember(pathname: string, search: string, store: Store = browserStore): void {
  const g = groupOf(pathname);
  if (!g || pathname.startsWith("/ticker/")) return;
  store.set(KEY, JSON.stringify({ ...read(store), [g.id]: pathname + search }));
}

const FROM = "nav.from";

/** Per-tab browser storage (sessionStorage), for where a ticker profile was opened from. */
export const tabStore: Store = {
  get: (k) => { try { return window.sessionStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { window.sessionStorage.setItem(k, v); } catch { /* not remembered */ } },
};

/** Remember the page a ticker profile is opened from: every page in a group counts; home, the guide and unknown pages
 *  clear it; a ticker page keeps it (one profile linking to the next stays under the same page). */
export function rememberFrom(pathname: string, search: string, store: Store = tabStore): void {
  if (pathname.startsWith("/ticker/")) return;
  store.set(FROM, groupOf(pathname) ? pathname + search : "");
}

export type Location = { group: NavGroup; page: NavPage | null; from: string | null; symbol: string };

/** Where a ticker page sits in the menu: under the page it was opened from (with that page's query string, so the
 *  way back keeps its filters), else under Markets with no page. Null for any other path. */
export function tickerLocation(pathname: string, store: Store = tabStore): Location | null {
  if (!pathname.startsWith("/ticker/")) return null;
  let symbol = pathname.slice("/ticker/".length);
  try { symbol = decodeURIComponent(symbol); } catch { /* shown as written */ }
  symbol = symbol.toUpperCase();
  const from = store.get(FROM) || null;
  const path = from?.split("?")[0] ?? "";
  const group = from ? groupOf(path) : null;
  if (!group) return { group: NAV[0]!, page: null, from: null, symbol };
  const page = group.pages.find((p) => path === p.path || path.startsWith(`${p.path}/`)) ?? null;
  return { group, page, from, symbol };
}

/** Where a group's tab leads: the page last opened in it, else its first page. */
export function lastPage(group: NavGroup, store: Store = browserStore): string {
  const last = read(store)[group.id];
  return last && groupOf(last.split("?")[0]!)?.id === group.id ? last : group.pages[0]!.path;
}

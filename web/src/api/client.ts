import type { components } from "./schema";

type S = components["schemas"];
export type Profile = S["Profile"];
export type Series = S["Series"];
export type SearchHit = S["SearchHit"];
export type AppContext = S["AppContext"];
export type Windows = S["Windows"];
export type SectionMeta = Pick<S["Price"], "status" | "source" | "asof">;
export type RegimeView = S["RegimeView"];
export type RotationView = S["RotationView"];
export type RotationGroup = S["RotationGroup"];
export type RotationRow = S["RotationRow"];
export type RrgTrail = S["RrgTrail"];
export type MomentumView = S["MomentumView"];
export type MomentumRow = S["MomentumRow"];
export type DiscoveryView = S["DiscoveryView"];
export type DiscoveryMarket = S["DiscoveryMarket"];
export type DiscoveryRow = S["DiscoveryRow"];
export type PositioningView = S["PositioningView"];
export type CoverageView = S["CoverageView"];
export type LineChartData = S["LineChart"];
export type MeView = S["MeView"];
export type MyRow = S["MyRow"];
export type WatchState = S["WatchState"];
export type TickerSummary = S["TickerSummary"];
export type UpdateStatus = S["UpdateStatus"];
export type ImportResult = S["ImportResult"];
export type TxIn = S["TxIn"];
export type TxRow = S["TxRow"];
export type TxCheck = S["TxCheck"];
export type TxResult = S["TxResult"];
export type Issue = S["Issue"];
export type PositionsView = S["PositionsView"];
export type PositionRow = S["PositionRow"];
export type PriceCheck = S["PriceCheck"];
export type Account = S["Account"];
export type AccountIn = S["AccountIn"];
export type ImportPreview = S["ImportPreview"];
export type ImportRow = S["ImportRow"];
export type ImportRecord = S["ImportRecord"];
export type ImportCommitResult = S["ImportCommitResult"];
export type Preset = S["Preset"];
export type ImportParams = { filename: string; preset?: string; account?: string; mapping?: Record<string, string>;
  symbols?: Record<string, string>; confirm?: boolean };

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** validation issues sent with a 422 (portfolio editor) */
    public issues: Issue[] = [],
  ) {
    super(message);
  }
}

async function get<T>(url: string, method = "GET", body?: BodyInit, contentType?: string): Promise<T> {
  const r = await fetch(url, { method, body, headers: contentType ? { "Content-Type": contentType } : undefined });
  if (!r.ok) {
    let detail = r.statusText;
    let issues: Issue[] = [];
    try {
      const body = (await r.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
      else if (body.detail && typeof body.detail === "object" && "message" in body.detail) {
        const d = body.detail as { message: string; issues?: Issue[] };
        detail = d.message;
        issues = d.issues ?? [];
      }
    } catch {
      /* not JSON */
    }
    throw new ApiError(r.status, detail, issues);
  }
  return (await r.json()) as T;
}

const enc = encodeURIComponent;

function importQuery(p: ImportParams): string {
  const q = new URLSearchParams({ filename: p.filename });
  if (p.preset) q.set("preset", p.preset);
  if (p.account) q.set("account", p.account);
  if (p.mapping) q.set("mapping", JSON.stringify(p.mapping));
  if (p.symbols && Object.keys(p.symbols).length) q.set("symbols", JSON.stringify(p.symbols));
  if (p.confirm) q.set("confirm", "true");
  return q.toString();
}

export const api = {
  profile: (symbol: string, refresh = false) =>
    get<Profile>(`/api/ticker/${enc(symbol)}${refresh ? "?refresh=true" : ""}`),
  series: (symbol: string, days = 756) => get<Series>(`/api/ticker/${enc(symbol)}/series?days=${days}`),
  search: (q: string) => get<SearchHit[]>(`/api/search?q=${enc(q)}`),
  context: () => get<AppContext>("/api/context"),
  regime: () => get<RegimeView>("/api/regime"),
  rotation: () => get<RotationView>("/api/rotation"),
  momentum: () => get<MomentumView>("/api/momentum"),
  positioning: () => get<PositioningView>("/api/positioning"),
  coverage: () => get<CoverageView>("/api/coverage"),
  discover: () => get<DiscoveryView>("/api/discover"),
  discoverStatus: () => get<UpdateStatus>("/api/discover/scan"),
  startDiscover: () => get<UpdateStatus>("/api/discover/scan", "POST"),
  me: () => get<MeView>("/api/me"),
  tickers: () => get<TickerSummary[]>("/api/tickers"),
  updateStatus: () => get<UpdateStatus>("/api/update"),
  startUpdate: () => get<UpdateStatus>("/api/update", "POST"),
  importPortfolio: (csv: string) => get<ImportResult>("/api/import", "POST", csv, "text/csv"),
  transactions: () => get<TxRow[]>("/api/portfolio/transactions"),
  validateTx: (tx: TxIn, id?: number) =>
    get<TxCheck>(`/api/portfolio/validate${id ? `?id=${id}` : ""}`, "POST", JSON.stringify(tx), "application/json"),
  addTx: (tx: TxIn) => get<TxResult>("/api/portfolio/transactions", "POST", JSON.stringify(tx), "application/json"),
  editTx: (id: number, tx: TxIn) => get<TxResult>(`/api/portfolio/transactions/${id}`, "PUT", JSON.stringify(tx), "application/json"),
  deleteTx: (id: number) => get<TxRow>(`/api/portfolio/transactions/${id}`, "DELETE"),
  restoreTx: (row: TxRow) => get<TxRow>("/api/portfolio/transactions/restore", "POST", JSON.stringify(row), "application/json"),
  positions: () => get<PositionsView>("/api/portfolio/positions"),
  priceCheck: (symbol: string, date: string) =>
    get<PriceCheck>(`/api/portfolio/price-check?symbol=${enc(symbol)}&date=${enc(date)}`),
  accounts: () => get<Account[]>("/api/portfolio/accounts"),
  importPresets: () => get<Preset[]>("/api/portfolio/import/presets"),
  importPreview: (file: ArrayBuffer, p: ImportParams) =>
    get<ImportPreview>(`/api/portfolio/import/preview?${importQuery(p)}`, "POST", file, "application/octet-stream"),
  importCommit: (file: ArrayBuffer, p: ImportParams) =>
    get<ImportCommitResult>(`/api/portfolio/import/commit?${importQuery(p)}`, "POST", file, "application/octet-stream"),
  imports: () => get<ImportRecord[]>("/api/portfolio/imports"),
  undoImport: (id: number) => get<number>(`/api/portfolio/imports/${id}`, "DELETE"),
  saveAccount: (a: AccountIn) => get<Account[]>("/api/portfolio/accounts", "POST", JSON.stringify(a), "application/json"),
  watch: (symbol: string) => get<WatchState>(`/api/watchlist/${enc(symbol)}`, "PUT"),
  unwatch: (symbol: string) => get<WatchState>(`/api/watchlist/${enc(symbol)}`, "DELETE"),
};

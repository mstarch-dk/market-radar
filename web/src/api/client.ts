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
export type PositioningView = S["PositioningView"];
export type CoverageView = S["CoverageView"];
export type LineChartData = S["LineChart"];
export type MeView = S["MeView"];
export type MyRow = S["MyRow"];
export type WatchState = S["WatchState"];
export type TickerSummary = S["TickerSummary"];
export type UpdateStatus = S["UpdateStatus"];
export type ImportResult = S["ImportResult"];

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function get<T>(url: string, method = "GET", body?: BodyInit, contentType?: string): Promise<T> {
  const r = await fetch(url, { method, body, headers: contentType ? { "Content-Type": contentType } : undefined });
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const body = (await r.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(r.status, detail);
  }
  return (await r.json()) as T;
}

const enc = encodeURIComponent;

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
  me: () => get<MeView>("/api/me"),
  tickers: () => get<TickerSummary[]>("/api/tickers"),
  updateStatus: () => get<UpdateStatus>("/api/update"),
  startUpdate: () => get<UpdateStatus>("/api/update", "POST"),
  importPortfolio: (csv: string) => get<ImportResult>("/api/import", "POST", csv, "text/csv"),
  watch: (symbol: string) => get<WatchState>(`/api/watchlist/${enc(symbol)}`, "PUT"),
  unwatch: (symbol: string) => get<WatchState>(`/api/watchlist/${enc(symbol)}`, "DELETE"),
};

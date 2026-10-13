import type { components } from "./schema";

type S = components["schemas"];
export type Profile = S["Profile"];
export type Series = S["Series"];
export type SearchHit = S["SearchHit"];
export type AppContext = S["AppContext"];
export type Windows = S["Windows"];
export type SectionMeta = Pick<S["Price"], "status" | "source" | "asof">;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
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
};

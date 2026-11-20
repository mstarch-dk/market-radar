import { useQuery } from "@tanstack/react-query";
import { api, type SectorEtfRow, type SectorEtfsView } from "../api/client";

/** A sector key as an anchor on the Sector ETFs page: "Autos & Parts" → "autos-parts". */
export const sectorAnchor = (key: string) => key.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

export type SectorGoTo = { key: string; label: string; href: string; pick: SectorEtfRow | null };

/** Each sector by its key and by its rotation tickers (XLK, EXV1.DE …), with the go-to of the latest record. */
export function goToIndex(v: SectorEtfsView | undefined) {
  const byKey = new Map<string, SectorGoTo>();
  const byTicker = new Map<string, SectorGoTo>();
  for (const s of v?.sectors ?? []) {
    const g = { key: s.key, label: s.label, href: `/sectoretfs#${sectorAnchor(s.key)}`, pick: s.etfs.find((e) => e.pick) ?? null };
    byKey.set(s.key, g);
    for (const r of s.rotation) byTicker.set(r.ticker, g);
  }
  return { byKey, byTicker };
}

/** The Sector ETFs page's data, for the links from other pages (empty until it loads, or if it fails). */
export function useSectorGoTo() {
  const q = useQuery({ queryKey: ["sector-etfs"], queryFn: api.sectorEtfs, retry: false, staleTime: 5 * 60_000 });
  return goToIndex(q.data);
}

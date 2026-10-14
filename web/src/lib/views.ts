// Market views (your subjective beliefs): display helpers and the alignment lookup for table columns.
import { useQuery } from "@tanstack/react-query";
import { api, type AlignCompact } from "../api/client";

export type AlignLabel = AlignCompact["label"];

export const ALIGN_KIND: Record<AlignLabel, string> = { aligned: "pos", conflicts: "neg", mixed: "warn", unrelated: "" };
export const ALIGN_TEXT: Record<AlignLabel, string> = {
  aligned: "fits your views", conflicts: "against your views", mixed: "mixed", unrelated: "unrelated",
};
export const VERDICT_KIND: Record<string, string> = {
  supported: "pos", contradicted: "neg", mixed: "warn", unclear: "", "no data": "na",
};
export const STATE_KIND: Record<string, string> = { supports: "pos", contradicts: "neg", flat: "", "no data": "na" };

const ORDER: Record<AlignLabel, number> = { aligned: 3, mixed: 2, unrelated: 1, conflicts: 0 };

/** Sort value for an alignment column: aligned first, then mixed, unrelated, conflicts; stronger first within. */
export function alignSort(a: AlignCompact | undefined): number | null {
  return a ? ORDER[a.label] + Math.max(-0.99, Math.min(0.99, a.score)) / 10 : null;
}

/** "AI is in a bubble" → conviction dots ●●●○○ */
export const dots = (n: number) => "●".repeat(n) + "○".repeat(Math.max(0, 5 - n));

/** Alignment of many tickers with your active views ({} when you have none). */
export function useAlignment(tickers: string[], store: "main" | "discovery") {
  const q = useQuery({
    queryKey: ["views-align", store, tickers.length, tickers[0], tickers[tickers.length - 1]],
    queryFn: () => api.alignViews(tickers, store),
    enabled: tickers.length > 0,
    staleTime: 60_000,
  });
  return q.data ?? {};
}

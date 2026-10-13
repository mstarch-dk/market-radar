import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { api, type TickerSummary } from "../api/client";

/** Every tracked ticker in brief, keyed by symbol: one cached request shared by all hover cards and badges. */
export function useTickers(): Map<string, TickerSummary> {
  const { data } = useQuery({ queryKey: ["tickers"], queryFn: api.tickers, staleTime: 10 * 60_000, retry: false });
  return useMemo(() => new Map((data ?? []).map((t) => [t.symbol, t])), [data]);
}

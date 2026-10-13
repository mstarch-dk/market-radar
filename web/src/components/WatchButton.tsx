import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useTickers } from "../lib/tickers";

function useWatch(symbol: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (watch: boolean) => (watch ? api.watch(symbol) : api.unwatch(symbol)),
    onSuccess: () => {
      for (const key of [["profile", symbol], ["context"], ["me"], ["tickers"]]) qc.invalidateQueries({ queryKey: key });
    },
  });
}

/** Add a symbol to, or take it off, the watchlist (stored locally by the API). Holdings come from the Yahoo
 *  import, so they get no button. */
export function WatchButton({ symbol, status, compact }: { symbol: string; status: string | null | undefined; compact?: boolean }) {
  const m = useWatch(symbol);
  if (status === "holding") return null;
  const watching = status === "watch";
  const label = m.isPending ? (watching ? "Removing…" : "Adding…")
    : compact ? (watching ? "Remove" : "Watch") : watching ? "Remove from watchlist" : "Add to watchlist";
  return (
    <>
      <button className={`btn ${watching ? "" : "primary"} ${compact ? "small" : ""}`} disabled={m.isPending}
        onClick={() => m.mutate(!watching)}
        aria-label={watching ? `Take ${symbol} off your watchlist` : `Put ${symbol} on your watchlist`}>
        {watching ? "★ " : "☆ "}{label}
      </button>
      {m.isError && <span className="neg small"> {m.error.message}</span>}
    </>
  );
}

/** The one-click star for table rows: ☆ adds to the watchlist, ★ removes; held positions show a filled dot. */
export function WatchStar({ symbol }: { symbol: string }) {
  const status = useTickers().get(symbol)?.my_status;
  const m = useWatch(symbol);
  if (status === "holding") return <span className="star held" aria-label="You hold this">●</span>;
  const watching = status === "watch";
  return (
    <button type="button" className={`star ${watching ? "on" : ""}`} disabled={m.isPending} onClick={() => m.mutate(!watching)}
      aria-label={watching ? `Take ${symbol} off your watchlist` : `Put ${symbol} on your watchlist`}
      aria-pressed={watching}>
      {watching ? "★" : "☆"}
    </button>
  );
}

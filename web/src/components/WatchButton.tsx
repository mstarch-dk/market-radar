import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

/** Add a symbol to, or take it off, the watchlist (stored locally by the API). Holdings come from the Yahoo
 *  import, so they get no button. */
export function WatchButton({ symbol, status, compact }: { symbol: string; status: string | null | undefined; compact?: boolean }) {
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: (watch: boolean) => (watch ? api.watch(symbol) : api.unwatch(symbol)),
    onSuccess: () => {
      for (const key of [["profile", symbol], ["context"], ["me"]]) qc.invalidateQueries({ queryKey: key });
    },
  });
  if (status === "holding") return null;
  const watching = status === "watch";
  const label = m.isPending ? (watching ? "Removing…" : "Adding…")
    : compact ? (watching ? "Remove" : "Watch") : watching ? "Remove from watchlist" : "Add to watchlist";
  return (
    <>
      <button className={`btn ${watching ? "" : "primary"} ${compact ? "small" : ""}`} disabled={m.isPending}
        onClick={() => m.mutate(!watching)}
        title={watching ? `Take ${symbol} off your watchlist` : `Put ${symbol} on your watchlist (it joins the daily update)`}>
        {watching ? "★ " : "☆ "}{label}
      </button>
      {m.isError && <span className="neg small"> {m.error.message}</span>}
    </>
  );
}

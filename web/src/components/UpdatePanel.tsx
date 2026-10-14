import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api } from "../api/client";

/** "Update data" from the app: starts the same refresh as `uv run radar run` and shows its progress, so nobody
 *  needs a terminal. When it finishes, every page reloads its data. */
export function UpdatePanel({ compact, label = "Update data" }: { compact?: boolean; label?: string }) {
  const qc = useQueryClient();
  const status = useQuery({
    queryKey: ["update"], queryFn: api.updateStatus,
    refetchInterval: (q) => (q.state.data?.status === "running" ? 1500 : false),
  });
  const start = useMutation({
    mutationFn: api.startUpdate,
    onSuccess: (s) => qc.setQueryData(["update"], s),
  });
  const s = status.data;
  const running = s?.status === "running";
  const was = useRef(s?.status);
  useEffect(() => {                 // a finished update: reload everything the pages show
    if (was.current === "running" && s && s.status !== "running") qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "update" });
    was.current = s?.status;
  }, [s, qc]);

  const pct = s?.progress ? Math.round((100 * s.progress.done) / Math.max(1, s.progress.total)) : null;
  return (
    <div className={`update-panel ${compact ? "compact" : "card"}`}>
      <div className="up-row">
        <button type="button" className="btn primary" disabled={running || start.isPending} onClick={() => start.mutate()}>
          {running ? "Updating…" : label}
        </button>
        {running && (
          <span className="small muted">
            {s?.progress ? `${s.progress.label}: ${s.progress.done} of ${s.progress.total} tickers (${pct}%)` : "Working…"}
            {" "}You can keep using the app; pages refresh when it's done.
          </span>
        )}
        {!running && s?.status === "done" && <span className="small pos">Updated {s.finished?.replace("T", " ").slice(0, 16)}.</span>}
        {!running && s?.status === "failed" && <span className="small neg">Update stopped: {s.error}</span>}
        {start.isError && <span className="small neg">{start.error.message}</span>}
      </div>
      {running && pct !== null && <div className="up-bar"><div style={{ width: `${pct}%` }} /></div>}
      {!compact && s && s.log.length > 0 && (
        <details className="up-log" open={running || s.status === "failed"}>
          <summary className="small muted">What it did ({s.log.length} lines)</summary>
          <pre>{s.log.join("\n")}</pre>
        </details>
      )}
    </div>
  );
}

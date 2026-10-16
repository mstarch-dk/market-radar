import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api } from "../api/client";

const JOBS = {
  daily: { key: "update", status: api.updateStatus, start: api.startUpdate, unit: "tickers", busy: "Updating…", done: "Updated", stopped: "Update stopped" },
  discover: { key: "discover-scan", status: api.discoverStatus, start: api.startDiscover, unit: "", busy: "Updating…", done: "Updated", stopped: "Update stopped" },
  // the readings rebuilt from the data already downloaded (no downloads; about half a minute)
  report: { key: "report", status: api.reportStatus, start: api.startReport, unit: "", busy: "Rebuilding…", done: "Rebuilt", stopped: "Rebuild stopped" },
} as const;

/** "Update data" from the app: starts the same refresh as `uv run radar run` (or, with `job="discover"`, the
 *  discovery scan; with `job="report"`, `uv run radar report`) and shows its progress, so nobody needs a terminal. When it finishes, every page reloads its
 *  data. */
export function UpdatePanel({ compact, label = "Update data", job = "daily" }: {
  compact?: boolean; label?: string; job?: keyof typeof JOBS;
}) {
  const j = JOBS[job];
  const qc = useQueryClient();
  const status = useQuery({
    queryKey: [j.key], queryFn: j.status,
    refetchInterval: (q) => (q.state.data?.status === "running" ? 1500 : false),
  });
  const start = useMutation({
    mutationFn: j.start,
    onSuccess: (s) => qc.setQueryData([j.key], s),
  });
  const s = status.data;
  const running = s?.status === "running";
  const was = useRef(s?.status);
  useEffect(() => {                 // a finished update: reload everything the pages show
    if (was.current === "running" && s && s.status !== "running") qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== j.key });
    was.current = s?.status;
  }, [s, qc, j.key]);

  const pct = s?.progress ? Math.round((100 * s.progress.done) / Math.max(1, s.progress.total)) : null;
  return (
    <div className={`update-panel ${compact ? "compact" : "card"}`}>
      <div className="up-row">
        <button type="button" className="btn primary" disabled={running || start.isPending} onClick={() => start.mutate()}>
          {running ? j.busy : label}
        </button>
        {running && (
          <span className="small muted">
            {s?.progress ? `${s.progress.label}: ${s.progress.done} of ${s.progress.total}${j.unit ? ` ${j.unit}` : ""} (${pct}%)` : "Working…"}
            {" "}You can keep using the app; pages refresh when it's done.
          </span>
        )}
        {!running && s?.status === "done" && <span className="small pos">{j.done} {s.finished?.replace("T", " ").slice(0, 16)}.</span>}
        {!running && s?.status === "failed" && <span className="small neg">{j.stopped}: {s.error}</span>}
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

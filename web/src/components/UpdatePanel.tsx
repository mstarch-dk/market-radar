import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api, type UpdateStatus } from "../api/client";
import { JobProgressView } from "./JobProgress";

const JOBS = {
  daily: { key: "update", status: api.updateStatus, start: api.startUpdate, unit: "tickers", busy: "Updating…", done: "Updated", stopped: "Update stopped" },
  discover: { key: "discover-scan", status: api.discoverStatus, start: api.startDiscover, unit: "", busy: "Updating…", done: "Updated", stopped: "Update stopped" },
  // the readings rebuilt from the data already downloaded (no downloads; about half a minute)
  report: { key: "report", status: api.reportStatus, start: api.startReport, unit: "", busy: "Rebuilding…", done: "Rebuilt", stopped: "Rebuild stopped" },
} as const;

const IDLE_POLL = 15_000;   // the data refresh is checked now and then, so one started in a terminal or by Claude shows

/** Who runs a job another process started (the operations log's kind). */
const WHO: Record<string, string> = { cli_run: "in a terminal", cli_update: "in a terminal", update: "by Claude or another window" };

/** The one-line status: the step (i of n) and its phase, or the bare phase for a job without steps. */
function line(s: UpdateStatus, unit: string): string {
  const p = s.progress;
  const phase = p && p.total ? `${p.label}: ${p.done.toLocaleString()} of ${p.total.toLocaleString()}${unit && !s.step ? ` ${unit}` : ""} (${Math.round((100 * p.done) / p.total)}%)` : "";
  if (s.step) return `Step ${s.step.i} of ${s.step.n}: ${s.step.label}${phase ? ` · ${phase}` : ""}.`;
  return phase || "Working…";
}

/** "Update data" from the app: starts the same refresh as `uv run radar run` (or, with `job="discover"`, the
 *  discovery scan; with `job="report"`, `uv run radar report`) and shows its progress, so nobody needs a terminal.
 *  An update started in a terminal or by Claude shows here too, read-only. When it finishes, every page reloads
 *  its data. */
export function UpdatePanel({ compact, label = "Update data", job = "daily" }: {
  compact?: boolean; label?: string; job?: keyof typeof JOBS;
}) {
  const j = JOBS[job];
  const qc = useQueryClient();
  const status = useQuery({
    queryKey: [j.key], queryFn: j.status,
    refetchInterval: (q) => (q.state.data?.status === "running" ? 1500 : job === "daily" ? IDLE_POLL : false),
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

  const pct = s?.progress && !s.step ? Math.round((100 * s.progress.done) / Math.max(1, s.progress.total)) : null;
  const tracked = !!s && (s.steps.length > 0 || s.issues.length > 0);
  return (
    <div className={`update-panel ${compact ? "compact" : "card"}`}>
      <div className="up-row">
        <button type="button" className="btn primary" disabled={running || start.isPending} onClick={() => start.mutate()}>
          {running ? j.busy : label}
        </button>
        {running && s && (
          <span className="small muted">
            {s.elsewhere && <b>Started {WHO[s.elsewhere] ?? "elsewhere"}. </b>}
            {(compact || !tracked) && line(s, j.unit)}
            {" "}You can keep using the app; pages refresh when it&apos;s done.
          </span>
        )}
        {!running && s?.status === "done" && <span className="small pos">{j.done} {s.finished?.replace("T", " ").slice(0, 16)}.</span>}
        {!running && s?.status === "done" && s.issues_total > 0 && (
          <span className="small warn-text">{s.issues_total} {s.issues_total === 1 ? "problem" : "problems"} on the way{compact ? " (see the Data page)" : ""}.</span>
        )}
        {!running && s?.status === "failed" && <span className="small neg">{j.stopped}: {s.error}</span>}
        {start.isError && <span className="small neg">{start.error.message}</span>}
      </div>
      {running && pct !== null && <div className="up-bar"><div style={{ width: `${pct}%` }} /></div>}
      {!compact && s && tracked && (running || s.issues.length > 0) && (
        <JobProgressView p={{ step: s.step, phase: s.progress, steps: s.steps, issues: s.issues, issues_total: s.issues_total }} />
      )}
      {compact && running && s?.step && s.progress && s.progress.total > 0 && (
        <div className="up-bar"><div style={{ width: `${Math.round((100 * s.progress.done) / s.progress.total)}%` }} /></div>
      )}
      {!compact && s && s.log.length > 0 && (
        <details className="up-log" open={running || s.status === "failed"}>
          <summary className="small muted">What it did ({s.log.length} lines)</summary>
          <pre>{s.log.join("\n")}</pre>
        </details>
      )}
    </div>
  );
}

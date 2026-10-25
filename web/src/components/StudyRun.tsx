import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api, type ReportHead } from "../api/client";
import { elapsed, runAction } from "../lib/evidence";

/** "Run the study" on an Evidence card: the study's own command (`uv run radar study …`) started by the app as a
 *  child process, one study at a time, with its log and a Cancel button, so nobody needs a terminal. When it
 *  finishes the Evidence page reloads and shows the new report. `compact`: the button and a status line only. */
export function StudyRun({ h, compact }: { h: Pick<ReportHead, "run_key" | "status" | "old_data" | "label">; compact?: boolean }) {
  const qc = useQueryClient();
  const status = useQuery({
    queryKey: ["study-run"], queryFn: api.studyStatus,
    refetchInterval: (q) => (q.state.data?.status === "running" ? 1500 : false),
  });
  const start = useMutation({ mutationFn: () => api.startStudy(h.run_key), onSuccess: (s) => qc.setQueryData(["study-run"], s) });
  const cancel = useMutation({ mutationFn: api.cancelStudy, onSuccess: (s) => qc.setQueryData(["study-run"], s) });
  const s = status.data;
  const running = s?.status === "running";
  const mine = s?.study === h.run_key;
  const was = useRef(s?.status);
  useEffect(() => {                 // a finished run (any study): the Evidence page reads the reports again
    if (was.current === "running" && s && s.status !== "running") qc.invalidateQueries({ queryKey: ["evidence"] });
    was.current = s?.status;
  }, [s, qc]);

  const [now, setNow] = useState(Date.now());
  useEffect(() => {                 // the time it has run, by the second (a study can print nothing for minutes)
    if (!(running && mine)) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [running, mine]);

  const action = runAction(h);
  const last = s?.log.at(-1)?.replace(/^\d\d:\d\d:\d\d /, "");
  return (
    <div className={`update-panel study-run ${compact ? "compact" : ""}`}>
      <div className="up-row">
        {running && mine ? (
          <button type="button" className="btn" disabled={cancel.isPending} onClick={() => cancel.mutate()}>Cancel</button>
        ) : (
          <button type="button" className={`btn${action.primary ? " primary" : ""}`} disabled={running || start.isPending}
            title={running ? "Another study is running: one at a time" : undefined} onClick={() => start.mutate()}>
            {action.label}
          </button>
        )}
        {running && mine && (
          <span className="small muted">Running for {elapsed(s?.started, now)}{last ? `: ${last}` : ""}. You can keep using the app.</span>
        )}
        {running && !mine && !compact && <span className="small muted">Another study is running ({s?.study}).</span>}
        {!running && mine && s?.status === "done" && <span className="small pos">Finished {s.finished?.replace("T", " ").slice(0, 16)}.</span>}
        {!running && mine && s?.status === "failed" && <span className="small neg">Stopped: {s.error}</span>}
        {start.isError && <span className="small neg">{start.error.message}</span>}
        {cancel.isError && <span className="small neg">{cancel.error.message}</span>}
      </div>
      {!compact && mine && s && s.log.length > 0 && (
        <details className="up-log" open={s.status === "failed"}>
          <summary className="small muted">What it did ({s.log.length} lines)</summary>
          <pre>{s.log.join("\n")}</pre>
        </details>
      )}
    </div>
  );
}

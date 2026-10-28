import type { JobProgress } from "../api/client";

const MARK: Record<"ok" | "failed" | "running" | "pending", { text: string; cls: string; label: string }> = {
  ok: { text: "✓", cls: "pos", label: "done" },
  failed: { text: "✗", cls: "neg", label: "failed" },
  running: { text: "›", cls: "accent", label: "running" },
  pending: { text: "·", cls: "muted", label: "to come" },
};

/** What a job is doing and what has gone wrong so far: the step running (i of n) with its phase as a bar, every
 *  step with how it ended, and the issues met so far (a failed source keeps its cached data; a ticker without
 *  data is left out). Shared by the update panel and the Operations page. */
export function JobProgressView({ p, steps = true }: { p: JobProgress; steps?: boolean }) {
  const phase = p.phase;
  const pct = phase && phase.total ? Math.round((100 * phase.done) / phase.total) : null;
  const issues = p.issues ?? [];
  const more = (p.issues_total ?? 0) - issues.length;
  return (
    <div className="job-progress">
      {p.step && (
        <div className="small">
          <b>Step {p.step.i} of {p.step.n}:</b> {p.step.label}
          {phase && phase.total > 0 && <span className="muted"> · {phase.label}: {phase.done.toLocaleString()} of {phase.total.toLocaleString()} ({pct}%)</span>}
        </div>
      )}
      {pct !== null && <div className="up-bar" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><div style={{ width: `${pct}%` }} /></div>}
      {issues.length > 0 && (
        <ul className="jp-issues" aria-label="Problems so far">
          {more > 0 && <li className="muted">{more} earlier {more === 1 ? "problem" : "problems"} not shown (see the log)</li>}
          {issues.map((i, k) => (
            <li key={k} className={i.level === "error" ? "neg" : "warn-text"}>{i.source && <b>{i.source}: </b>}{i.message}</li>
          ))}
        </ul>
      )}
      {steps && (p.steps ?? []).length > 0 && (
        <details className="small">
          <summary className="muted">
            Steps: {p.steps.filter((s) => s.status === "ok").length} done
            {p.steps.some((s) => s.status === "failed") && <span className="neg">, {p.steps.filter((s) => s.status === "failed").length} failed</span>}
            {" "}of {p.steps.length}
          </summary>
          <ol className="jp-steps">
            {p.steps.map((s) => {
              const m = MARK[s.status];
              return (
                <li key={s.key} title={s.message ?? undefined}>
                  <span className={`jp-mark ${m.cls}`} aria-label={m.label}>{m.text}</span>
                  <span className={s.status === "pending" ? "muted" : ""}>{s.label}</span>
                </li>
              );
            })}
          </ol>
        </details>
      )}
    </div>
  );
}

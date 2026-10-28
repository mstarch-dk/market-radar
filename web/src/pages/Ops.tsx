import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type DoctorCheck, type OpsEvent, type OpsJob, type OpsRequest, type OpsRow, type OpsRunningJob } from "../api/client";
import { PageHead } from "../components/cells";
import { DataTable, type Col } from "../components/DataTable";
import { JobProgressView } from "../components/JobProgress";
import { Badge } from "../components/ui";

const pad = (n: number) => String(n).padStart(2, "0");
/** A stored timestamp (UTC with its offset) in local time, as "YYYY-MM-DD HH:MM:SS". */
const ts = (iso: string | null | undefined) => {
  const d = iso ? new Date(iso) : null;
  if (!d || Number.isNaN(d.getTime())) return iso ?? "–";
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
};
const ms = (v: number | null | undefined) => (v == null ? "–" : `${Math.round(v).toLocaleString()} ms`);
const LEVEL_KIND: Record<string, string> = { info: "", warn: "warn", error: "neg" };
const JOB_KIND: Record<string, string> = { done: "pos", failed: "neg", running: "accent", interrupted: "warn" };
const CHECK_KIND: Record<string, string> = { ok: "pos", warn: "warn", fail: "neg", info: "" };

/** Requests per day as small bars (counts, not a direction: no up/down colour). */
function DayBars({ values, dates }: { values: number[]; dates: string[] }) {
  const w = 6, gap = 2, h = 24;
  const hi = Math.max(1, ...values);
  return (
    <svg width={values.length * (w + gap)} height={h} className="daybars" role="img"
      aria-label={values.map((v, i) => `${dates[i]}: ${v}`).join(", ")}>
      {values.map((v, i) => {
        const bh = v ? Math.max(2, (v / hi) * h) : 1;
        return <rect key={i} x={i * (w + gap)} y={h - bh} width={w} height={bh} rx={1}
          fill={v ? "var(--accent)" : "var(--line)"}><title>{`${dates[i]}: ${v.toLocaleString()}`}</title></rect>;
      })}
    </svg>
  );
}

function hostCols(dates: string[]): Col<OpsRow>[] {
  return [
    { key: "host", label: "Host", align: "l", sort: (r) => r.host, search: (r) => `${r.host} ${r.source ?? ""}`,
      filter: { kind: "enum" }, render: (r) => <span className="mono small">{r.host}</span> },
    { key: "source", label: "Source", align: "l", sort: (r) => r.source ?? "", filter: { kind: "enum", value: (r) => r.source ?? "(none)" },
      render: (r) => r.source ?? <span className="muted">–</span> },
    { key: "requests", label: "Requests", sort: (r) => r.requests, render: (r) => r.requests.toLocaleString() },
    { key: "error_pct", label: "Errors", sort: (r) => r.error_pct, help: "ops_errors",
      render: (r) => <span className={r.errors ? "neg" : "muted"}>{r.errors.toLocaleString()} ({r.error_pct.toFixed(1)}%)</span> },
    { key: "throttled", label: "429s", sort: (r) => r.throttled, help: "ops_429",
      render: (r) => <span className={r.throttled ? "warn-text" : "muted"}>{r.throttled}</span> },
    { key: "p50", label: "p50", sort: (r) => r.p50_ms, help: "ops_latency", render: (r) => ms(r.p50_ms) },
    { key: "p95", label: "p95", sort: (r) => r.p95_ms, help: "ops_latency", render: (r) => ms(r.p95_ms) },
    { key: "today", label: "Today / budget", sort: (r) => r.today, help: "ops_budget",
      render: (r) => <span className={r.budget != null && r.today > r.budget ? "neg" : ""}>
        {r.today.toLocaleString()}{r.budget != null ? <span className="muted"> / {r.budget.toLocaleString()}</span> : null}</span> },
    { key: "daily", label: "Per day", csv: false, render: (r) => <DayBars values={r.daily} dates={dates} /> },
    { key: "last", label: "Last request", sort: (r) => r.last, render: (r) => <span className="small">{ts(r.last)}</span> },
    { key: "last_error", label: "Last error", align: "l", sort: (r) => r.last_error_at,
      render: (r) => r.last_error
        ? <div className="wrap small"><span className="neg">{r.last_error}</span><br /><span className="muted">{ts(r.last_error_at)}</span></div>
        : <span className="muted">–</span> },
  ];
}

const eventCols: Col<OpsEvent>[] = [
  { key: "ts", label: "When", sort: (e) => e.ts, render: (e) => <span className="small">{ts(e.ts)}</span> },
  { key: "level", label: "Level", align: "l", sort: (e) => e.level, filter: { kind: "enum" },
    render: (e) => <Badge kind={LEVEL_KIND[e.level]}>{e.level}</Badge> },
  { key: "kind", label: "Kind", align: "l", sort: (e) => e.kind, filter: { kind: "enum" }, help: "ops_kind", render: (e) => e.kind },
  { key: "source", label: "Source", align: "l", sort: (e) => e.source ?? "", filter: { kind: "enum", value: (e) => e.source ?? "(none)" },
    render: (e) => e.source ?? <span className="muted">–</span> },
  { key: "message", label: "Message", align: "l", search: (e) => `${e.message} ${e.source ?? ""}`,
    render: (e) => <div className="wrap">{e.message}{e.detail && (
      <details className="ops-detail"><summary className="small muted">Traceback</summary><pre>{e.detail}</pre></details>)}</div> },
  { key: "job", label: "Job", sort: (e) => e.job_id, render: (e) => e.job_id != null ? `#${e.job_id}` : <span className="muted">–</span> },
];

const requestCols: Col<OpsRequest>[] = [
  { key: "ts", label: "When", sort: (r) => r.ts, render: (r) => <span className="small">{ts(r.ts)}</span> },
  { key: "host", label: "Host", align: "l", sort: (r) => r.host, filter: { kind: "enum" }, search: (r) => `${r.host}${r.path}`,
    render: (r) => <span className="mono small">{r.host}</span> },
  { key: "path", label: "Path", align: "l", render: (r) => <span className="mono small wrap">{r.method} {r.path}</span> },
  { key: "source", label: "Source", align: "l", sort: (r) => r.source ?? "", filter: { kind: "enum", value: (r) => r.source ?? "(none)" },
    render: (r) => r.source ?? <span className="muted">–</span> },
  { key: "status", label: "Status", sort: (r) => r.status, filter: { kind: "enum", value: (r) => (r.status == null ? "no answer" : String(r.status)) },
    render: (r) => <span className={r.ok ? "" : "neg"}>{r.status ?? "–"}</span> },
  { key: "dur", label: "Time", sort: (r) => r.duration_ms, render: (r) => ms(r.duration_ms) },
  { key: "attempt", label: "Try", sort: (r) => r.attempt, render: (r) => r.attempt },
  { key: "error", label: "Error", align: "l", render: (r) => r.error ? <span className="neg small wrap">{r.error}</span> : "" },
];

function JobLog({ id }: { id: number }) {
  const q = useQuery({ queryKey: ["ops-job", id], queryFn: () => api.opsJob(id) });
  if (q.isPending) return <p className="muted small">Loading…</p>;
  if (q.isError) return <p className="neg small">Couldn&apos;t load: {q.error.message}</p>;
  const j = q.data;
  return (
    <div className="up-log">
      <p className="small muted">{j.requests.toLocaleString()} requests, {j.errors.toLocaleString()} failed.</p>
      {j.progress && <JobProgressView p={j.progress} />}
      {j.log.length ? <pre>{j.log.join("\n")}</pre> : <p className="small muted">No log lines were kept for this job.</p>}
    </div>
  );
}

function Jobs({ jobs }: { jobs: OpsJob[] }) {
  const [open, setOpen] = useState<number | null>(null);
  if (!jobs.length) return <p className="note muted">No jobs recorded yet: they appear after the next update or discovery scan.</p>;
  return (
    <div className="card scroll">
      <table className="t">
        <thead><tr><th className="l">Job</th><th className="l">Kind</th><th className="l">Status</th><th>Started</th><th>Took</th><th className="l">Error</th><th /></tr></thead>
        <tbody>
          {jobs.map((j) => (
            <Fragment key={j.id}>
              <tr>
                <td className="l">#{j.id}</td>
                <td className="l">{j.kind}</td>
                <td className="l"><Badge kind={JOB_KIND[j.status] ?? ""}>{j.status}</Badge></td>
                <td>{ts(j.started)}</td>
                <td>{j.duration_s == null ? "–" : j.duration_s < 90 ? `${Math.round(j.duration_s)} s` : `${(j.duration_s / 60).toFixed(1)} min`}</td>
                <td className="l"><span className="neg small">{j.error ?? ""}</span></td>
                <td><button type="button" className="btn small" aria-expanded={open === j.id}
                  onClick={() => setOpen(open === j.id ? null : j.id)}>{open === j.id ? "Hide log" : "Log"}</button></td>
              </tr>
              {open === j.id && <tr><td colSpan={7} className="l"><JobLog id={j.id} /></td></tr>}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Doctor() {
  const [probe, setProbe] = useState<boolean | null>(null);
  const q = useQuery({ queryKey: ["ops-doctor", probe], queryFn: () => api.opsDoctor(!!probe), enabled: probe !== null });
  const qc = useQueryClient();
  const run = (p: boolean) => {
    setProbe(p);
    qc.invalidateQueries({ queryKey: ["ops-doctor", p] });
  };
  return (
    <div className="card">
      <div className="up-row">
        <button type="button" className="btn" onClick={() => run(false)} disabled={q.isFetching}>Check the setup</button>
        <button type="button" className="btn" onClick={() => run(true)} disabled={q.isFetching}>Check + contact every source</button>
        <span className="small muted">{q.isFetching ? "Checking…" : "The same checks as uv run radar doctor. Contacting the sources takes a few seconds."}</span>
      </div>
      {q.isError && <p className="neg small">Couldn&apos;t run the checks: {q.error.message}</p>}
      {q.data && (
        <table className="t">
          <tbody>
            {q.data.map((c: DoctorCheck) => (
              <tr key={c.name}>
                <td className="l"><Badge kind={CHECK_KIND[c.status]}>{c.status}</Badge></td>
                <td className="l"><b>{c.name}</b></td>
                <td className="l wrap">{c.detail}{c.fix && c.status !== "ok" && c.status !== "info" && <><br /><span className="muted small">→ {c.fix}</span></>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

/** Who runs a job (the operations log's kind). */
const KIND_LABEL: Record<string, string> = {
  update: "Data update (the app or Claude)", cli_run: "radar run (a terminal)", cli_update: "radar update (a terminal)",
  discover: "Discovery scan (the app)", cli_discover: "radar discover (a terminal)", report: "Rebuilding the readings (the app or Claude)",
  cli_report: "radar report (a terminal)", study: "A study",
};
const ago = (s: number | null | undefined) => (s == null ? "never" : s < 90 ? `${Math.round(s)} s ago` : `${Math.round(s / 60)} min ago`);

/** The jobs running now, whichever process runs them, with their step, phase, problems so far and log tail. */
function RunningNow({ jobs }: { jobs: OpsRunningJob[] }) {
  if (!jobs.length) return null;
  return (
    <>
      <h2>Running now</h2>
      {jobs.map((j) => (
        <div key={j.id} className="card running-job" aria-live="polite">
          <div className="up-row">
            <b>{KIND_LABEL[j.kind] ?? j.kind}</b>
            <span className="small muted">#{j.id} · started {ts(j.started)} · {j.requests.toLocaleString()} requests
              {j.errors > 0 && <span className="neg">, {j.errors.toLocaleString()} failed</span>} · last sign of life {ago(j.quiet_s)}</span>
            {j.stale && <Badge kind="warn">not responding</Badge>}
          </div>
          {j.stale && (
            <p className="small warn-text">No sign of life for a few minutes: the process that ran it may have stopped (a closed terminal, a
              crash). If nothing else is running, a new update can be started; it is refused while the old one still holds its lock.</p>
          )}
          {j.progress ? <JobProgressView p={j.progress} /> : <p className="small muted">This job reports no progress (an older version runs it).</p>}
          {j.log.length > 0 && (
            <details className="up-log">
              <summary className="small muted">The last {j.log.length} log lines</summary>
              <pre>{j.log.join("\n")}</pre>
            </details>
          )}
        </div>
      ))}
    </>
  );
}

const WINDOWS = [1, 7, 30];

export function Ops() {
  const [params, setParams] = useSearchParams();
  const days = WINDOWS.includes(Number(params.get("days"))) ? Number(params.get("days")) : 7;
  const qc = useQueryClient();
  const summary = useQuery({ queryKey: ["ops-summary", days], queryFn: () => api.opsSummary(days), refetchInterval: 30_000 });
  const events = useQuery({ queryKey: ["ops-events"], queryFn: api.opsEvents, refetchInterval: 30_000 });
  const jobs = useQuery({ queryKey: ["ops-jobs"], queryFn: api.opsJobs, refetchInterval: 30_000 });
  // fast while something runs, so its steps and problems show as they happen
  const running = useQuery({ queryKey: ["ops-running"], queryFn: api.opsRunning,
    refetchInterval: (q) => ((q.state.data?.length ?? 0) > 0 ? 2_000 : 15_000) });
  const nRunning = running.data?.length ?? 0;
  const had = useRef(nRunning);
  useEffect(() => {                 // a job ended: the tiles, events and jobs now have its outcome
    if (nRunning < had.current) qc.invalidateQueries({ predicate: (q) => ["ops-summary", "ops-events", "ops-jobs"].includes(String(q.queryKey[0])) });
    had.current = nRunning;
  }, [nRunning, qc]);
  const [showRequests, setShowRequests] = useState(false);
  const requests = useQuery({ queryKey: ["ops-requests"], queryFn: api.opsRequests, enabled: showRequests });
  const clear = useMutation({
    mutationFn: api.clearCooldown,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ops-summary"] }),
  });
  const setDays = (d: number) => {
    const next = new URLSearchParams(params);
    next.set("days", String(d));
    setParams(next, { replace: true });
  };
  const s = summary.data;
  const lu = s?.last_update;

  return (
    <>
      <PageHead title="Operations">
        What the radar does behind the scenes: every request to an outside source (Yahoo, FRED, CFTC, …), failed updates and
        parse errors, server errors, and the update and scan jobs with their logs. Requests are paced per site so the
        radar doesn&apos;t get blocked; a site that keeps answering &ldquo;too many requests&rdquo; (HTTP 429) is paused for a while
        and its data stays as it was. Limits are in config/settings.yaml (<code>network:</code>); the log is kept in
        data/ops.db (<code>ops:</code> says for how long). This page is about the plumbing, not the markets.
      </PageHead>

      {running.data && <RunningNow jobs={running.data} />}

      {summary.isError && (
        <div className="error">Couldn&apos;t load the operations log: {summary.error.message}{" "}
          <button type="button" className="btn small" onClick={() => summary.refetch()}>Retry</button></div>
      )}
      {summary.isPending && <div className="skeleton" style={{ height: 120 }} aria-busy="true" />}
      {s && (
        <>
          <div className="tiles ops-tiles">
            <div className="tile">
              <span>Last update</span>
              {lu ? <><b><Badge kind={JOB_KIND[lu.status] ?? ""}>{lu.status}</Badge></b>
                <span>{ts(lu.started)}{lu.duration_s != null && ` · ${Math.round(lu.duration_s)} s`}</span></>
                : <b className="muted">none recorded</b>}
            </div>
            <div className="tile">
              <span>Requests, last 24 h</span>
              <b>{s.requests_24h.toLocaleString()}</b>
              <span className={s.errors_24h ? "neg" : ""}>{s.errors_24h.toLocaleString()} failed</span>
            </div>
            <div className="tile">
              <span>Error events, last 24 h</span>
              <b className={s.error_events_24h ? "neg" : ""}>{s.error_events_24h.toLocaleString()}</b>
              <span>failed sources, parse and server errors</span>
            </div>
            <div className="tile">
              <span>Paused sites</span>
              <b className={s.cooldowns.length ? "warn-text" : ""}>{s.cooldowns.length}</b>
              <span>{s.over_budget.length ? <span className="neg">over budget today: {s.over_budget.join(", ")}</span> : "none over budget today"}</span>
            </div>
          </div>

          {s.cooldowns.length > 0 && (
            <div className="notes" role="alert">
              {s.cooldowns.map((c) => (
                <div key={c.host} className="up-row">
                  <span><b className="mono">{c.host}</b> is paused until {ts(c.until)}: {c.reason ?? "rate limited"}
                    {c.strikes > 1 && ` (pause #${c.strikes} today, so it lasts longer)`}.</span>
                  <button type="button" className="btn small" disabled={clear.isPending} onClick={() => clear.mutate(c.host)}>Resume now</button>
                </div>
              ))}
              {clear.isError && <span className="neg small">{clear.error.message}</span>}
            </div>
          )}

          <h2>Sites and sources</h2>
          <div className="up-row">
            <span className="small muted">Window:</span>
            {WINDOWS.map((d) => (
              <button key={d} type="button" className={`btn small ${d === days ? "primary" : ""}`} aria-pressed={d === days}
                onClick={() => setDays(d)}>{d === 1 ? "24 h" : `${d} days`}</button>
            ))}
          </div>
          <div className="card">
            <DataTable id="ops" csvName="requests-by-host" rows={s.rows} cols={hostCols(s.dates)}
              rowKey={(r) => `${r.host}|${r.source ?? ""}`}
              empty={<p className="muted">No requests recorded in the last {days === 1 ? "24 hours" : `${days} days`}.</p>} />
          </div>
        </>
      )}

      <h2>Events</h2>
      <div className="card">
        {events.isError ? <p className="neg">Couldn&apos;t load events: {events.error.message}</p>
          : events.data ? <DataTable id="ev" csvName="events" rows={events.data} cols={eventCols} rowKey={(e) => String(e.id)}
            empty={<p className="muted">No events yet.</p>} />
          : <div className="skeleton" style={{ height: 120 }} aria-busy="true" />}
      </div>

      <h2>Jobs</h2>
      {jobs.isError ? <p className="neg">Couldn&apos;t load jobs: {jobs.error.message}</p>
        : jobs.data ? <Jobs jobs={jobs.data} /> : <div className="skeleton" style={{ height: 80 }} aria-busy="true" />}

      <h2>Recent requests</h2>
      <details className="card" open={showRequests} onToggle={(e) => setShowRequests((e.target as HTMLDetailsElement).open)}>
        <summary className="small muted">The last 300 requests, one by one (paths only: query strings and keys are never stored)</summary>
        {requests.isError && <p className="neg">Couldn&apos;t load: {requests.error.message}</p>}
        {requests.data && <DataTable id="rq" csvName="requests" rows={requests.data} cols={requestCols} rowKey={(r) => String(r.id)}
          empty={<p className="muted">No requests recorded yet.</p>} />}
      </details>

      <h2>Health checks</h2>
      <Doctor />
    </>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, type RegimeView, type VoteOption } from "../api/client";
import { Loaded, PageHead, Signal, regimeKind } from "../components/cells";
import { DataTable, type Col } from "../components/DataTable";
import { GaugeBadge, GaugeBar } from "../components/Gauge";
import { LineChart } from "../components/LineChart";
import { Term } from "../components/Term";
import { Badge } from "../components/ui";
import { date } from "../lib/format";

type Ind = RegimeView["indicators"][number];

const indCols: Col<Ind>[] = [
  { key: "name", label: "Indicator", align: "l", sort: (i) => i.name, search: (i) => `${i.name} ${i.note}`, render: (i) => i.name },
  { key: "value", label: "Reading", render: (i) => i.value, csv: (i) => i.value },
  { key: "status", label: "Vote", align: "l", sort: (i) => i.status, help: "signal", filter: { kind: "enum" },
    render: (i) => i.votes ? <Signal s={i.status} />
      : <span className="dim"><Signal s={i.status} /> <Badge>not voting</Badge></span> },
  { key: "gauge", label: "Reading, graded", align: "l", sort: (i) => i.gauge?.score, csv: (i) => i.gauge?.label,
    render: (i) => i.gauge
      ? <span className={i.status === "stale" ? "dim" : ""}><GaugeBadge g={i.gauge} name={i.name} /><GaugeBar g={i.gauge} /></span>
      : <span className="muted">–</span> },
  { key: "note", label: "Context", align: "l", csv: (i) => i.note,
    render: (i) => <span className="wrap muted">{i.note}{i.asof && <> · as of {date(i.asof)}</>}</span> },
];

/** Switches for the indicator groups that can be left out of the vote (settings.yaml regime.votes is the default). */
function VoteSwitches({ votes }: { votes: VoteOption[] }) {
  const qc = useQueryClient();
  const set = useMutation({
    mutationFn: (v: Record<string, boolean>) => api.setRegimeVotes(v),
    // the regime label also sets the stop width on holdings and ticker pages
    onSuccess: () => ["regime", "me", "context", "profile"].forEach((k) => qc.invalidateQueries({ queryKey: [k] })),
  });
  if (!votes.length) return null;
  return (
    <div className="card votes">
      <div className="sub"><Term k="not_voting">Counted in the vote</Term></div>
      {votes.map((v) => (
        <label key={v.group} className="check">
          <input type="checkbox" checked={v.on} disabled={set.isPending}
            onChange={(e) => set.mutate({ [v.group]: e.target.checked })} />
          {v.label}
          {v.on !== v.default && <span className="muted small"> (default: {v.default ? "on" : "off"})</span>}
        </label>
      ))}
      {set.isError && <span className="neg small">Not saved: {(set.error as Error).message}</span>}
      <p className="small muted">Your choice is saved on this computer and used everywhere the regime is: here, the stop
        levels and the next <code>radar report</code> (the market brief). Valuation is slow-moving: a stretched market can
        stay stretched for years, so it is off by default.</p>
    </div>
  );
}

export function Regime() {
  const q = useQuery({ queryKey: ["regime"], queryFn: api.regime, retry: false, staleTime: 5 * 60_000 });
  return (
    <Loaded q={q} title="Regime">
      {(d) => {
        const o = d.overall;
        const cr = d.coverage.regime;
        return (
          <>
            <PageHead title="Regime" asof={d.asof} generated={d.generated} ageDays={d.age_days} stale={d.stale} />
            <div className="card hero">
              <div>
                <div className="sub">Overall reading</div>
                <div className="big"><Badge kind={regimeKind(o.label)}>{o.label}</Badge></div>
              </div>
              <div className="sub">
                {o.on} risk-on · {o.off} risk-off · {o.neutral} neutral/informational
                {o.na > 0 && <> · {o.na} without data</>}{o.stale > 0 && <> · {o.stale} stale</>} · net {o.net.toFixed(2)}
                {(o.not_voting ?? 0) > 0 && <> · {o.not_voting} shown but <Term k="not_voting">not voting</Term></>}
              </div>
            </div>
            <VoteSwitches votes={d.votes ?? []} />
            <p className="coverage-strip">
              <b>{cr.current} of {cr.total}</b> indicators have current data
              {cr.na.length > 0 && <> · <span className="warn">{cr.na.length} without data ({cr.na.join(", ")})</span></>}
              {cr.stale.length > 0 && <> · <span className="warn">{cr.stale.length} stale, not counted ({cr.stale.join(", ")})</span></>}
              {d.coverage.oldest && <> · oldest input: {d.coverage.oldest.name}, {date(d.coverage.oldest.asof)} ({d.coverage.oldest.age_days} days)</>}
              {d.coverage.failing.length > 0 && <> · <span className="neg">last update failed: {d.coverage.failing.join(", ")}</span></>}
              {" "}· <Link to="/data">Data &amp; coverage →</Link>
            </p>
            <h2>Indicators</h2>
            <div className="card"><DataTable id="ind" csvName="regime" rows={d.indicators} cols={indCols} rowKey={(i) => i.name} /></div>
            <h2>Charts</h2>
            <div className="grid charts">
              {d.charts.map((c) => <LineChart key={c.title} chart={c} />)}
            </div>
          </>
        );
      }}
    </Loaded>
  );
}

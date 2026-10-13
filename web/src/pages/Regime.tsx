import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Loaded, PageHead, Signal, regimeKind } from "../components/cells";
import { LineChart } from "../components/LineChart";
import { Badge } from "../components/ui";
import { date } from "../lib/format";

export function Regime() {
  const q = useQuery({ queryKey: ["regime"], queryFn: api.regime, retry: false, staleTime: 5 * 60_000 });
  return (
    <Loaded q={q} title="Regime">
      {(d) => {
        const o = d.overall;
        const cr = d.coverage.regime;
        return (
          <>
            <PageHead title="Regime" asof={d.asof} generated={d.generated} />
            <div className="card hero">
              <div>
                <div className="sub">Overall reading</div>
                <div className="big"><Badge kind={regimeKind(o.label)}>{o.label}</Badge></div>
              </div>
              <div className="sub">
                {o.on} risk-on · {o.off} risk-off · {o.neutral} neutral/informational
                {o.na > 0 && <> · {o.na} without data</>}{o.stale > 0 && <> · {o.stale} stale</>} · net {o.net.toFixed(2)}
              </div>
            </div>
            <p className="coverage-strip">
              <b>{cr.current} of {cr.total}</b> indicators have current data
              {cr.na.length > 0 && <> · <span className="warn">{cr.na.length} without data ({cr.na.join(", ")})</span></>}
              {cr.stale.length > 0 && <> · <span className="warn">{cr.stale.length} stale, not counted ({cr.stale.join(", ")})</span></>}
              {d.coverage.oldest && <> · oldest input: {d.coverage.oldest.name}, {date(d.coverage.oldest.asof)} ({d.coverage.oldest.age_days} days)</>}
              {d.coverage.failing.length > 0 && <> · <span className="neg">last update failed: {d.coverage.failing.join(", ")}</span></>}
              {" "}· <Link to="/data">Data &amp; coverage →</Link>
            </p>
            <h2>Indicators</h2>
            <div className="card scroll">
              <table className="t dt">
                <thead><tr><th className="l">Indicator</th><th>Reading</th><th className="l">Signal</th><th className="l">Context</th></tr></thead>
                <tbody>
                  {d.indicators.map((i) => (
                    <tr key={i.name}>
                      <td className="l">{i.name}</td>
                      <td>{i.value}</td>
                      <td className="l"><Signal s={i.status} /></td>
                      <td className="l wrap muted">{i.note}{i.asof && <> · as of {date(i.asof)}</>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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

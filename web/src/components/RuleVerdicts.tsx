import type { RuleVerdict } from "../api/client";
import { SEVERITY_KIND, sortVerdicts, STATUS_KIND, STATUS_TEXT } from "../lib/rules";
import { Badge } from "./ui";

/** Your rules' verdicts on one action (or on what you hold now), breaks first: the rule, its severity, the
 *  evidence with its numbers and the way to comply. `compact` hides what complies or doesn't apply. */
export function RuleVerdicts({ rows, compact = false }: { rows: RuleVerdict[]; compact?: boolean }) {
  const shown = sortVerdicts(rows).filter((v) => !compact || !["complies", "not_applicable"].includes(v.status));
  const hidden = rows.length - shown.length;
  if (rows.length === 0) return <p className="small muted">No active rules.</p>;
  return (
    <>
      <table className="t rule-verdicts">
        <thead><tr><th>Verdict</th><th>Rule</th><th>What the radar sees</th></tr></thead>
        <tbody>
          {shown.map((v, i) => (
            <tr key={`${v.rule_id}-${v.symbol ?? ""}-${i}`} className={`rv-${v.status}`}>
              <td><Badge kind={STATUS_KIND[v.status]}>{STATUS_TEXT[v.status]}</Badge></td>
              <td>
                <div>{v.statement}</div>
                <div className="small muted"><Badge kind={SEVERITY_KIND[v.severity]}>{v.severity}</Badge> {v.kind_label}</div>
              </td>
              <td>
                <div className="small">{v.message}</div>
                {v.comply && <div className="small"><b>To comply:</b> {v.comply}</div>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {hidden > 0 && <p className="small muted">{hidden} more rule(s) comply or don&apos;t apply.</p>}
    </>
  );
}

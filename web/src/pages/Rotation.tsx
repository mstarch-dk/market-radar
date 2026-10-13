import { useQuery } from "@tanstack/react-query";
import { api, type RotationGroup, type RotationRow } from "../api/client";
import { Check, Loaded, PageHead, Pct, Quadrant, RankChange } from "../components/cells";
import { DataTable, type Col } from "../components/DataTable";
import { RrgChart } from "../components/RrgChart";
import { TickerLink } from "../components/TickerLink";
import { Badge } from "../components/ui";
import { date } from "../lib/format";

/** ETF groups shown on the Themes page; every other group is a sector/region rotation. */
export const THEME_GROUPS = ["themes", "factors"];

const base: Col<RotationRow>[] = [
  { key: "name", label: "Name", align: "l", sort: (r) => r.name, render: (r) => <TickerLink symbol={r.ticker} name={r.name} nameFirst /> },
  { key: "rank", label: "#", sort: (r) => r.rank, render: (r) => r.rank ?? "–", title: "Rank in the group by relative strength" },
  { key: "chg", label: "Δ rank", sort: (r) => r.rank_change, render: (r) => <RankChange v={r.rank_change} /> },
  { key: "quadrant", label: "Quadrant", align: "l", sort: (r) => r.quadrant, render: (r) => <Quadrant q={r.quadrant} /> },
];
const rel: Col<RotationRow>[] = [
  { key: "rel_r1m", label: "Rel 1m", sort: (r) => r.rel_r1m, render: (r) => <Pct v={r.rel_r1m} /> },
  { key: "rel_r3m", label: "Rel 3m", sort: (r) => r.rel_r3m, render: (r) => <Pct v={r.rel_r3m} /> },
  { key: "rel_r6m", label: "Rel 6m", sort: (r) => r.rel_r6m, render: (r) => <Pct v={r.rel_r6m} /> },
];
const abs3: Col<RotationRow> = { key: "r3m", label: "Abs 3m", sort: (r) => r.r3m, render: (r) => <Pct v={r.r3m} /> };
const above: Col<RotationRow> = { key: "above200", label: ">200d", sort: (r) => r.above200, render: (r) => <Check v={r.above200} /> };
const local: Col<RotationRow> = {
  key: "local", label: "vs home mkt", align: "l", sort: (r) => r.quadrant_local, render: (r) => <Quadrant q={r.quadrant_local} />,
  title: "Quadrant against the group's home benchmark",
};

function ucitsCols(year: string | null | undefined): Col<RotationRow>[] {
  return [
    { key: "ucits", label: "UCITS alternative", align: "l", sort: (r) => r.ucits_name ?? r.ucits,
      render: (r) => r.ucits ? <TickerLink symbol={r.ucits} name={r.ucits_name} nameFirst /> : <span className="muted">–</span> },
    { key: "isin", label: "ISIN", align: "l", sort: (r) => r.isin, render: (r) => r.isin ?? <span className="muted">–</span> },
    { key: "pl", label: `Positive list ${year ?? ""}`, align: "l", sort: (r) => r.positive_list,
      render: (r) => r.positive_list === "yes" ? <Badge kind="pos">yes</Badge> : r.positive_list === "no" ? <Badge kind="neg">no</Badge>
        : <span className="muted">?</span> },
  ];
}

export function GroupSection({ g, tail, themes, plYear }: { g: RotationGroup; tail: number; themes: boolean; plYear?: string | null }) {
  const cols = themes
    ? [...base, ...rel, above, ...ucitsCols(plYear)]
    : [...base, ...(g.rrg_local ? [local] : []), ...rel, abs3, above];
  return (
    <section id={g.key} className="group">
      <h2>{g.label}</h2>
      <div className="grid wide-charts">
        <RrgChart trails={g.rrg} title={`${g.label} vs ACWI – last ${tail} weeks`} />
        {g.rrg_local && <RrgChart trails={g.rrg_local} title={`${g.label} vs ${g.local_benchmark} – last ${tail} weeks`} />}
      </div>
      <div className="card"><DataTable rows={g.rows} cols={cols} rowKey={(r) => r.ticker} /></div>
    </section>
  );
}

export function Rotation() {
  const q = useQuery({ queryKey: ["rotation"], queryFn: api.rotation, retry: false, staleTime: 5 * 60_000 });
  return (
    <Loaded q={q} title="Sector rotation">
      {(d) => {
        const groups = d.groups.filter((g) => !THEME_GROUPS.includes(g.key));
        return (
          <>
            <PageHead title="Sector rotation" asof={d.asof} generated={d.generated}>
              The rotation graph plots each ETF&apos;s <b>relative trend</b> vs ACWI (x) against its <b>acceleration</b> (y).
              Rotation usually runs clockwise: Improving → Leading → Weakening → Lagging. Names moving from <b>Improving into
              Leading</b> are typical early momentum candidates. Rank change is compared with the snapshot from{" "}
              {d.prev ? date(d.prev) : "– (no earlier snapshot yet)"}.
            </PageHead>
            <nav className="jump">{groups.map((g) => <a key={g.key} href={`#${g.key}`}>{g.label}</a>)}</nav>
            {groups.map((g) => <GroupSection key={g.key} g={g} tail={d.tail_weeks} themes={false} />)}
          </>
        );
      }}
    </Loaded>
  );
}

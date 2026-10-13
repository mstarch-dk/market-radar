import { useQuery } from "@tanstack/react-query";
import { api, type RotationGroup, type RotationRow } from "../api/client";
import { Check, Loaded, PageHead, Pct, Quadrant, RankChange } from "../components/cells";
import { DataTable, type Col } from "../components/DataTable";
import { RrgChart } from "../components/RrgChart";
import { TickerLink } from "../components/TickerLink";
import { Badge } from "../components/ui";
import { date, num } from "../lib/format";

/** ETF groups shown on the Themes page; every other group is a sector/region rotation. */
export const THEME_GROUPS = ["themes", "factors"];

const base: Col<RotationRow>[] = [
  { key: "name", label: "Name", align: "l", sort: (r) => r.name, search: (r) => `${r.name} ${r.ticker} ${r.ucits ?? ""} ${r.ucits_name ?? ""}`,
    render: (r) => <TickerLink symbol={r.ticker} name={r.name} nameFirst />, csv: (r) => r.ticker },
  { key: "rank", label: "#", sort: (r) => r.rank, render: (r) => r.rank ?? "–", help: "rank" },
  { key: "chg", label: "Δ rank", name: "Rank change", sort: (r) => r.rank_change, render: (r) => <RankChange v={r.rank_change} />, help: "rank_change" },
  { key: "quadrant", label: "Quadrant", align: "l", sort: (r) => r.quadrant, render: (r) => <Quadrant q={r.quadrant} />,
    help: "quadrant", filter: { kind: "enum" } },
];
const rel: Col<RotationRow>[] = [
  { key: "rel_r1m", label: "Rel 1m", sort: (r) => r.rel_r1m, render: (r) => <Pct v={r.rel_r1m} />, help: "rel_r1m", heat: true },
  { key: "rel_r3m", label: "Rel 3m", sort: (r) => r.rel_r3m, render: (r) => <Pct v={r.rel_r3m} />, help: "rel_r3m", heat: true,
    filter: { kind: "range", unit: "pct" } },
  { key: "rel_r6m", label: "Rel 6m", sort: (r) => r.rel_r6m, render: (r) => <Pct v={r.rel_r6m} />, help: "rel_r6m", heat: true },
];
const abs3: Col<RotationRow> = { key: "r3m", label: "Abs 3m", sort: (r) => r.r3m, render: (r) => <Pct v={r.r3m} />, help: "abs_r3m" };
const above: Col<RotationRow> = { key: "above200", label: ">200d", name: "Above 200d", sort: (r) => r.above200,
  render: (r) => <Check v={r.above200} />, help: "above200", filter: { kind: "bool" } };
const rs: Col<RotationRow>[] = [
  { key: "rs_ratio", label: "RS-Ratio", sort: (r) => r.rs_ratio, render: (r) => num(r.rs_ratio, 2), help: "rs_ratio", hidden: true },
  { key: "rs_mom", label: "RS-Mom", name: "RS-Momentum", sort: (r) => r.rs_mom, render: (r) => num(r.rs_mom, 2), help: "rs_mom", hidden: true },
];
const local: Col<RotationRow> = {
  key: "local", label: "vs home mkt", name: "Quadrant vs home market", align: "l", sort: (r) => r.quadrant_local,
  render: (r) => <Quadrant q={r.quadrant_local} />, help: "quadrant_local", filter: { kind: "enum" },
};

function ucitsCols(year: string | null | undefined): Col<RotationRow>[] {
  return [
    { key: "ucits", label: "UCITS alternative", align: "l", sort: (r) => r.ucits_name ?? r.ucits, help: "ucits", csv: (r) => r.ucits,
      render: (r) => r.ucits ? <TickerLink symbol={r.ucits} name={r.ucits_name} nameFirst /> : <span className="muted">–</span>,
      filter: { kind: "bool", value: (r) => Boolean(r.ucits) } },
    { key: "isin", label: "ISIN", align: "l", sort: (r) => r.isin, render: (r) => r.isin ?? <span className="muted">–</span>, help: "isin",
      search: (r) => r.isin },
    { key: "pl", label: `Positive list ${year ?? ""}`, name: "Positive list", align: "l", sort: (r) => r.positive_list, help: "positive_list",
      filter: { kind: "enum" },
      render: (r) => r.positive_list === "yes" ? <Badge kind="pos">yes</Badge> : r.positive_list === "no" ? <Badge kind="neg">no</Badge>
        : <span className="muted">?</span> },
  ];
}

export function GroupSection({ g, tail, themes, plYear }: { g: RotationGroup; tail: number; themes: boolean; plYear?: string | null }) {
  const cols = themes
    ? [...base, ...rel, above, ...rs, ...ucitsCols(plYear)]
    : [...base, ...(g.rrg_local ? [local] : []), ...rel, abs3, above, ...rs];
  return (
    <section id={g.key} className="group">
      <h2>{g.label}</h2>
      <div className="grid wide-charts">
        <RrgChart trails={g.rrg} title={`${g.label} vs ACWI – last ${tail} weeks`} />
        {g.rrg_local && <RrgChart trails={g.rrg_local} title={`${g.label} vs ${g.local_benchmark} – last ${tail} weeks`} />}
      </div>
      <div className="card"><DataTable id={g.key} csvName={`rotation-${g.key}`} rows={g.rows} cols={cols} rowKey={(r) => r.ticker} /></div>
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

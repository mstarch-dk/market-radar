import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api, type CompareRow } from "../api/client";
import { Loaded, PageHead, Pct } from "../components/cells";
import { DataTable, type Col } from "../components/DataTable";
import { LineChart } from "../components/LineChart";
import { usePortfolioSel } from "../components/PortfolioPicker";
import { Badge } from "../components/ui";
import { date, num } from "../lib/format";
import { DEFAULT_SEL, formatSel, isDefaultSel, type PortfolioSel } from "../lib/portfolioSel";

const p = (r: CompareRow, k: string) => r.stats?.periods[k];
const cols: Col<CompareRow>[] = [
  { key: "label", label: "Portfolio", align: "l", sort: (r) => r.label, render: (r) => (
    <span>{r.label}{" "}
      {r.kind === "tag" ? <span className="muted small">({r.members.join(", ") || "no portfolios"})</span>
        : r.portfolio?.mode === "virtual" && <Badge kind="warn">virtual</Badge>}</span>) },
  { key: "start", label: "From", align: "l", sort: (r) => r.stats?.start, render: (r) => date(r.stats?.start) },
  { key: "value", label: "Value (DKK)", sort: (r) => r.stats?.value_dkk, render: (r) => num(r.stats?.value_dkk, 0) },
  { key: "twr", label: "TWR", help: "twr", sort: (r) => r.stats?.twr_total, render: (r) => <Pct v={r.stats?.twr_total} />, heat: true },
  { key: "twr_ann", label: "TWR p.a.", help: "twr", sort: (r) => r.stats?.twr_ann, render: (r) => <Pct v={r.stats?.twr_ann} /> },
  { key: "mwr", label: "MWR p.a.", help: "mwr", sort: (r) => r.stats?.mwr_ann, render: (r) => <Pct v={r.stats?.mwr_ann} /> },
  { key: "acwi", label: "ACWI", help: "acwi_twr", sort: (r) => r.stats?.acwi_twr_total, render: (r) => <Pct v={r.stats?.acwi_twr_total} /> },
  { key: "excess", label: "vs ACWI", help: "excess_twr", sort: (r) => r.stats?.excess_twr, render: (r) => <Pct v={r.stats?.excess_twr} />, heat: true },
  { key: "dd", label: "Max drawdown", help: "max_drawdown", sort: (r) => r.stats?.max_drawdown, render: (r) => <Pct v={r.stats?.max_drawdown} /> },
  { key: "vol", label: "Volatility p.a.", sort: (r) => r.stats?.vol_ann, render: (r) => <Pct v={r.stats?.vol_ann} />, hidden: true },
  { key: "3m", label: "3m", sort: (r) => p(r, "3m")?.portfolio, render: (r) => <Pct v={p(r, "3m")?.portfolio} />, hidden: true },
  { key: "ytd", label: "YTD", sort: (r) => p(r, "ytd")?.portfolio, render: (r) => <Pct v={p(r, "ytd")?.portfolio} />, hidden: true },
  { key: "1y", label: "1y", sort: (r) => p(r, "1y")?.portfolio, render: (r) => <Pct v={p(r, "1y")?.portfolio} />, hidden: true },
  { key: "funding", label: "Cash", help: "funding", align: "l", sort: (r) => r.funding, render: (r) => <span className="muted small">{r.funding}</span> },
];

/** Choose the lines to compare: portfolios (real and virtual) and tag groups, kept in the URL. */
function Lines({ sel, onChange }: { sel: PortfolioSel; onChange: (s: PortfolioSel) => void }) {
  const { data: portfolios = [] } = useQuery({ queryKey: ["portfolios"], queryFn: api.portfolios });
  const { data: tags = [] } = useQuery({ queryKey: ["portfolio-tags"], queryFn: api.tags });
  const ids = "ids" in sel ? sel.ids : [];
  const chosenTags = "tags" in sel ? sel.tags : [];
  const toggle = (next: { ids: number[]; tags: string[] }) =>
    onChange(next.ids.length || next.tags.length ? next : DEFAULT_SEL);
  const withRows = portfolios.filter((x) => x.n_tx > 0);
  return (
    <div className="perf-lines small">
      <span className="muted">Compare:</span>
      {withRows.map((x) => (
        <label key={x.id} className="chip-check">
          <input type="checkbox" checked={ids.includes(x.id)}
            onChange={(e) => toggle({ ids: e.target.checked ? [...ids, x.id] : ids.filter((i) => i !== x.id), tags: chosenTags })} />
          {x.name}{x.mode === "virtual" ? " (virtual)" : ""}
        </label>
      ))}
      {tags.map((t) => (
        <label key={t.tag} className="chip-check">
          <input type="checkbox" checked={chosenTags.includes(t.tag)}
            onChange={(e) => toggle({ ids, tags: e.target.checked ? [...chosenTags, t.tag] : chosenTags.filter((x) => x !== t.tag) })} />
          #{t.tag} <span className="muted">(pooled)</span>
        </label>
      ))}
      {!isDefaultSel(sel) && <button type="button" className="linkish" onClick={() => onChange(DEFAULT_SEL)}>your real portfolios</button>}
    </div>
  );
}

/** Portfolio returns over time in DKK, against ACWI: real and virtual portfolios, and tag groups for A/B tests. */
export function Performance() {
  const [sel, setSel] = usePortfolioSel();
  const [params, setParams] = useSearchParams();
  const start = params.get("from") ?? "";
  const setStart = (v: string) => setParams((p) => {
    const next = new URLSearchParams(p);
    if (v) next.set("from", v); else next.delete("from");
    return next;
  }, { replace: true });
  const q = useQuery({ queryKey: ["comparison", formatSel(sel), start],
    queryFn: () => api.compare("ids" in sel ? sel : undefined, start || undefined), retry: false });
  return (
    <Loaded q={q} title="Returns over time">
      {(d) => (
        <>
          <PageHead title="Returns over time" asof={d.asof}>
            Each portfolio&apos;s <b>time-weighted return in DKK</b> (the investments&apos; own performance, independent of when
            money came in) next to ACWI&apos;s over the same period, from a common start where every line is rebased to 100.
            Tick a tag to pool its portfolios into one line: two tags make an A/B test. A missing price or exchange rate
            leaves a gap, never a zero. Analysis, not advice.
          </PageHead>
          <Lines sel={sel} onChange={setSel} />
          <p className="small">
            <label>From <input type="date" value={start || d.start || ""} onChange={(e) => setStart(e.target.value)} /></label>
            {start && <button type="button" className="linkish" onClick={() => setStart("")}>the common start</button>}
          </p>
          {d.rows.length === 0
            ? <p className="note">Nothing to compare yet. <Link to="/portfolio">Add trades on the Portfolio page</Link>, or tick a portfolio above.</p>
            : (
              <>
                <LineChart chart={d.chart} height={320} />
                <div className="card"><DataTable id="perf" csvName="returns" rows={d.rows} cols={cols} rowKey={(r) => r.label} /></div>
                <ul className="small muted perf-notes">
                  {d.rows.flatMap((r) => [...r.notes, ...r.missing].map((n) => <li key={r.label + n}><b>{r.label}</b>: {n}</li>))}
                </ul>
              </>
            )}
        </>
      )}
    </Loaded>
  );
}

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type AttributionView } from "../api/client";
import { Pct } from "../components/cells";
import { DataTable, type Col } from "../components/DataTable";
import { Tabs } from "../components/Tabs";
import { Term } from "../components/Term";
import { TickerLink } from "../components/TickerLink";
import { Badge, Card, KV } from "../components/ui";
import { EFFECTS, extent, stack, waterfall, type Effect, type Step } from "../lib/attribution";
import { date, isNum, num, pct, type Maybe } from "../lib/format";
import type { GlossaryKey } from "../lib/glossary";
import { pageChapter, useGuideTree } from "../lib/guide";
import { formatSel, type PortfolioSel } from "../lib/portfolioSel";

type Dim = "sector" | "region";
type DimView = AttributionView["dims"][string];
type Row = DimView["rows"][number];
type Month = DimView["months"][number];
type CcyRow = NonNullable<AttributionView["currency"]>["rows"][number];

const DIMS: [Dim, string][] = [["sector", "By sector"], ["region", "By region"]];
const EFFECT_LABEL: Record<Effect, string> = {
  allocation: "Allocation", selection: "Selection", interaction: "Interaction", currency: "Currency", cross: "Cross",
};
const EFFECT_HELP: Record<Effect, GlossaryKey> = {
  allocation: "attr_allocation", selection: "attr_selection", interaction: "attr_interaction", currency: "attr_currency",
  cross: "attr_cross",
};
const EFFECT_COLOR: Record<Effect, string> = {
  allocation: "var(--s1)", selection: "var(--s2)", interaction: "var(--s3)", currency: "var(--s4)", cross: "var(--s6)",
};
const PROXY = "Benchmark segments are ETFs that track MSCI World sectors and country indices, not ACWI's own segments: "
  + "their gap to ACWI is shown as its own line, not hidden in the effects.";

const segLabel = (k: string) => k === "unclassified" ? "unclassified (own segment)" : k;

const rowCols: Col<Row>[] = [
  { key: "key", label: "Segment", align: "l", sort: (r) => r.key, search: (r) => r.key, render: (r) => (
    <span className={r.key === "cash" || r.key === "unclassified" ? "muted" : ""}>{segLabel(r.key)}</span>) },
  { key: "w_p", label: "Weight", name: "Average weight", sort: (r) => r.w_p, render: (r) => pct(r.w_p, 1, false) },
  { key: "w_b", label: "ACWI", name: "ACWI's average weight", sort: (r) => r.w_b, render: (r) => pct(r.w_b, 1, false) },
  { key: "r_p", label: "Return", name: "Your return in the segment (local)", sort: (r) => r.r_p,
    render: (r) => isNum(r.r_p) ? <Pct v={r.r_p} /> : <span className="muted" title="Not held in the period">–</span> },
  { key: "r_b", label: "ACWI return", name: "The segment's benchmark return (local)", sort: (r) => r.r_b,
    render: (r) => isNum(r.r_b) ? <Pct v={r.r_b} /> : <span className="muted" title="No benchmark segment">–</span> },
  { key: "allocation", label: "Allocation", help: "attr_allocation", sort: (r) => r.allocation, render: (r) => <Pct v={r.allocation} digits={2} /> },
  { key: "selection", label: "Selection", help: "attr_selection", sort: (r) => r.selection, render: (r) => <Pct v={r.selection} digits={2} /> },
  { key: "interaction", label: "Interaction", help: "attr_interaction", sort: (r) => r.interaction, render: (r) => <Pct v={r.interaction} digits={2} /> },
  { key: "total", label: "Total", sort: (r) => r.total, render: (r) => <b><Pct v={r.total} digits={2} /></b>, heat: true },
];

const monthCols: Col<Month>[] = [
  { key: "month", label: "Month", align: "l", sort: (m) => m.month, render: (m) => (
    <span>{m.month} {m.basis === "back-drifted" && <Badge kind="warn" title="ACWI's weights rolled back from the first weekly record">back-drifted</Badge>}</span>) },
  ...EFFECTS.map((e): Col<Month> => ({ key: e, label: EFFECT_LABEL[e], help: EFFECT_HELP[e], sort: (m) => m[e],
    render: (m) => <Pct v={m[e]} digits={2} /> })),
  { key: "active", label: "Active", help: "attr_active", sort: (m) => m.active, render: (m) => <b><Pct v={m.active} digits={2} /></b> },
  { key: "days", label: "Days", sort: (m) => m.days, render: (m) => m.days },
];

const ccyCols: Col<CcyRow>[] = [
  { key: "currency", label: "Currency", align: "l", sort: (r) => r.currency, render: (r) => (
    r.currency === "unknown" ? <span className="muted" title="Funds whose currency isn't known: counted as local">unknown</span> : r.currency) },
  { key: "w_p", label: "Weight", name: "Average weight", sort: (r) => r.w_p, render: (r) => pct(r.w_p, 1, false) },
  { key: "w_b", label: "ACWI", name: "ACWI's average weight", sort: (r) => r.w_b, render: (r) => pct(r.w_b, 1, false) },
  { key: "fx", label: "vs DKK", name: "The currency's move against DKK", sort: (r) => r.fx_return, render: (r) => <Pct v={r.fx_return} /> },
  { key: "effect", label: "Effect", help: "attr_currency", sort: (r) => r.effect, render: (r) => <b><Pct v={r.effect} digits={2} /></b> },
];

/** The reconciliation as a waterfall: from 0 through each part to the active return vs ACWI, which they add up to. */
function Waterfall({ steps, total }: { steps: Step[]; total: Maybe }) {
  const [lo, hi] = extent([...steps.flatMap((s) => [s.from, s.to]), isNum(total) ? total : null]);
  const span = hi - lo || 1;
  const x = (v: number) => `${((v - lo) / span) * 100}%`;
  const bar = (a: number, b: number, color: string) => (
    <i style={{ left: x(Math.min(a, b)), width: `max(2px, ${(Math.abs(b - a) / span) * 100}%)`, background: color }} />);
  return (
    <div className="waterfall" role="table" aria-label="Active return vs ACWI, split into its parts">
      {steps.map((s) => (
        <div key={s.key} className="wf-row" role="row">
          <span role="cell">{s.label}</span>
          <span role="cell" className="wf-track" style={{ ["--zero" as string]: x(0) }}>
            {s.from !== null && s.to !== null && bar(s.from, s.to, s.to >= s.from ? "var(--pos)" : "var(--neg)")}
          </span>
          <span role="cell" className="num">{isNum(s.value) ? <Pct v={s.value} digits={2} />
            : <span className="muted" title="Missing: no bar, and the bars after it have no position">–</span>}</span>
        </div>
      ))}
      <div className="wf-row wf-total" role="row">
        <span role="cell"><Term k="attr_active">Active return vs ACWI</Term></span>
        <span role="cell" className="wf-track" style={{ ["--zero" as string]: x(0) }}>
          {isNum(total) && bar(0, total, "var(--ink-2)")}</span>
        <span role="cell" className="num"><b><Pct v={total} digits={2} /></b></span>
      </div>
    </div>
  );
}

/** Each month's linked effects stacked above (helped) and below (hurt) zero, with the month's values on hover. */
function MonthChart({ months }: { months: Month[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const stacks = months.map(stack);
  const [lo, hi] = extent(stacks.flatMap((s) => s.flatMap((g) => [g.y0, g.y1])));
  const H = 180, W = Math.max(months.length * 18, 300), pad = 4;
  const y = (v: number) => pad + ((hi - v) / (hi - lo || 1)) * (H - 2 * pad);
  const bw = W / Math.max(months.length, 1);
  const m = hover !== null ? months[hover] : null;
  return (
    <div className="attr-months">
      <div className="chart-legend" aria-hidden="true">
        {EFFECTS.map((e) => <span key={e}><i style={{ background: EFFECT_COLOR[e], height: 8 }} />{EFFECT_LABEL[e]}</span>)}
      </div>
      <div className="attr-plot">
        <span className="attr-axis" style={{ top: 0 }}>{pct(hi, 1)}</span>
        <span className="attr-axis" style={{ top: y(0) - 7 }}>0%</span>
        <span className="attr-axis" style={{ bottom: 0 }}>{pct(lo, 1)}</span>
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" height={H} width="100%" role="img"
          aria-label="Monthly effects, stacked; the table below has the numbers" onMouseLeave={() => setHover(null)}>
          <line x1={0} x2={W} y1={y(0)} y2={y(0)} stroke="var(--line)" />
          {stacks.map((segs, i) => (
            <g key={months[i]?.month ?? i} onMouseEnter={() => setHover(i)}>
              <rect x={i * bw} y={0} width={bw} height={H} fill={hover === i ? "var(--surface-2)" : "transparent"} />
              {segs.map((g) => (
                <rect key={g.effect} x={i * bw + bw * 0.15} width={bw * 0.7} y={y(g.y1)} height={Math.max(y(g.y0) - y(g.y1), 0.5)}
                  fill={EFFECT_COLOR[g.effect]} stroke="var(--surface)" strokeWidth={1} />
              ))}
            </g>
          ))}
        </svg>
      </div>
      <p className="small muted attr-readout">
        {m ? <>{m.month}{m.basis === "back-drifted" && " (back-drifted)"}: {EFFECTS.map((e) => `${EFFECT_LABEL[e]} ${pct(m[e], 2)}`).join(" · ")} ·
          active <b>{pct(m.active, 2)}</b> over {m.days} days</>
          : <>{months[0]?.month} – {months[months.length - 1]?.month}. Hover a month for its numbers.</>}
      </p>
    </div>
  );
}

function DimSection({ d, dim, setDim }: { d: AttributionView; dim: Dim; setDim: (x: Dim) => void }) {
  const v = d.dims[dim];
  if (!v) return null;
  return (
    <section className="group">
      <h2>Where it came from</h2>
      <Tabs tabs={DIMS} value={dim} onChange={setDim} label="Attribution dimension" />
      <div className="card">
        <p className="small">
          {EFFECTS.map((e, i) => <span key={e}>{i > 0 && " · "}<Term k={EFFECT_HELP[e]}>{EFFECT_LABEL[e]}</Term>{" "}
            <Pct v={v.totals[e]} digits={2} /></span>)}
        </p>
        <DataTable key={dim} id={`at${dim[0]}`} csvName={`attribution-${dim}`} rows={v.rows} cols={rowCols} rowKey={(r) => r.key}
          toolbar={false} empty="No segments." />
        <p className="small muted">
          Weights are averages over the days used, returns compounded in local currency, effects{" "}
          <Term k="attr_linking">linked</Term> over the period. {v.days} days used
          {v.days_missing > 0 && <span className="warn-text">, {v.days_missing} left out (see the notes)</span>}.
        </p>
        {v.months.length > 0 && <MonthChart months={v.months} />}
        <details>
          <summary className="small">The months as a table ({v.months.length})</summary>
          <DataTable id={`atm${dim[0]}`} csvName={`attribution-${dim}-months`} rows={v.months} cols={monthCols}
            rowKey={(m) => m.month} toolbar={false} />
        </details>
      </div>
    </section>
  );
}

function SkillCard({ g }: { g: AttributionView["regression"] }) {
  if (!g) {
    return <Card title="Skill or luck"><p className="small muted">No factor regression for this selection: the notes say why.</p></Card>;
  }
  const t2 = g.reached ? "reached" : isNum(g.months_to_t2) ? `about ${num(g.months_to_t2, 0)} months more` : "out of reach at this alpha";
  return (
    <Card title="Skill or luck">
      <KV rows={[
        ["Alpha p.a.", <Pct v={g.alpha_ann} />, { help: "attr_alpha", hint: isNum(g.alpha_se_ann) ? `± ${pct(g.alpha_se_ann, 1, false)}` : undefined }],
        ["t (Newey-West)", <span className={isNum(g.alpha_t) && Math.abs(g.alpha_t) >= 2 ? "pos" : ""}>{num(g.alpha_t, 2)}</span>,
          { hint: `lag ${g.nw_lag} weeks` }],
        ["Weeks", g.n_weeks, { hint: `${date(g.start)} – ${date(g.end)}` }],
        ["To reach t = 2", t2, { help: "attr_months_to_t2" }],
        ["R²", num(g.r2, 2)],
      ]} />
      <div className="badges">
        {g.loadings.map((l) => (
          <Badge key={l.factor} kind={isNum(l.t) && Math.abs(l.t) >= 2 ? "accent" : ""}>
            {l.factor} {num(l.beta, 2)} <span className="muted">t {num(l.t, 1)}</span></Badge>))}
      </div>
      <p className="small muted">French&apos;s developed factors in DKK, to {date(g.factors_to)}. Highlighted: |t| ≥ 2.
        A measurement of the past, not a forecast.</p>
    </Card>
  );
}

/** The Attribution tab on Returns: why the chosen portfolios, pooled, beat or lagged ACWI over the period. */
export function AttributionTab({ sel, start }: { sel: PortfolioSel; start: string }) {
  const [dim, setDim] = useState<Dim>("sector");
  const q = useQuery({ queryKey: ["attribution", formatSel(sel), start],
    queryFn: () => api.attribution(sel, start || undefined), retry: false, staleTime: 60_000 });
  const guide = useGuideTree().data;
  const chapter = guide ? pageChapter(guide.page_links, "/returns") : null;
  if (q.isPending) return <p className="muted">Loading the attribution…</p>;
  if (q.isError) return <p className="note warn-text">The attribution could not be computed: {String(q.error)}</p>;
  const d = q.data;
  const rec = d.reconciliation;
  const tot = d.dims.sector?.totals;
  const steps = waterfall([
    { key: "trading", label: "Trading and fees", value: rec?.trading_fees },
    { key: "proxy", label: "Benchmark proxies vs ACWI", value: rec?.proxy_vs_acwi },
    ...EFFECTS.map((e) => ({ key: e, label: EFFECT_LABEL[e], value: tot?.[e] })),
  ]);
  return (
    <>
      <p className="note">
        Why the ticked portfolios, <b>pooled into one</b>, beat or lagged ACWI over the period, in DKK: allocation and
        selection by sector and by region (Brinson–Fachler on local returns), the currency effect, and whether what&apos;s
        left looks like skill. Each holding is classified as it is today. {PROXY} Analysis, not advice.
      </p>
      <div className="tiles">
        <div className="tile"><span>Period</span>
          <b>{d.period ? `${date(d.period.start)} – ${date(d.period.end)}` : "–"}</b>
          <span>{d.period ? `${num(d.period.months, 0)} months` : "no valued history"}</span></div>
        <div className="tile"><span><Term k="twr">Time-weighted return</Term></span><b><Pct v={rec?.twr} /></b>
          <span>ACWI {pct(rec?.acwi)}</span></div>
        <div className="tile"><span><Term k="attr_active">Active vs ACWI</Term></span><b><Pct v={rec?.active} /></b>
          <span>{d.selection.names.join(", ") || "no portfolios"}</span></div>
        <div className="tile"><span><Term k="attr_alpha">Alpha p.a. (t)</Term></span>
          <b><Pct v={d.regression?.alpha_ann} /> <span className="small">({num(d.regression?.alpha_t, 1)})</span></b>
          <span>{d.regression ? `${d.regression.n_weeks} weeks` : "no regression"}</span></div>
      </div>
      {!rec || Object.keys(d.dims).length === 0
        ? <p className="note">No attribution for this selection yet: the notes below say why.
          {d.selection.ids.length === 0 && <> <Link to="/portfolio">Add trades on the Portfolio page</Link>.</>}</p>
        : (
          <>
            <section className="group">
              <h2>From ACWI to your return</h2>
              <div className="card">
                <Waterfall steps={steps} total={rec.active} />
                <p className="small muted">
                  <Term k="attr_trading_fees">Trading and fees</Term> and <Term k="attr_proxy">benchmark proxies vs ACWI</Term> come
                  first; the effects (by sector here) add up to the rest. Linking error {isNum(d.dims.sector?.linking_error) ? d.dims.sector.linking_error.toExponential(0) : "–"}.
                </p>
              </div>
            </section>
            <DimSection d={d} dim={dim} setDim={setDim} />
            <div className="grid">
              {d.currency && (
                <Card title="Currency">
                  <p className="small"><Term k="attr_currency">Currency effect</Term> <Pct v={d.currency.effect} digits={2} />,{" "}
                    <Term k="attr_cross">cross term</Term> <Pct v={d.currency.cross} digits={2} />.</p>
                  <DataTable id="atc" csvName="attribution-currency" rows={d.currency.rows} cols={ccyCols} rowKey={(r) => r.currency}
                    toolbar={false} empty="No currencies." />
                </Card>
              )}
              <SkillCard g={d.regression} />
            </div>
          </>
        )}
      {rec === null && d.regression && <div className="grid"><SkillCard g={d.regression} /></div>}
      <section className="group">
        <h2>Notes</h2>
        <ul className="small muted perf-notes">
          {d.unclassified.length > 0 && (
            <li className="warn-text">Not placed by sector (their own segment, with their own return): {d.unclassified.map((u, i) => (
              <span key={u.symbol}>{i > 0 && ", "}<TickerLink symbol={u.symbol} /> ({pct(u.avg_weight, 1, false)})</span>))}.</li>
          )}
          {d.benchmark.back_drifted_months.length > 0 && (
            <li>ACWI&apos;s weights are back-drifted in {d.benchmark.back_drifted_months.length} month(s), before the first weekly
              record ({date(d.benchmark.first_snapshot)}).</li>
          )}
          {d.notes.map((n) => <li key={n}>{n}</li>)}
          {chapter && <li><Link to={`/guide/${chapter}`}>How to read Returns and the attribution (guide)</Link></li>}
        </ul>
      </section>
    </>
  );
}

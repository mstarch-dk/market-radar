import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, type XrayView } from "../api/client";
import { Loaded, PageHead, Pct } from "../components/cells";
import { DataTable, type Col } from "../components/DataTable";
import { PortfolioPicker, usePortfolioSel } from "../components/PortfolioPicker";
import { Tabs, useTabParam } from "../components/Tabs";
import { Term } from "../components/Term";
import { TickerLink } from "../components/TickerLink";
import { Badge, Card, KV } from "../components/ui";
import { date, isNum, num, pct, type Maybe } from "../lib/format";
import { pageChapter, useGuideTree } from "../lib/guide";
import { formatSel, isDefaultSel } from "../lib/portfolioSel";

type Dim = "sector" | "region" | "currency";
type ExpRow = XrayView["exposure"]["sector"]["rows"][number];
type ClassRow = XrayView["classes"][number];
type RiskRow = NonNullable<XrayView["risk"]>["positions"][number];
type Pair = XrayView["concentration"]["pairs"][number];
type Window = XrayView["stress"][number];

const DIMS: [Dim, string][] = [["sector", "Sector"], ["region", "Region"], ["currency", "Currency"]];

const CLASS_LABEL: Record<ClassRow["class"], string> = {
  world: "world fund (ACWI's weights)", index_fund: "index fund (its index's weights)", sector_fund: "sector fund",
  fund_sectors: "fund (Yahoo's sector weights)", fund: "fund, not looked through", stock: "stock", unknown: "unknown",
};

const ticker = <T,>(get: (r: T) => string, key = "symbol", label = "Name"): Col<T> => ({
  key, label, align: "l", sort: get, search: get, csv: get, render: (r) => <TickerLink symbol={get(r)} /> });

/** Active weight as a bar from the middle: right = more than ACWI, left = less. `max` is the largest |active| shown. */
function ActiveBar({ v, max }: { v: Maybe; max: number }) {
  if (!isNum(v) || max <= 0) return <span className="dbar" aria-hidden="true" />;
  const w = `${Math.min(Math.abs(v) / max, 1) * 100}%`;
  return (
    <span className="dbar" aria-hidden="true">
      <span className="l">{v < 0 && <i style={{ width: w }} />}</span>
      <span className="r">{v > 0 && <i style={{ width: w }} />}</span>
    </span>
  );
}

function expCols(max: number): Col<ExpRow>[] {
  return [
    { key: "key", label: "Key", align: "l", sort: (r) => r.key, search: (r) => r.key,
      render: (r) => r.acwi == null && r.active == null ? <span className="muted">{r.key === "?" ? "unknown" : r.key}</span> : r.key },
    { key: "weight", label: "Weight", sort: (r) => r.weight, render: (r) => pct(r.weight, 1, false) },
    { key: "acwi", label: "ACWI", sort: (r) => r.acwi, render: (r) => pct(r.acwi, 1, false) },
    { key: "active", label: "Active", help: "xray_active", sort: (r) => r.active, render: (r) => <Pct v={r.active} /> },
    { key: "bar", label: "", name: "Active weight (bar)", csv: false, render: (r) => <ActiveBar v={r.active} max={max} /> },
  ];
}

const classCols: Col<ClassRow>[] = [
  ticker((r) => r.symbol),
  { key: "class", label: "Class", help: "xray_class", align: "l", sort: (r) => r.class, csv: (r) => r.class,
    filter: { kind: "enum", value: (r) => [CLASS_LABEL[r.class]] }, render: (r) => CLASS_LABEL[r.class] },
  { key: "value", label: "Value (DKK)", sort: (r) => r.value_dkk, render: (r) => num(r.value_dkk, 0) },
  { key: "weight", label: "Weight", sort: (r) => r.weight, render: (r) => pct(r.weight, 1, false) },
  { key: "detail", label: "Fund data", align: "l", sort: (r) => r.detail_asof, render: (r) => r.detail_asof
    ? <span className="small muted">Yahoo, {date(r.detail_asof)}</span> : <span className="muted">–</span> },
];

/** A share of active risk below 0 is a position that lowers the tracking error (it offsets the rest), said so. */
function ActiveShare({ v }: { v: Maybe }) {
  if (!isNum(v)) return <span className="muted">–</span>;
  return v < 0
    ? <span className="pos" title="This position lowers the tracking error">{pct(v)} <Badge kind="accent">reduces TE</Badge></span>
    : <>{pct(v, 1, false)}</>;
}

const riskCols: Col<RiskRow>[] = [
  ticker((r) => r.symbol),
  { key: "weight", label: "Weight", name: "Weight in the risk model", sort: (r) => r.weight, render: (r) => pct(r.weight, 1, false) },
  { key: "total", label: "Share of risk", help: "xray_share_total", sort: (r) => r.share_total,
    render: (r) => pct(r.share_total, 1, false) },
  { key: "active", label: "Share of active risk", help: "xray_share_active", sort: (r) => r.share_active,
    render: (r) => <ActiveShare v={r.share_active} /> },
  { key: "mctr", label: "MCTR", help: "xray_mctr", sort: (r) => r.mctr_ann, render: (r) => pct(r.mctr_ann, 1, false) },
];

const pairCols: Col<Pair>[] = [
  ticker((r) => r.a, "a", "Holding"),
  ticker((r) => r.b, "b", "Moves with"),
  { key: "corr", label: "Correlation", sort: (r) => r.corr, render: (r) => num(r.corr, 2) },
  { key: "weight", label: "Combined weight", sort: (r) => r.weight, render: (r) => pct(r.weight, 1, false) },
];

const stressCols: Col<Window>[] = [
  { key: "label", label: "Window", align: "l", sort: (r) => r.start, render: (r) => (
    <span>{r.label} <span className="small muted">{date(r.start)} – {date(r.end)}</span></span>) },
  { key: "ret", label: "Return", sort: (r) => r.ret, render: (r) => <Pct v={r.ret} /> },
  { key: "acwi_ret", label: "ACWI", sort: (r) => r.acwi_ret, render: (r) => <Pct v={r.acwi_ret} /> },
  { key: "dd", label: "Max drawdown", sort: (r) => r.max_dd, render: (r) => <Pct v={r.max_dd} /> },
  { key: "acwi_dd", label: "ACWI drawdown", sort: (r) => r.acwi_max_dd, render: (r) => <Pct v={r.acwi_max_dd} /> },
  { key: "coverage", label: "Coverage", help: "xray_stress", sort: (r) => r.coverage, render: (r) => pct(r.coverage, 0, false) },
  { key: "note", label: "", name: "Note", align: "l", csv: (r) => [r.note, ...r.missing].filter(Boolean).join("; "),
    render: (r) => (
      <span className="small muted">{r.note}{r.missing.length > 0 && <> {r.note && "· "}no prices: {r.missing.join(", ")}</>}</span>) },
];

function Tile({ label, help, children, sub, warn }: {
  label: string; help?: Parameters<typeof Term>[0]["k"]; children: React.ReactNode; sub?: React.ReactNode; warn?: boolean;
}) {
  return (
    <div className="tile">
      <span>{help ? <Term k={help}>{label}</Term> : label}</span>
      <b className={warn ? "warn-text" : ""}>{children}</b>
      {sub && <span>{sub}</span>}
    </div>
  );
}

const TILT_LABEL: Record<XrayView["tilts"][number]["key"], string> = { score: "Momentum", qv: "K+V" };

/** The holdings' value-weighted momentum score and K+V next to the universe's medians; names without a score are
 *  left out of the average and counted. */
function TiltsTile({ tilts }: { tilts: XrayView["tilts"] }) {
  const missing = tilts.filter((t) => t.missing.length > 0);
  return (
    <div className="tile">
      <span><Term k="xray_tilts">Score tilts</Term></span>
      <b>{tilts.map((t, i) => <span key={t.key}>{i > 0 && " · "}{TILT_LABEL[t.key]} {num(t.value, 0)}</span>)}</b>
      <span>median {tilts.map((t) => num(t.median, 0)).join(" / ")}
        {missing.length > 0 && <> · without a score: {missing.map((t) => `${TILT_LABEL[t.key]} ${t.missing.length}`).join(", ")}</>}</span>
    </div>
  );
}

function Header({ d }: { d: XrayView }) {
  const { totals: t, risk: r, concentration: c } = d;
  const total = t.cash_dkk != null ? t.invested_dkk + t.cash_dkk : null;
  return (
    <div className="tiles xray-tiles">
      <Tile label="Invested (DKK)" sub={t.unvalued.length > 0 && <span className="warn-text">{t.unvalued.length} without a value</span>}>
        {num(t.invested_dkk, 0)}</Tile>
      <Tile label="Cash share" sub={t.cash_dkk != null ? `${num(t.cash_dkk, 0)} DKK` : "no cash ledger"}>
        {total != null && total > 0 ? pct(t.cash_dkk! / total, 1, false) : "–"}</Tile>
      <Tile label="Volatility (ex-ante)" help="xray_vol" warn={r?.warn}>{pct(r?.vol_ann, 1, false)}</Tile>
      <Tile label="Beta" help="xray_beta" warn={r?.warn}>{num(r?.beta, 2)}</Tile>
      <Tile label="Tracking error" help="xray_te" warn={r?.warn}>{pct(r?.te_ann, 1, false)}</Tile>
      <Tile label="Effective N" help="xray_effective_n" sub={isNum(c.top5_share) && `top 5: ${pct(c.top5_share, 0, false)}`}>
        {num(c.effective_n, 1)}</Tile>
      <Tile label="Risk model coverage" help="xray_coverage" warn={r ? r.warn : t.invested_dkk > 0}
        sub={r ? (r.warn ? "figures cover only part" : "of invested value") : t.invested_dkk > 0 ? "too low: no risk figures" : undefined}>
        {r ? pct(r.coverage, 0, false) : "–"}</Tile>
      {d.tilts.length > 0 && <TiltsTile tilts={d.tilts} />}
    </div>
  );
}

function Exposure({ d }: { d: XrayView }) {
  const [dim, setDim] = useTabParam(DIMS.map(([k]) => k), "sector");
  const e = d.exposure[dim];
  const max = Math.max(0, ...e.rows.map((r) => Math.abs(r.active ?? 0)));
  return (
    <section className="group">
      <h2>Exposure vs ACWI <span className="small muted">(of invested value)</span></h2>
      <Tabs tabs={DIMS} value={dim} onChange={setDim} label="Exposure dimension" />
      <div className="card">
        <DataTable key={dim} id={`x${dim[0]}`} csvName={`xray-${dim}`} rows={e.rows} cols={expCols(max)} rowKey={(r) => r.key}
          toolbar={false} empty="No valued holdings." />
        <p className={`small ${e.warn ? "warn-text" : "muted"}`}>
          {e.coverage == null ? `${DIMS.find(([k]) => k === dim)![1]}: coverage unknown.`
            : `${DIMS.find(([k]) => k === dim)![1]}: ${pct(e.coverage, 0, false)} of the value placed${e.warn ? " (low)" : ""}.`}
          {e.note && <> {e.note}.</>}
        </p>
      </div>
      {d.classes.length > 0 && (
        <details className="card">
          <summary>How each name is classified ({d.classes.length})</summary>
          <DataTable id="xcls" csvName="xray-classes" rows={d.classes} cols={classCols} rowKey={(r) => r.symbol} />
        </details>
      )}
    </section>
  );
}

function Risk({ r }: { r: NonNullable<XrayView["risk"]> }) {
  return (
    <section className="group">
      <h2>Where the risk sits</h2>
      <div className="card">
        <DataTable id="xrisk" csvName="xray-risk" rows={r.positions} cols={riskCols} rowKey={(x) => x.symbol} />
        <p className="small muted">
          {isNum(r.acwi_leg_share_active) && (r.acwi_leg_share_active < 0
            ? <>The ACWI leg (the index you are measured against) lowers the active risk slightly
              ({pct(r.acwi_leg_share_active)} of it). </>
            : <>The ACWI leg (the index you are measured against) carries {pct(r.acwi_leg_share_active, 1, false)} of the
              active risk. </>)}
          A negative share of active risk is a position that lowers the tracking error. <Term k="xray_div_ratio">Diversification
          ratio</Term> {num(r.div_ratio, 2)}. Weekly DKK returns over {r.window_weeks} weeks, shrunk {pct(r.shrink, 0, false)} towards
          a constant correlation.
        </p>
        {r.excluded.length > 0 && (
          <p className="small warn-text">Not in the risk model: {r.excluded.map((x, i) => (
            <span key={x.symbol}>{i > 0 && ", "}<TickerLink symbol={x.symbol} /> ({pct(x.weight, 1, false)}, {x.reason})</span>))}.</p>
        )}
        <p className="small">
          <Term k="xray_realised">Ex-ante vs realised</Term>: today&apos;s weights on past returns give a volatility
          of {pct(r.vol_ann, 1, false)}; what was actually held over the last year moved {pct(r.realised_vol_1y, 1, false)} a year,
          with a deepest fall of {pct(r.realised_max_dd_1y)}.
          {!isNum(r.realised_vol_1y) && <span className="muted"> (No realised figures: too little history.)</span>}
        </p>
      </div>
    </section>
  );
}

function ConcentrationCard({ c }: { c: XrayView["concentration"] }) {
  return (
    <Card title="Concentration">
      <KV rows={[
        ["Effective N", num(c.effective_n, 1), { help: "xray_effective_n" }],
        ["Top 5", pct(c.top5_share, 1, false)],
        ["Largest position", c.largest ? <><TickerLink symbol={c.largest.symbol} /> {pct(c.largest.weight, 1, false)}</> : "–"],
        ["Largest share of risk", c.largest_ctr ? <><TickerLink symbol={c.largest_ctr.symbol} /> {pct(c.largest_ctr.share, 1, false)}</> : "–",
          { help: "xray_share_total" }],
        ["In world funds", pct(c.world_fund_weight, 1, false), { hide: !c.world_fund_weight, hint: "each counted as one position" }],
      ]} />
      <h3><Term k="xray_pairs">Holdings that move together</Term></h3>
      {c.pairs.length === 0 ? <p className="small muted">No pair above the threshold.</p>
        : <DataTable id="xpairs" csvName="xray-pairs" rows={c.pairs} cols={pairCols} rowKey={(p) => `${p.a}|${p.b}`} toolbar={false} />}
    </Card>
  );
}

function FactorsCard({ f }: { f: NonNullable<XrayView["factors"]> }) {
  return (
    <Card title="Factor tilts">
      <p className="small"><Term k="factor_tilts">Loadings</Term> over {f.n_weeks} weeks, R² {num(f.r2, 2)}:</p>
      <div className="badges">
        {f.loadings.map((l) => (
          <Badge key={l.factor} kind={l.t != null && Math.abs(l.t) >= 2 ? (l.beta! > 0 ? "accent" : "warn") : ""}>
            {l.factor} {num(l.beta, 2)} <span className="muted">t {num(l.t, 1)}</span>
          </Badge>
        ))}
      </div>
      <p className="small muted">Residual alpha {pct(f.alpha_ann)} a year (t {num(f.alpha_t, 1)}; {f.alpha_basis}). Highlighted: |t| ≥ 2.
        The factors are US ETFs as spreads over ACWI, so this describes how the portfolio has behaved; it is not a forecast.</p>
    </Card>
  );
}

/** The portfolio X-ray: what a selection is exposed to against ACWI and where its risk sits, computed live. */
export function Xray() {
  const [sel, setSel] = usePortfolioSel();
  const q = useQuery({ queryKey: ["xray", formatSel(sel)], queryFn: () => api.xray(sel), retry: false, staleTime: 60_000 });
  const guide = useGuideTree().data;
  const chapter = guide ? pageChapter(guide.page_links, "/xray") : null;
  return (
    <Loaded q={q} title="Portfolio X-ray">
      {(d) => (
        <>
          <PageHead title="Portfolio X-ray" asof={d.asof ?? undefined} generated={d.generated}>
            What the chosen portfolios are exposed to by sector, region and currency <b>against ACWI</b>, and where the risk
            sits: each position&apos;s share of the total and of the active risk (the tracking error), concentration, how
            today&apos;s weights would have done in past crises, and the factor tilts. In DKK, computed live from today&apos;s
            weights. A fund is looked through only where its weights are known; the rest is shown as such, never guessed.
            Analysis, not advice.
          </PageHead>
          <p><PortfolioPicker sel={sel} onChange={setSel} />
            {!isDefaultSel(sel) && <span className="small warn-text"> Showing the chosen portfolios, not only yours.</span>}</p>
          <Header d={d} />
          {d.totals.unvalued.length > 0 && (
            <p className="small warn-text">Left out of every weight (no DKK value): {d.totals.unvalued.map((u, i) => (
              <span key={u.symbol}>{i > 0 && ", "}<TickerLink symbol={u.symbol} /> ({num(u.quantity, 0)}, {u.reason})</span>))}.</p>
          )}
          {d.classes.length === 0
            ? <p className="note">Nothing to X-ray in this selection. <Link to="/portfolio">Add trades on the Portfolio page</Link>, or
              choose another portfolio above.</p>
            : (
              <>
                <Exposure d={d} />
                {d.risk && <Risk r={d.risk} />}
                <div className="grid">
                  <ConcentrationCard c={d.concentration} />
                  {d.factors && <FactorsCard f={d.factors} />}
                </div>
                <section className="group">
                  <h2><Term k="xray_stress">Stress: today&apos;s weights in past crises</Term></h2>
                  <div className="card">
                    <DataTable id="xstress" csvName="xray-stress" rows={d.stress} cols={stressCols} rowKey={(w) => w.key}
                      toolbar={false} empty="No stress windows configured." />
                  </div>
                </section>
              </>
            )}
          {(d.notes.length > 0 || chapter) && (
            <section className="group">
              <h2>Notes</h2>
              <ul className="small muted perf-notes">
                {d.notes.map((n) => <li key={n}>{n}</li>)}
                {chapter && <li><Link to={`/guide/${chapter}`}>How to read the X-ray (guide)</Link></li>}
              </ul>
            </section>
          )}
        </>
      )}
    </Loaded>
  );
}

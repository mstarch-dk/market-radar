import type { ReactNode } from "react";
import { GaugeBadge, GaugeBar, Graded } from "./Gauge";
import { Sparkline } from "./Sparkline";
import { Term } from "./Term";
import { TickerLink } from "./TickerLink";
import { Link } from "react-router-dom";
import { ALIGN_KIND, ALIGN_TEXT, dots, VERDICT_KIND } from "../lib/views";
import type { Profile, Windows } from "../api/client";
import type { components } from "../api/schema";

type RiskWindow = components["schemas"]["RiskWindow"];
import { compact, date, daysUntil, isNum, num, pct, price, tone, type Maybe } from "../lib/format";
import { Badge, Card, KV, Signed } from "./ui";

const WIN: [keyof Windows, string][] = [["r1w", "1W"], ["r1m", "1M"], ["r3m", "3M"], ["r6m", "6M"], ["ytd", "YTD"], ["r1y", "1Y"]];

function Row({ label, w, hint }: { label: ReactNode; w?: Windows | null; hint?: string }) {
  if (!w) return null;
  return (
    <tr>
      <td>{label}{hint && <span className="muted small"> {hint}</span>}</td>
      {WIN.map(([k]) => <td key={k} className={tone(w[k])}>{pct(w[k])}</td>)}
    </tr>
  );
}

export function Returns({ p }: { p: Profile }) {
  const pr = p.price;
  return (
    <Card title="Price development" meta={pr}>
      <div className="scroll">
        <table className="t">
          <thead><tr><th />{WIN.map(([, l]) => <th key={l}>{l}</th>)}</tr></thead>
          <tbody>
            <Row label={pr.currency ?? "Local"} w={pr.returns} />
            {pr.currency !== "DKK" && <Row label="DKK" w={pr.returns_dkk} />}
            <Row label="vs ACWI" w={pr.vs_acwi} />
            <Row label={pr.sector_etf ? <>vs <TickerLink symbol={pr.sector_etf} /></> : "vs sector"} w={pr.vs_sector} />
          </tbody>
        </table>
      </div>
      <p className="small muted">Total returns (adjusted closes); "vs" rows are the difference in percentage points.</p>
      <h3>52-week range <span className="muted">(adjusted closes, not intraday)</span></h3>
      <KV rows={[
        ["High", price(pr.high_52w, pr.currency), { hint: pct(pr.from_high) }],
        ["Low", price(pr.low_52w, pr.currency), { hint: pct(pr.from_low) }],
      ]} />
      {!pr.vs_sector && p.identity.quote_type === "EQUITY" && (
        <p className="small muted">No sector ETF mapped for {p.identity.sector ?? "this sector"} in this region.</p>
      )}
    </Card>
  );
}

const yesNo = (v: boolean | null | undefined, yes: string, no: string) => (v === null || v === undefined ? "–" : v ? yes : no);

export function MomentumCard({ p }: { p: Profile }) {
  const m = p.momentum;
  return (
    <Card title="Momentum & trend" meta={m}>
      <KV rows={[
        ["Momentum score", <>{isNum(m.score) ? `${num(m.score, 0)} / 100` : "–"} <GaugeBadge g={m.gauges?.score} name="Momentum score" /></>,
          { hint: m.rank ? `rank ${m.rank} of ${m.group_size}` : undefined, help: "score" }],
        ["3m / 6m return", <><Signed v={m.r3m}>{pct(m.r3m)}</Signed> / <Signed v={m.r6m}>{pct(m.r6m)}</Signed></>],
        ["12-1 month return", pct(m.r12_1), { tone: m.r12_1, hint: "skips the last month", help: "r12_1" }],
        ["Price vs 50-day", yesNo(m.above50, "above", "below"), { hint: price(m.sma50) }],
        ["Price vs 200-day", yesNo(m.above200, "above", "below"), { hint: price(m.sma200) }],
        ["Trend (50d > rising 200d)", yesNo(m.trend_ok, "intact", "not intact"), { help: "trend_ok" }],
        ["From 52-week high", <>{pct(m.from_high)} <GaugeBadge g={m.gauges?.from_high} name="52w high" /></>, { help: "from_high" }],
        ["Volume, 20d vs 6m avg", <>{isNum(m.vol_surge) ? `${num(m.vol_surge, 2)}×` : "–"} <GaugeBadge g={m.gauges?.vol_surge} name="Volume" /></>, { help: "vol_surge" }],
      ]} />
      <p className="small muted">Score: {m.score_basis}{m.region_label ? `, ${m.region_label}` : ""}.</p>
    </Card>
  );
}

export function TechnicalsCard({ p }: { p: Profile }) {
  const t = p.technicals;
  return (
    <Card title="Technicals" meta={t}>
      <KV rows={[
        ["RSI 14", <>{num(t.rsi14, 1)} <GaugeBadge g={t.gauges?.rsi14} name="RSI 14" /><GaugeBar g={t.gauges?.rsi14} /></>, { help: "rsi" }],
        ["MACD 12/26/9", <>{num(t.macd_hist, 2)} <GaugeBadge g={t.gauges?.macd_atr} name="MACD (histogram ÷ ATR)" /></>, { hint: "histogram", help: "macd" }],
        ["Bollinger %B", <>{num(t.bb_pct_b, 2)} <GaugeBadge g={t.gauges?.bb_pct_b} name="Bollinger %B" /><GaugeBar g={t.gauges?.bb_pct_b} /></>, { help: "bb" }],
        ["ATR 14", <>{price(t.atr)} <GaugeBadge g={t.gauges?.atr_pct} name="Daily range" /></>, { hint: pct(t.atr_pct, 1, false) + " of price", help: "atr" }],
        ["Volatility (3m, annualised)", pct(t.vol_3m, 1, false)],
        ["Max drawdown (1y)", pct(t.max_drawdown_1y), { tone: t.max_drawdown_1y }],
        ["Beta / correlation vs ACWI", <>{`${num(t.beta_acwi, 2)} / ${num(t.corr_acwi, 2)}`} <GaugeBadge g={t.gauges?.beta} name="Beta" /></>, { hint: "weekly, 1y", help: "beta" }],
      ]} />
    </Card>
  );
}

export function LevelsCard({ p }: { p: Profile }) {
  const l = p.levels;
  const cur = p.price.currency;
  return (
    <Card title="Stop / take-profit (rule)" meta={l}>
      <KV rows={[
        ["Trailing stop", <>{price(l.stop, cur)} <GaugeBadge g={l.gauges?.stop_dist} name="Stop" /></>, { hint: pct(l.stop_pct), help: "stop" }],
        ["Take-profit", l.take_profit ? <>{price(l.take_profit, cur)} <GaugeBadge g={l.gauges?.tp_dist} name="Target" /></> : "none", { hint: l.take_profit ? pct(l.tp_pct) : undefined, help: "take_profit" }],
        ["Stop width k × ATR", isNum(l.k) ? `${num(l.k, 1)} × ${price(l.atr)}` : "–", { help: "k" }],
        ["Regime", l.regime ?? "–"],
      ]} />
      {(l.flags ?? []).length > 0 && <div className="badges">{(l.flags ?? []).map((f) => <Badge key={f} kind="warn">{f}</Badge>)}</div>}
      <ul className="reasons">
        {(l.reasons ?? []).map((r, i) => (
          <li key={i}>
            <span className="eff">{r.effect ? (r.effect > 0 ? `+${r.effect}` : r.effect) : ""}</span>
            <span><b>{r.signal}</b> · {r.detail}</span>
          </li>
        ))}
      </ul>
      <p className="small muted">A mechanical rule for review, not advice.</p>
    </Card>
  );
}

export function RiskCard({ p }: { p: Profile }) {
  const r = p.risk;
  if (!r) return null;
  const w = ["1y", "3y"].filter((k) => r.windows[k]);
  const f2 = (v: number | null | undefined, d = 2) => num(v, d);
  const row = (label: ReactNode, cell: (x: RiskWindow) => ReactNode) => (
    <tr><td>{label}</td>{w.map((k) => <td key={k}>{cell(r.windows[k]!)}</td>)}</tr>
  );
  return (
    <Card title="Risk vs ACWI (DKK, weekly)" meta={r}>
      {w.length === 0 ? <p className="empty">Not enough weekly history.</p> : (
        <div className="scroll">
          <table className="t">
            <thead><tr><th />{w.map((k) => <th key={k}>{k} <span className="muted small">({r.windows[k]!.n_weeks}w)</span></th>)}</tr></thead>
            <tbody>
              {row("Return, annualised", (x) => <Signed v={x.return_ann}>{pct(x.return_ann)}</Signed>)}
              {row("Volatility", (x) => pct(x.vol_ann, 1, false))}
              {row(<Term k="risk_beta">Beta ± se (R²)</Term>, (x) => <>{f2(x.beta)} <span className="muted small">± {f2(x.beta_se)} ({f2(x.r2)})</span></>)}
              {row(<Term k="downside_beta">Downside beta</Term>, (x) => f2(x.downside_beta))}
              {row(<Term k="risk_alpha">Alpha (t)</Term>, (x) => <><Signed v={x.alpha_ann}>{pct(x.alpha_ann)}</Signed> <span className="muted small">({f2(x.alpha_t, 1)})</span></>)}
              {row(<Term k="idio_vol">Stock-specific vol</Term>, (x) => pct(x.idio_vol_ann, 1, false))}
              {row(<Term k="sharpe">Sharpe / Sortino</Term>, (x) => `${f2(x.sharpe)} / ${f2(x.sortino)}`)}
              {row("Max drawdown (weeks under)", (x) => <><Signed v={x.max_dd}>{pct(x.max_dd)}</Signed> <span className="muted small">({x.max_dd_weeks}w)</span></>)}
            </tbody>
          </table>
        </div>
      )}
      {r.factors && (
        <>
          <h3><Term k="factor_tilts">Factor tilts ({r.factors.n_weeks}w, R² {f2(r.factors.r2)})</Term></h3>
          <div className="badges">
            {r.factors.loadings.map((l) => (
              <Badge key={l.factor} kind={l.t != null && Math.abs(l.t) >= 2 ? (l.beta! > 0 ? "accent" : "warn") : ""}>
                {l.factor} {f2(l.beta)} <span className="muted">t {f2(l.t, 1)}</span>
              </Badge>
            ))}
          </div>
          <p className="small muted">Residual alpha {pct(r.factors.alpha_ann)} a year (t {f2(r.factors.alpha_t, 1)}). Highlighted: |t| ≥ 2.</p>
        </>
      )}
      {r.budget != null && (
        <KV rows={[[<Term k="risk_budget">Size at {pct(r.budget_risk, 0, false)} risk</Term>,
          r.budget > 1 ? "over 100% (stop very close)" : pct(r.budget, 0, false), { hint: "of the portfolio, at the rule stop" }]]} />
      )}
      {r.notes.length > 0 && <p className="small muted">{r.notes.join(" ")}</p>}
    </Card>
  );
}

const EPS_LABEL: Record<string, string> = { "0q": "This qtr", "+1q": "Next qtr", "0y": "This year", "+1y": "Next year" };
const REC_COLORS = ["var(--pos)", "#6cc08f", "var(--muted)", "#ee9a8f", "var(--neg)"];
const REC_KEYS = ["strong_buy", "buy", "hold", "sell", "strong_sell"] as const;

function TargetRange({ low, mean, high, now, currency }: { low: Maybe; mean: Maybe; high: Maybe; now: number; currency?: string | null }) {
  if (!isNum(low) || !isNum(high) || !isNum(mean)) return null;
  const lo = Math.min(low, now) * 0.97;
  const hi = Math.max(high, now) * 1.03;
  const x = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  return (
    <div className="range" aria-label="Analyst target range">
      <div className="track" />
      <div className="band" style={{ left: x(low), width: `calc(${x(high)} - ${x(low)})` }} />
      <div className="mark mean" style={{ left: x(mean) }}><span>mean {price(mean, currency)}</span></div>
      <div className="mark now" style={{ left: x(now), top: 2, height: 12 }} title={`price ${price(now, currency)}`} />
      <span className="small muted" style={{ position: "absolute", left: 0, top: -2 }}>{price(low)}</span>
      <span className="small muted" style={{ position: "absolute", right: 0, top: -2 }}>{price(high)}</span>
    </div>
  );
}

export function AnalystCard({ p }: { p: Profile }) {
  const a = p.analyst;
  const cur = p.price.currency;
  const days = daysUntil(a.calendar.next_earnings);
  return (
    <Card title="Analysts & estimates" meta={a}>
      {a.stale && <p className="small muted">Consensus is older than {a.max_age_days} days: targets not used.</p>}
      {isNum(a.target_mean) && (
        <>
          <KV rows={[
            ["Mean target", <>{price(a.target_mean, cur)} <GaugeBadge g={a.gauges?.upside} name="Analyst targets" /></>, { hint: pct(a.upside) + " upside" }],
            ["Consensus", `${a.rec_key ?? "–"}${isNum(a.rec_mean) ? ` (${num(a.rec_mean, 1)})` : ""}`,
              { hint: isNum(a.n_analysts) ? `${a.n_analysts} analysts` : undefined }],
            ["Target change, 30 days", <>{pct(a.target_change)} <GaugeBadge g={a.gauges?.target_change} name="Analyst targets" /></>, { hide: !isNum(a.target_change) }],
          ]} />
          <TargetRange low={a.target_low} mean={a.target_mean} high={a.target_high} now={p.price.last} currency={cur} />
        </>
      )}
      <KV rows={[
        ["Next earnings", a.calendar.next_earnings ? date(a.calendar.next_earnings) : "–",
          { hint: days !== null ? `in ${days} days` : undefined }],
        ["Ex-dividend", date(a.calendar.ex_dividend), { hide: !a.calendar.ex_dividend }],
      ]} />
      {a.recommendations.length > 0 && (
        <>
          <h3>Recommendations by month</h3>
          {a.recommendations.map((r) => (
            <div className="rec-row" key={r.period ?? ""}>
              <span className="muted">{r.period === "0m" ? "now" : r.period}</span>
              <div className="stack">
                {REC_KEYS.map((k, i) => r[k] > 0 && <div key={k} style={{ width: `${(100 * r[k]) / r.n}%`, background: REC_COLORS[i] }} title={`${k.replace("_", " ")}: ${r[k]}`} />)}
              </div>
              <span className="num small">{r.n} · {num(r.mean, 1)}</span>
            </div>
          ))}
          <div className="rec-legend">
            {REC_KEYS.map((k, i) => <span key={k}><i style={{ background: REC_COLORS[i] }} />{k.replace("_", " ")}</span>)}
            <span>mean: 1 = strong buy, 5 = strong sell</span>
          </div>
        </>
      )}
      {a.eps.length > 0 && (
        <>
          <h3>EPS estimates and revisions</h3>
          <div className="scroll">
            <table className="t">
              <thead><tr><th /><th>EPS</th><th>Δ30d</th><th>Δ90d</th><th title="Analysts revising up / down, last 30 days">Rev. 30d</th><th>Growth</th></tr></thead>
              <tbody>
                {a.eps.map((e) => (
                  <tr key={e.period}>
                    <td>{EPS_LABEL[e.period] ?? e.label}</td>
                    <td>{num(e.eps, 2)}</td>
                    <td className={tone(e.chg_30d)}>{pct(e.chg_30d)}</td>
                    <td className={tone(e.chg_90d)}>{pct(e.chg_90d)}</td>
                    <td><span className="pos">↑{e.up_30d ?? "–"}</span> <span className="neg">↓{e.down_30d ?? "–"}</span></td>
                    <td className={tone(e.growth)}>{pct(e.growth)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="small muted">Change of the consensus EPS estimate; EPS in {a.eps[0]?.currency ?? "the reporting currency"}.</p>
        </>
      )}
    </Card>
  );
}

/** The ticker in the weekly valuation snapshot: P/E against its sector (stocks) or ACWI (funds), EPS revisions,
 * and the P/E over the stored weeks. */
function SnapshotRows({ s }: { s: NonNullable<Profile["fundamentals"]["snapshot"]> }) {
  const g = s.gauges ?? {};
  const times = (v: Maybe) => (isNum(v) ? `${num(v, 2)}×` : "–");
  const fund = s.kind === "fund";
  return (
    <>
      <h3>Weekly snapshot{s.asof && <span className="muted small"> · {date(s.asof)} · {s.weeks} week{s.weeks === 1 ? "" : "s"} stored</span>}</h3>
      <KV rows={[
        [fund ? "Fund P/E (Yahoo)" : "P/E on next year's EPS", <Graded g={fund ? g.pe_vs_acwi : g.pe_vs_sector}>{num(s.pe, 1)}</Graded>,
          { help: fund ? "fund_pe" : "pe_fy1" }],
        [fund ? "vs ACWI" : `vs sector median${s.sector ? ` (${s.sector})` : ""}`,
          <Graded g={fund ? g.pe_vs_acwi : g.pe_vs_sector}>{times(fund ? s.pe_vs_acwi : s.pe_vs_sector)}</Graded>,
          { help: fund ? "pe_vs_acwi" : "pe_vs_sector", hint: (fund ? g.pe_vs_acwi : g.pe_vs_sector)?.label }],
        ["P/E percentile (own history)", num(s.pe_pct, 0), { hide: !fund, help: "pe_pct",
          hint: isNum(s.pe_pct) ? undefined : "needs 26 weeks" }],
        ["EPS estimate change 4w / 12w", <><Graded g={g.eps_rev}>{pct(s.eps_rev_4w)}</Graded> / {pct(s.eps_rev_12w)}</>,
          { hide: fund, help: "eps_rev", hint: isNum(s.eps_rev_4w) ? undefined : "builds up over 4 and 12 weeks" }],
        ["P/E over the stored weeks", s.history.length > 1 ? <Sparkline values={s.history.map((h) => h.pe)} /> : "–",
          { hide: s.history.length < 2 }],
      ]} />
    </>
  );
}

export function FundamentalsCard({ p }: { p: Profile }) {
  const f = p.fundamentals;
  return (
    <Card title="Valuation & fundamentals" meta={f}>
      {f.snapshot && <SnapshotRows s={f.snapshot} />}
      {f.snapshot && <h3>Yahoo profile</h3>}
      <KV rows={[
        ["Market cap", `${compact(f.market_cap)} ${f.currency ?? ""}`, { hint: isNum(f.market_cap_dkk) && f.currency !== "DKK" ? `${compact(f.market_cap_dkk)} DKK` : undefined }],
        ["P/E trailing / forward", `${num(f.trailing_pe, 1)} / ${num(f.forward_pe, 1)}`],
        ["PEG", num(f.peg, 2), { hide: !isNum(f.peg) }],
        ["EV / EBITDA", num(f.ev_ebitda, 1), { hide: !isNum(f.ev_ebitda) }],
        ["Price / book", num(f.price_to_book, 1), { hide: !isNum(f.price_to_book) }],
        ["Gross / operating / net margin", `${pct(f.gross_margin, 0, false)} / ${pct(f.operating_margin, 0, false)} / ${pct(f.profit_margin, 0, false)}`],
        ["Revenue growth (yoy)", pct(f.revenue_growth), { tone: f.revenue_growth }],
        ["Earnings growth (yoy)", pct(f.earnings_growth), { tone: f.earnings_growth }],
        ["Return on equity", pct(f.return_on_equity, 0, false), { hide: !isNum(f.return_on_equity) }],
        ["Debt / equity", num(f.debt_to_equity, 2), { hide: !isNum(f.debt_to_equity) }],
        ["Dividend yield", pct(f.dividend_yield, 2, false), { hint: isNum(f.payout_ratio) ? `payout ${pct(f.payout_ratio, 0, false)}` : undefined }],
        ["Beta (Yahoo / radar)", `${num(f.beta, 2)} / ${num(f.beta_radar, 2)}`],
        ["Short interest", pct(f.short_pct_float, 1, false), { hide: !isNum(f.short_pct_float) }],
      ]} />
      {(f.notes ?? []).length > 0 && <p className="small muted">Dropped: {(f.notes ?? []).join("; ")}.</p>}
    </Card>
  );
}

export function EtfCard({ p }: { p: Profile }) {
  const e = p.etf;
  if (!e) return null;
  const id = p.identity;
  return (
    <Card title="Fund look-through" meta={e}>
      <KV rows={[
        ["Expense ratio", pct(e.expense_ratio, 2, false)],
        ["Fund size", compact(e.total_assets), { hide: !isNum(e.total_assets) }],
        ["Provider", e.family ?? "–", { hide: !e.family }],
        ["Positive list (SKAT)", id.positive_list ?? "not checked", { hint: id.isin ?? "no ISIN in config", hide: !id.etf_group, help: "positive_list" }],
        ["UCITS version", id.ucits ? <TickerLink symbol={id.ucits} /> : "–", { hide: !id.ucits, help: "ucits" }],
      ]} />
      {p.fundamentals.snapshot && <SnapshotRows s={p.fundamentals.snapshot} />}
      {e.sector_weights.length > 0 && (
        <>
          <h3>Sectors</h3>
          {e.sector_weights.slice(0, 8).map((s) => (
            <div className="rec-row" key={s.sector} style={{ gridTemplateColumns: "150px 1fr 50px" }}>
              <span>{s.sector}</span>
              <div className="stack"><div className="bar" style={{ width: `${100 * s.weight}%` }} /></div>
              <span className="num small">{pct(s.weight, 1, false)}</span>
            </div>
          ))}
        </>
      )}
      {e.top_holdings.length > 0 && (
        <>
          <h3>Top holdings</h3>
          <table className="t">
            <tbody>
              {e.top_holdings.map((h) => (
                <tr key={h.symbol}>
                  <td><TickerLink symbol={h.symbol} name={h.name} />
                    {e.overlap.includes(h.symbol) && <> <Badge kind="accent">you hold</Badge></>}</td>
                  <td>{pct(h.weight, 1, false)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </Card>
  );
}

export function PeersCard({ p }: { p: Profile }) {
  const s = p.peers;
  const rot = s.rotation;
  const q = rot?.quadrant;
  return (
    <Card title="Sector & peers" meta={s}>
      {rot && (
        <KV rows={[
          [<>{rot.name} (<TickerLink symbol={rot.ticker} />)</>, <Badge kind={q === "Leading" ? "pos" : q === "Lagging" ? "neg" : q === "Weakening" ? "warn" : "accent"}>{q}</Badge>,
            { hint: `rel. 3m ${pct(rot.rel_r3m)}` }],
        ]} />
      )}
      {s.peers.length > 0 ? (
        <>
          <h3>Tracked stocks in {s.industry}</h3>
          <div className="scroll">
            <table className="t">
              <thead><tr><th>Ticker</th><th>Score</th><th>3M</th><th>6M</th><th>Trend</th></tr></thead>
              <tbody>
                {s.peers.map((x) => (
                  <tr key={x.ticker}>
                    <td><TickerLink symbol={x.ticker} name={x.name} /></td>
                    <td>{num(x.score, 0)}</td>
                    <td className={tone(x.r3m)}>{pct(x.r3m)}</td>
                    <td className={tone(x.r6m)}>{pct(x.r6m)}</td>
                    <td>{x.trend_ok === true ? "✓" : x.trend_ok === false ? "✗" : "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="small muted">Scores are percentiles within each stock's own region.</p>
        </>
      ) : (
        <p className="small muted">No tracked stocks in the same industry.</p>
      )}
    </Card>
  );
}

export function RecentCard({ p }: { p: Profile }) {
  const r = p.price.recent;
  return (
    <Card title="Last 20 sessions" meta={p.price}>
      <div className="scroll" style={{ maxHeight: 320, overflowY: "auto" }}>
        <table className="t">
          <thead><tr><th>Date</th><th>Close (adj.)</th><th>Change</th><th>Volume</th></tr></thead>
          <tbody>
            {r.map((b) => (
              <tr key={b.date}>
                <td>{date(b.date)}</td>
                <td>{price(b.close)}</td>
                <td className={tone(b.change)}>{pct(b.change, 2)}</td>
                <td>{compact(b.volume)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/** How this name lines up with your market views (your own subjective beliefs), with the radar's current
 *  evidence for each view, so "fits your view, but the data contradicts the view" is visible. */
export function ViewsCard({ p }: { p: Profile }) {
  const v = p.views;
  if (!v) {
    return (
      <Card title="Your market views">
        <p className="small muted">No market views yet. <Link to="/views">Write down where you think markets are heading</Link> and
          every ticker page shows how the name lines up with them.</p>
      </Card>
    );
  }
  const related = v.views.filter((x) => x.label !== "unrelated");
  return (
    <Card title="Your market views">
      <p><Badge kind={ALIGN_KIND[v.label]}>{ALIGN_TEXT[v.label]}</Badge>
        <span className="small muted"> {related.length} of {v.views.length} views apply</span></p>
      {related.map((x) => (
        <div key={x.id ?? x.statement} className="vw-row">
          <div><Badge kind={ALIGN_KIND[x.label]}>{x.label}</Badge> <b>{x.statement}</b>{" "}
            <span className="dots small" title={`Conviction ${x.conviction} of 5`}>{dots(x.conviction)}</span></div>
          <div className="small muted">{x.reasons.map((r) => r.text).join(" · ")}</div>
          {x.evidence && <div className="small">The radar&apos;s data on this view: <Badge kind={VERDICT_KIND[x.evidence]}>{x.evidence}</Badge></div>}
        </div>
      ))}
      {related.length === 0 && <p className="small muted">None of your views clearly applies to this name.</p>}
      <p className="small muted">Your views are subjective beliefs, not forecasts. <Link to="/views">Edit your views</Link></p>
    </Card>
  );
}

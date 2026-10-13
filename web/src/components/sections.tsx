import { Link } from "react-router-dom";
import type { Profile, Windows } from "../api/client";
import { compact, date, daysUntil, isNum, num, pct, price, tone, type Maybe } from "../lib/format";
import { Badge, Card, KV, Signed } from "./ui";

const WIN: [keyof Windows, string][] = [["r1w", "1W"], ["r1m", "1M"], ["r3m", "3M"], ["r6m", "6M"], ["ytd", "YTD"], ["r1y", "1Y"]];

function Row({ label, w, hint }: { label: string; w?: Windows | null; hint?: string }) {
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
            <Row label={`vs ${pr.sector_etf ?? "sector"}`} w={pr.vs_sector} />
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
        ["Momentum score", isNum(m.score) ? `${num(m.score, 0)} / 100` : "–",
          { hint: m.rank ? `rank ${m.rank} of ${m.group_size}` : undefined }],
        ["3m / 6m return", <><Signed v={m.r3m}>{pct(m.r3m)}</Signed> / <Signed v={m.r6m}>{pct(m.r6m)}</Signed></>],
        ["12-1 month return", pct(m.r12_1), { tone: m.r12_1, hint: "skips the last month" }],
        ["Price vs 50-day", yesNo(m.above50, "above", "below"), { hint: price(m.sma50) }],
        ["Price vs 200-day", yesNo(m.above200, "above", "below"), { hint: price(m.sma200) }],
        ["Trend (50d > rising 200d)", yesNo(m.trend_ok, "intact", "not intact")],
        ["From 52-week high", pct(m.from_high), { tone: m.from_high }],
        ["Volume, 20d vs 6m avg", isNum(m.vol_surge) ? `${num(m.vol_surge, 2)}×` : "–"],
      ]} />
      <p className="small muted">Score: {m.score_basis}{m.region_label ? `, ${m.region_label}` : ""}.</p>
    </Card>
  );
}

export function TechnicalsCard({ p }: { p: Profile }) {
  const t = p.technicals;
  const state = (s: string | null | undefined) =>
    s ? <Badge kind={s === "overbought" || s === "bearish" ? "neg" : s === "oversold" || s === "bullish" ? "pos" : ""}>{s}</Badge> : null;
  return (
    <Card title="Technicals" meta={t}>
      <KV rows={[
        ["RSI 14", <>{num(t.rsi14, 1)} {state(t.rsi_state)}</>],
        ["MACD 12/26/9", <>{num(t.macd_hist, 2)} {state(t.macd_state)}</>, { hint: "histogram" }],
        ["Bollinger %B", num(t.bb_pct_b, 2), { hint: "0 = lower band, 1 = upper" }],
        ["ATR 14", price(t.atr), { hint: pct(t.atr_pct, 1, false) + " of price" }],
        ["Volatility (3m, annualised)", pct(t.vol_3m, 1, false)],
        ["Max drawdown (1y)", pct(t.max_drawdown_1y), { tone: t.max_drawdown_1y }],
        ["Beta / correlation vs ACWI", `${num(t.beta_acwi, 2)} / ${num(t.corr_acwi, 2)}`, { hint: "weekly, 1y" }],
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
        ["Trailing stop", price(l.stop, cur), { hint: pct(l.stop_pct), tone: -1 }],
        ["Take-profit", l.take_profit ? price(l.take_profit, cur) : "none", { hint: l.take_profit ? pct(l.tp_pct) : undefined }],
        ["Stop width k × ATR", isNum(l.k) ? `${num(l.k, 1)} × ${price(l.atr)}` : "–"],
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
            ["Mean target", price(a.target_mean, cur), { hint: pct(a.upside) + " upside", tone: a.upside }],
            ["Consensus", `${a.rec_key ?? "–"}${isNum(a.rec_mean) ? ` (${num(a.rec_mean, 1)})` : ""}`,
              { hint: isNum(a.n_analysts) ? `${a.n_analysts} analysts` : undefined }],
            ["Target change, 30 days", pct(a.target_change), { tone: a.target_change, hide: !isNum(a.target_change) }],
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

export function FundamentalsCard({ p }: { p: Profile }) {
  const f = p.fundamentals;
  return (
    <Card title="Valuation & fundamentals" meta={f}>
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
        ["Positive list (SKAT)", id.positive_list ?? "not checked", { hint: id.isin ?? "no ISIN in config", hide: !id.etf_group }],
        ["UCITS version", id.ucits ?? "–", { hide: !id.ucits }],
      ]} />
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
                  <td><Link to={`/ticker/${encodeURIComponent(h.symbol)}`}>{h.symbol}</Link> <span className="muted small trunc" title={h.name ?? ""}>{h.name}</span>
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
          [`${rot.name} (${rot.ticker})`, <Badge kind={q === "Leading" ? "pos" : q === "Lagging" ? "neg" : q === "Weakening" ? "warn" : "accent"}>{q}</Badge>,
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
                    <td><Link to={`/ticker/${encodeURIComponent(x.ticker)}`}>{x.ticker}</Link> <span className="muted small trunc" title={x.name ?? ""}>{x.name}</span></td>
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

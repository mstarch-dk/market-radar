import { useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, type EvidenceView, type ForwardGroup, type LongrunCard, type LongrunRow, type ReportHead, type ScoreCard,
  type ScoreRow } from "../api/client";
import { Loaded, PageHead } from "../components/cells";
import { DataTable, type Col } from "../components/DataTable";
import { Tabs, useTabParam } from "../components/Tabs";
import { Term } from "../components/Term";
import { Badge, KV } from "../components/ui";
import { headStatus, strongT, tText } from "../lib/evidence";
import { date, isNum, num, pct, type Maybe } from "../lib/format";
import { pageChapter, useGuideTree } from "../lib/guide";

type Signal = "momentum" | "quality" | "value" | "qv";
type Horizon = ScoreCard["horizons"][number];
type Verdict = ScoreCard["verdicts"][number];
type Panel = LongrunCard["panels"][number];
type Part = Panel["by_decade"][number];
type BaseRate = LongrunCard["base_rates"][number];
type Rec = ForwardGroup["records"][number];

const SIGNALS: [Signal, string][] = [["momentum", "Momentum"], ["quality", "Quality"], ["value", "Value"], ["qv", "K+V"]];
const ic = (v: number) => num(v, 3);
const sp = (v: number) => pct(v, 2);

/** A mean with its t beside it; a |t| of 2 or more is set off, a missing t says so ("t n/a"). */
function MeanT({ m, t, fmt }: { m: Maybe; t: Maybe; fmt: (v: number) => string }) {
  if (!isNum(m)) return <span className="muted">–</span>;
  return <span className="ev-mt">{fmt(m)} <small className={strongT(t) ? "ev-t strong" : "ev-t"}>{tText(m, t)}</small></span>;
}

function StatusBadge({ h }: { h: ReportHead }) {
  const s = headStatus(h);
  return <Badge kind={s.kind} title={h.reason ?? undefined}>{s.label}</Badge>;
}

/** What a card says without numbers: not run yet (or unreadable), why, and the command that writes it. */
function NotRun({ h }: { h: ReportHead }) {
  return (
    <div className="ev-notrun">
      <p>{h.status === "missing" ? "Not run yet." : <>The report can&apos;t be read: {h.reason}</>}</p>
      <p className="small">Run it in a terminal in the radar&apos;s folder (it takes a few minutes):</p>
      <pre className="ev-cmd"><code>uv run {h.command}</code></pre>
    </div>
  );
}

/** The header lines every card shares: status, age, the rule it tested and today's. */
function HeadKV({ h, extra = [] }: { h: ReportHead; extra?: Parameters<typeof KV>[0]["rows"] }) {
  const s = headStatus(h);
  return (
    <KV rows={[
      ["Status", <StatusBadge h={h} />],
      ["Data to", h.data_asof ? `${date(h.data_asof)}${isNum(h.age_days) ? ` (${h.age_days} days ago)` : ""}` : "–"],
      ["Run", h.created ? h.created.replace("T", " ").slice(0, 16) : "–"],
      ["Rule", <code>{h.rule_hash ?? "not recorded"}</code>,
        { help: "ev_rule", hint: s.greyed ? <>today&apos;s rule: <code>{h.rule_hash_now ?? "–"}</code></> : undefined }],
      ...extra,
    ]} />
  );
}

/** A greyed card: another (or an unrecorded) rule. Its numbers stay inside it, under a line that says why. */
function Greyed({ h, children }: { h: ReportHead; children: ReactNode }) {
  if (!headStatus(h).greyed) return <>{children}</>;
  return (
    <div className="ev-stale-wrap">
      <p className="notes" role="status">
        <b>Older rule.</b> {h.reason}{h.reason && !h.reason.endsWith(".") ? "." : ""} These numbers are the old rule&apos;s and are shown greyed, apart from current ones.
      </p>
      <div className="ev-stale" aria-label="Numbers from an older rule">{children}</div>
    </div>
  );
}

/** A diverging bar for a value against the largest one shown (right = positive). */
function Bar({ v, max }: { v: Maybe; max: number }) {
  if (!isNum(v) || max <= 0) return <span className="dbar" aria-hidden="true" />;
  const w = `${Math.min(Math.abs(v) / max, 1) * 100}%`;
  return (
    <span className="dbar" aria-hidden="true">
      <span className="l">{v < 0 && <i style={{ width: w }} />}</span>
      <span className="r">{v > 0 && <i style={{ width: w }} />}</span>
    </span>
  );
}

/** Quintile excess returns, Q1 (worst score) to Q5 (best), as five bars around zero. */
function QBars({ q }: { q: Maybe[] | null | undefined }) {
  const vals = (q ?? []).map((v) => (isNum(v) ? v : null));
  const max = Math.max(1e-9, ...vals.map((v) => Math.abs(v ?? 0)));
  if (vals.length === 0 || vals.every((v) => v === null)) return <span className="muted">–</span>;
  const title = vals.map((v, i) => `Q${i + 1} ${v === null ? "–" : pct(v, 2)}`).join(", ");
  return (
    <svg className="ev-q" width={60} height={24} viewBox="0 0 60 24" role="img" aria-label={title}>
      <title>{title}</title>
      <line x1={0} x2={60} y1={12} y2={12} className="ev-q-axis" />
      {vals.map((v, i) => v === null ? null : (
        <rect key={i} x={i * 12 + 2} width={8} y={v >= 0 ? 12 - (v / max) * 11 : 12} height={Math.max((Math.abs(v) / max) * 11, 0.5)}
          className={v >= 0 ? "pos" : "neg"} />
      ))}
    </svg>
  );
}

const hLabel = (h: number) => `${h} mo`;

function scoreCols(maxIc: number, nTop: Maybe): Col<Horizon>[] {
  const a = (x: Horizon): ScoreRow | null => x.all ?? null;
  return [
    { key: "h", label: "Ahead", align: "l", sort: (x) => x.h, render: (x) => hLabel(x.h) },
    { key: "dates", label: "Dates", sort: (x) => a(x)?.dates, render: (x) => num(a(x)?.dates, 0) },
    { key: "ic", label: "IC", help: "ev_ic", sort: (x) => a(x)?.ic_mean, render: (x) => <MeanT m={a(x)?.ic_mean} t={a(x)?.ic_t} fmt={ic} /> },
    { key: "bar", label: "", name: "IC (bar)", csv: false, render: (x) => <Bar v={a(x)?.ic_mean} max={maxIc} /> },
    { key: "pos", label: "IC>0", sort: (x) => a(x)?.ic_pos, render: (x) => pct(a(x)?.ic_pos, 0, false) },
    { key: "q", label: "Q1–Q5", help: "ev_quintiles", csv: false, render: (x) => <QBars q={a(x)?.q} /> },
    { key: "spread", label: "Q5−Q1", help: "ev_spread", sort: (x) => a(x)?.spread,
      render: (x) => <MeanT m={a(x)?.spread} t={a(x)?.spread_t} fmt={sp} /> },
    { key: "top", label: `Top ${nTop ?? "N"} vs all`, help: "ev_top", sort: (x) => a(x)?.top_excess,
      render: (x) => <MeanT m={a(x)?.top_excess} t={a(x)?.top_excess_t} fmt={sp} /> },
    { key: "acwi", label: `Top ${nTop ?? "N"} vs ACWI`, help: "ev_top_vs_acwi", sort: (x) => a(x)?.top_vs_acwi,
      render: (x) => <MeanT m={a(x)?.top_vs_acwi ?? (isNum(a(x)?.top_dkk) && isNum(a(x)?.acwi_dkk) ? a(x)!.top_dkk! - a(x)!.acwi_dkk! : null)}
        t={a(x)?.top_vs_acwi_t} fmt={sp} /> },
    { key: "beat", label: "Ahead of ACWI", sort: (x) => a(x)?.top_beats_acwi, render: (x) => pct(a(x)?.top_beats_acwi, 0, false) },
  ];
}

type SplitRow = { h: number; part: "in-sample" | "holdout"; row: ScoreRow | null };

const splitCols: Col<SplitRow>[] = [
  { key: "h", label: "Ahead", align: "l", sort: (r) => r.h, render: (r) => hLabel(r.h) },
  { key: "part", label: "Part", align: "l", sort: (r) => r.part, render: (r) => r.part === "holdout" ? <b>holdout</b> : "in-sample" },
  { key: "dates", label: "Dates", sort: (r) => r.row?.dates, render: (r) => num(r.row?.dates, 0) },
  { key: "ic", label: "IC", sort: (r) => r.row?.ic_mean, render: (r) => <MeanT m={r.row?.ic_mean} t={r.row?.ic_t} fmt={ic} /> },
  { key: "spread", label: "Q5−Q1", sort: (r) => r.row?.spread, render: (r) => <MeanT m={r.row?.spread} t={r.row?.spread_t} fmt={sp} /> },
  { key: "top", label: "Top N vs all", sort: (r) => r.row?.top_excess,
    render: (r) => <MeanT m={r.row?.top_excess} t={r.row?.top_excess_t} fmt={sp} /> },
  { key: "acwi", label: "Top N vs ACWI", sort: (r) => r.row?.top_vs_acwi,
    render: (r) => <MeanT m={r.row?.top_vs_acwi} t={r.row?.top_vs_acwi_t} fmt={sp} /> },
];

const VERDICT_KIND: Record<string, string> = { "candidate improvement": "pos", "not better": "", "not enough data": "na" };

const verdictCols: Col<Verdict>[] = [
  { key: "variant", label: "Variant", align: "l", sort: (v) => v.variant, search: (v) => v.variant, render: (v) => <code>{v.variant}</code> },
  { key: "h", label: "Ahead", sort: (v) => v.h, render: (v) => hLabel(v.h) },
  { key: "label", label: "Verdict", help: "ev_verdict", align: "l", sort: (v) => v.label,
    filter: { kind: "enum", value: (v) => [v.label ?? "–"] },
    render: (v) => <Badge kind={VERDICT_KIND[v.label ?? ""] ?? "warn"}>{v.label ?? "–"}</Badge> },
  { key: "is", label: "In-sample IC", sort: (v) => v.in_sample_ic, render: (v) => num(v.in_sample_ic, 3) },
  { key: "ho", label: "Holdout IC", sort: (v) => v.holdout_ic, render: (v) => <MeanT m={v.holdout_ic} t={v.holdout_ic_t} fmt={ic} /> },
  { key: "diff", label: "Holdout difference t", sort: (v) => v.holdout_diff_t,
    render: (v) => isNum(v.holdout_diff_t) ? <span className={strongT(v.holdout_diff_t) ? "" : "muted"}>{num(v.holdout_diff_t, 1)}</span> : "–" },
];

function ScoreCardView({ c, holdoutNow }: { c: ScoreCard; holdoutNow: string }) {
  const h = c.head;
  const s = headStatus(h);
  const maxIc = Math.max(0, ...c.horizons.map((x) => Math.abs(x.all?.ic_mean ?? 0)));
  const splits: SplitRow[] = c.horizons.flatMap((x) => [
    { h: x.h, part: "in-sample" as const, row: x.in_sample ?? null }, { h: x.h, part: "holdout" as const, row: x.holdout ?? null }]);
  const u = c.universe;
  return (
    <div className="card ev-card" id={`ev-score-${h.signal}`}>
      <h2>{h.label} <StatusBadge h={h} /></h2>
      {!s.numbers ? <NotRun h={h} /> : (
        <Greyed h={h}>
          <div className="grid">
            <HeadKV h={h} extra={[
              ["Universe", u ? <>{c.us_only ? `${num(u.fund_names, 0)} US stocks (SEC EDGAR)` : `${num(u.tickers, 0)} stocks`},
                formation dates {u.first ?? "–"} to {u.last ?? "–"}</> : "–"],
              ["Holdout from", c.holdout_from ?? "–", { help: "ev_holdout",
                hint: c.holdout_from && c.holdout_from !== holdoutNow ? `settings today: ${holdoutNow}` : undefined }],
              ["Variants tried", num(c.variants_tried, 0), { help: "ev_variants" }],
              ["Top-quintile turnover", pct(c.turnover, 0, false), { hide: !isNum(c.turnover), hint: "a month" }],
              ["Rank correlation with momentum", num(c.momentum_corr, 2), { hide: !isNum(c.momentum_corr) }],
            ]} />
          </div>
          <h3>The score ({c.baseline ?? "baseline"}), all formation dates</h3>
          <DataTable id={`ev${h.signal}`} csvName={`evidence-${h.signal}`} rows={c.horizons} cols={scoreCols(maxIc, c.n_top)}
            rowKey={(x) => String(x.h)} toolbar={false} empty="No horizons in this report." />
          <h3><Term k="ev_holdout">In-sample vs holdout</Term> <span className="small muted">(holdout from {c.holdout_from ?? holdoutNow})</span></h3>
          <DataTable id={`ev${h.signal}s`} csvName={`evidence-${h.signal}-holdout`} rows={splits} cols={splitCols}
            rowKey={(r) => `${r.h}-${r.part}`} toolbar={false} />
          {c.verdicts.length > 0 && (
            <details>
              <summary>Variants against the score ({c.verdicts.length} verdicts)</summary>
              <DataTable id={`ev${h.signal}v`} csvName={`evidence-${h.signal}-verdicts`} rows={c.verdicts} cols={verdictCols}
                rowKey={(v) => `${v.variant}-${v.h}`} />
            </details>
          )}
          {(c.notes.length > 0 || c.caveats.length > 0) && (
            <ul className="small muted perf-notes">
              {c.notes.map((n) => <li key={n} className="warn-text">{n}</li>)}
              {c.caveats.map((n) => <li key={n}>{n}</li>)}
            </ul>
          )}
        </Greyed>
      )}
    </div>
  );
}

function longrunCols(): Col<{ key: string; label: string; row: LongrunRow | null }>[] {
  return [
    { key: "label", label: "", name: "Part", align: "l", sort: (r) => r.label, render: (r) => r.label },
    { key: "dates", label: "Months", sort: (r) => r.row?.dates, render: (r) => num(r.row?.dates, 0) },
    { key: "eff", label: "Eff. N", help: "ev_eff_n", sort: (r) => r.row?.eff_n, render: (r) => num(r.row?.eff_n, 0) },
    { key: "ic", label: "IC", help: "ev_ic", sort: (r) => r.row?.ic_mean, render: (r) => <MeanT m={r.row?.ic_mean} t={r.row?.ic_t} fmt={ic} /> },
    { key: "spread", label: "Q5−Q1", sort: (r) => r.row?.spread, render: (r) => <MeanT m={r.row?.spread} t={r.row?.spread_t} fmt={sp} /> },
    { key: "top", label: "Top N vs all", sort: (r) => r.row?.top_excess,
      render: (r) => <MeanT m={r.row?.top_excess} t={r.row?.top_excess_t} fmt={sp} /> },
    { key: "mkt", label: "Top N vs market", sort: (r) => r.row?.top_vs_market,
      render: (r) => <MeanT m={r.row?.top_vs_market} t={r.row?.top_vs_market_t} fmt={sp} /> },
  ];
}

const baseCols: Col<BaseRate>[] = [
  { key: "label", label: "Factor (long-short)", align: "l", sort: (b) => b.label, render: (b) => b.label },
  { key: "span", label: "Years", align: "l", sort: (b) => b.first, render: (b) => b.first ? `${b.first.slice(0, 4)}–${(b.last ?? "").slice(0, 4)}` : "–" },
  { key: "ann", label: "A year", sort: (b) => b.ann_return, render: (b) => <MeanT m={b.ann_return} t={b.t} fmt={(v) => pct(v, 1)} /> },
  { key: "ten", label: "Last 10 years", sort: (b) => b.last_10y_ann, render: (b) => pct(b.last_10y_ann, 1) },
  { key: "n6", label: "6-mo windows lost", sort: (b) => b.share_neg_6m, render: (b) => pct(b.share_neg_6m, 0, false) },
  { key: "n12", label: "12-mo lost", sort: (b) => b.share_neg_12m, render: (b) => pct(b.share_neg_12m, 0, false) },
  { key: "dd", label: "Worst fall", sort: (b) => b.max_dd, render: (b) => pct(b.max_dd, 0) },
];

function PanelView({ p }: { p: Panel }) {
  const hs = p.horizons.map((x) => x.h);
  const [h, setH] = useState<number>(hs.includes(6) ? 6 : (hs[0] ?? 6));
  if (p.error) return <p className="small warn-text">Not studied: {p.error}</p>;
  const main = p.horizons.flatMap((x) => [
    { key: `${x.h}a`, label: `${hLabel(x.h)}, all`, row: x.all ?? null },
    { key: `${x.h}h`, label: `${hLabel(x.h)}, holdout`, row: x.holdout ?? null }]);
  const parts = (xs: Part[]) => xs.filter((x) => x.h === h).map((x) => ({ key: x.part, label: x.part, row: x.row ?? null }));
  return (
    <>
      <p className="small muted">{num(p.members, 0)} members, top {num(p.n_top, 0)}, {num(p.months, 0)} formation months
        {p.first && <> from {p.first.slice(0, 7)} to {(p.last ?? "").slice(0, 7)}</>}; {num(p.variants_tried, 0)} variants tried.</p>
      <DataTable id={`evlr${p.key}`} csvName={`evidence-longrun-${p.key}`} rows={main} cols={longrunCols()} rowKey={(r) => r.key} toolbar={false} />
      {hs.length > 1 && <Tabs tabs={hs.map((x) => [String(x), hLabel(x)] as [string, string])} value={String(h)}
        onChange={(v) => setH(Number(v))} label="Horizon for the splits" />}
      <div className="grid">
        <div>
          <h3>By decade</h3>
          <DataTable id={`evlrd${p.key}`} csvName={`evidence-longrun-${p.key}-decades`} rows={parts(p.by_decade)} cols={longrunCols()}
            rowKey={(r) => r.key} toolbar={false} empty="No decade split." />
        </div>
        <div>
          <h3>In and out of US recessions</h3>
          <DataTable id={`evlrr${p.key}`} csvName={`evidence-longrun-${p.key}-recessions`} rows={parts(p.by_recession)}
            cols={longrunCols()} rowKey={(r) => r.key} toolbar={false} empty="No recession split." />
        </div>
      </div>
      {p.verdicts.length > 0 && (
        <details>
          <summary>Variants against the score ({p.verdicts.length} verdicts)</summary>
          <DataTable id={`evlrv${p.key}`} csvName={`evidence-longrun-${p.key}-verdicts`} rows={p.verdicts} cols={verdictCols}
            rowKey={(v) => `${v.variant}-${v.h}`} />
        </details>
      )}
    </>
  );
}

function LongrunView({ c, holdoutNow }: { c: LongrunCard; holdoutNow: string | null | undefined }) {
  const h = c.head;
  const s = headStatus(h);
  const [key, setKey] = useState<string>(c.panels[0]?.key ?? "");
  const panel = c.panels.find((p) => p.key === key) ?? c.panels[0];
  const sv = c.survivorship;
  return (
    <div className="card ev-card" id="ev-longrun">
      <h2>{h.label} <StatusBadge h={h} /></h2>
      {!s.numbers ? <NotRun h={h} /> : (
        <Greyed h={h}>
          <HeadKV h={h} extra={[["Holdout from", c.holdout_from ?? holdoutNow ?? "–", { help: "ev_holdout" }]]} />
          {c.panels.length > 1 && <Tabs tabs={c.panels.map((p) => [p.key, p.label ?? p.key] as [string, string])} value={panel?.key ?? ""}
            onChange={setKey} label="Panel" />}
          {panel && <PanelView key={panel.key} p={panel} />}
          {sv && (
            <>
              <h3><Term k="ev_survivorship">Survivorship gauge</Term></h3>
              <KV rows={[
                ["Implied haircut", pct(sv.implied_haircut, 0, false), { hint: `configured ${pct(sv.configured_haircut, 0, false)}` }],
                ["Top quintile a month, score study", pct(sv.study_top_quintile_excess_1m, 2)],
                ["The same, all US stocks (no survivorship)", pct(sv.survivorship_free_same_months, 2),
                  { hint: `since 1927: ${pct(sv.survivorship_free_since_1927, 2)}` }],
                ["Months compared", sv.first ? `${sv.first.slice(0, 7)} to ${(sv.last ?? "").slice(0, 7)}` : "–"],
              ]} />
              {sv.note && <p className="small muted">{sv.note}.</p>}
            </>
          )}
          {c.base_rates.length > 0 && (
            <>
              <h3>Base rates of the factors</h3>
              <DataTable id="evbase" csvName="evidence-base-rates" rows={c.base_rates} cols={baseCols} rowKey={(b) => b.label} toolbar={false} />
            </>
          )}
          {(c.notes.length > 0 || c.caveats.length > 0) && (
            <ul className="small muted perf-notes">
              {c.notes.map((n) => <li key={n} className="warn-text">{n}</li>)}
              {c.caveats.map((n) => <li key={n}>{n}</li>)}
            </ul>
          )}
        </Greyed>
      )}
    </div>
  );
}

const months = (days: Maybe) => (isNum(days) ? `${num(days / (365.25 / 12), 1)} mo` : "–");

/** A record younger than its minimum is listed muted and never ranked: it sorts after the judged ones. */
const judged = (r: Rec, v: Maybe) => (r.too_short || !isNum(v) ? null : v);

const forwardCols: Col<Rec>[] = [
  { key: "label", label: "Record", align: "l", sort: (r) => r.label, search: (r) => r.label,
    render: (r) => <span className={r.too_short ? "muted" : ""}>{r.label} {r.too_short && <Badge kind="na" title="Younger than the minimum: listed, not judged">
      <Term k="ev_too_short">too short</Term></Badge>}</span> },
  { key: "start", label: "Since", align: "l", sort: (r) => r.start, render: (r) => date(r.start) },
  { key: "age", label: "Age", sort: (r) => r.days, render: (r) => months(r.days) },
  { key: "ret", label: "Return", sort: (r) => judged(r, r.ret), render: (r) => <span className={r.too_short ? "muted" : ""}>{pct(r.ret)}</span> },
  { key: "acwi", label: "ACWI", sort: (r) => judged(r, r.acwi), render: (r) => <span className={r.too_short ? "muted" : ""}>{pct(r.acwi)}</span> },
  { key: "excess", label: "vs ACWI", sort: (r) => judged(r, r.excess),
    render: (r) => <span className={r.too_short ? "muted" : isNum(r.excess) ? (r.excess >= 0 ? "pos" : "neg") : ""}>{pct(r.excess)}</span> },
  { key: "dd", label: "Max drawdown", sort: (r) => judged(r, r.max_dd), render: (r) => <span className={r.too_short ? "muted" : ""}>{pct(r.max_dd)}</span> },
  { key: "note", label: "", name: "Note", align: "l", csv: (r) => r.note ?? "", render: (r) => <span className="small muted">{r.note}</span> },
];

function ForwardBlock({ id, title, help, g }: { id: string; title: string; help: string; g: ForwardGroup }) {
  const c = g.cohort;
  return (
    <div className="card">
      <h3>{title}</h3>
      <p className="small muted">{help}</p>
      {!g.running ? <p className="small muted">{g.note}</p> : (
        <>
          <DataTable id={id} csvName={`evidence-${id}`} rows={g.records} cols={forwardCols} rowKey={(r) => r.label} toolbar={false} />
          {c && (c.enough
            ? <p className="small">Mean excess {pct(c.mean_excess)} over {c.count}, ahead of ACWI in {pct(c.beat_acwi, 0, false)} of them.
              <span className="muted"> No t: the windows overlap and the count is small.</span></p>
            : <p className="small muted">{c.note}</p>)}
          {g.note && <p className="small muted">{g.note}</p>}
        </>
      )}
    </div>
  );
}

function StatusStrip({ d, onScore }: { d: EvidenceView; onScore: (s: Signal) => void }) {
  const go = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  const chip = (h: ReportHead, onClick?: () => void) => (
    <button key={`${h.name}-${h.signal ?? ""}`} type="button" className={`ev-chip ${headStatus(h).kind}`} onClick={onClick}
      title={h.reason ?? undefined}>
      {h.label} <small>{headStatus(h).label}</small>
    </button>
  );
  return (
    <div className="ev-strip" aria-label="The study reports">
      {d.scores.map((c) => chip(c.head, () => { onScore(c.head.signal as Signal); go("ev-scores"); }))}
      {chip(d.longrun.head, () => go("ev-longrun"))}
      {d.rules.map((h) => chip(h, () => go("ev-rules")))}
    </div>
  );
}

const ruleCols: Col<ReportHead>[] = [
  { key: "label", label: "Study", align: "l", sort: (h) => h.label, render: (h) => h.label },
  { key: "status", label: "Status", align: "l", sort: (h) => h.status, render: (h) => <StatusBadge h={h} /> },
  { key: "asof", label: "Data to", align: "l", sort: (h) => h.data_asof, render: (h) => date(h.data_asof) },
  { key: "rule", label: "Rule", align: "l", sort: (h) => h.rule_hash, render: (h) => <code>{h.rule_hash ?? "–"}</code> },
  { key: "cmd", label: "Command", align: "l", csv: (h) => h.command, render: (h) => <code className="small">uv run {h.command}</code> },
];

/** The Evidence page: how well the scores have worked, from the study reports and the forward record. */
export function Evidence() {
  const q = useQuery({ queryKey: ["evidence"], queryFn: api.evidence, retry: false, staleTime: 60_000 });
  const [signal, setSignal] = useTabParam(SIGNALS.map(([k]) => k), "momentum");
  const guide = useGuideTree().data;
  const chapter = guide ? pageChapter(guide.page_links, "/evidence") : null;
  return (
    <Loaded q={q} title="Evidence">
      {(d) => {
        const card = d.scores.find((c) => c.head.signal === signal) ?? d.scores[0];
        return (
          <>
            <PageHead title="Evidence" generated={d.generated}>
              How well the radar&apos;s scores have ranked stocks: each study tested at every past month-end on the returns
              that followed, with a <Term k="ev_nw_t">t-statistic</Term> next to every mean and a holdout the rules were never
              tuned on (from {d.holdout_from}); the momentum rule over decades of data without survivorship bias; and the
              forward record, picked before the returns were known, against ACWI. A study run under another rule than
              today&apos;s is greyed. Read from the study reports: nothing is computed here. Analysis, not advice.
            </PageHead>
            <StatusStrip d={d} onScore={setSignal} />
            <section className="group" id="ev-scores">
              <h2>The scores, tested at every past month-end</h2>
              <Tabs tabs={SIGNALS.map(([k, l]) => [k, <>{l} <StatusDot h={d.scores.find((c) => c.head.signal === k)?.head} /></>])}
                value={signal} onChange={setSignal} label="Score" />
              {card && <ScoreCardView key={card.head.signal} c={card} holdoutNow={d.holdout_from} />}
            </section>
            <section className="group">
              <h2>The momentum rule over decades</h2>
              <LongrunView c={d.longrun} holdoutNow={d.longrun_holdout_from} />
            </section>
            <section className="group" id="ev-forward">
              <h2><Term k="ev_forward">The forward record</Term></h2>
              {d.forward ? (
                <div className="grid">
                  <ForwardBlock id="evab" title="A/B test" g={d.forward.abtest}
                    help="Kvalitet + værdi, momentum and 50/50 as virtual portfolios, picked once a month, against ACWI with the same flows." />
                  <ForwardBlock id="evpt" title="Paper trail (picks-live)" g={d.forward.paper_trail}
                    help="Each month's top 15 by the score, bought and kept, against ACWI from its own day." />
                  <ForwardBlock id="evpr" title="Frozen proposals" g={d.forward.proposals}
                    help="Each proposal's picks, frozen before the model's numbers, against ACWI over the same days." />
                </div>
              ) : <p className="note">{d.notes.join(" ")}</p>}
            </section>
            <section className="group" id="ev-rules">
              <h2>The rule studies</h2>
              <div className="card">
                <DataTable id="evrules" csvName="evidence-rules" rows={d.rules} cols={ruleCols} rowKey={(h) => h.name} toolbar={false} />
                <p className="small muted">Their numbers are on the pages that use them: proposals and the stop rule.</p>
              </div>
            </section>
            {chapter && (
              <section className="group">
                <h2>Notes</h2>
                <ul className="small muted perf-notes">
                  {d.forward && d.notes.map((n) => <li key={n}>{n}</li>)}
                  <li><Link to={`/guide/${chapter}`}>How to read the evidence (guide)</Link></li>
                </ul>
              </section>
            )}
          </>
        );
      }}
    </Loaded>
  );
}

function StatusDot({ h }: { h: ReportHead | undefined }) {
  if (!h) return null;
  const s = headStatus(h);
  return <span className={`ev-dot ${s.kind}`} title={s.label} aria-label={s.label} />;
}

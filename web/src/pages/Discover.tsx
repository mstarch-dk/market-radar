import { useQuery } from "@tanstack/react-query";
import { fundValCols, stockValCols } from "../components/valuationCols";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ApiError, api, type DiscoveryMarket, type DiscoveryRow, type DiscoveryView } from "../api/client";
import { Check, PageHead, Pct, Quadrant } from "../components/cells";
import { DataTable, type Col } from "../components/DataTable";
import { TableToolbar } from "../components/TableToolbar";
import { TickerLink } from "../components/TickerLink";
import { fmt, Treemap, type TreemapItem } from "../components/Treemap";
import { Badge } from "../components/ui";
import { UpdatePanel } from "../components/UpdatePanel";
import { withViews } from "../components/ViewsColumn";
import { WatchStar } from "../components/WatchButton";
import { compact, date, num, pct } from "../lib/format";
import { EMPTY, filterRows, type TableState } from "../lib/tableState";
import { useTableState } from "../lib/useTableState";
import { useAlignment } from "../lib/views";

const ID = "d";

const COLOR = {
  r1w: { label: "1 week", steps: [0.01, 0.025, 0.05, 0.1], get: (r: DiscoveryRow) => r.r1w, f: fmt.pct },
  r1m: { label: "1 month", steps: [0.02, 0.05, 0.1, 0.2], get: (r: DiscoveryRow) => r.r1m, f: fmt.pct },
  r3m: { label: "3 months", steps: [0.04, 0.1, 0.2, 0.35], get: (r: DiscoveryRow) => r.r3m, f: fmt.pct },
  r6m: { label: "6 months", steps: [0.05, 0.15, 0.3, 0.5], get: (r: DiscoveryRow) => r.r6m, f: fmt.pct },
  score: { label: "Score", steps: [10, 20, 30, 40], get: (r: DiscoveryRow) => (r.score ?? null) === null ? null : r.score! - 50,
    f: (v: number | null) => fmt.score(v === null ? null : v + 50) },
  d_score: { label: "Δ score (1m)", steps: [5, 10, 20, 30], get: (r: DiscoveryRow) => r.d_score, f: fmt.signed },
} as const;
type ColorKey = keyof typeof COLOR;

const SIZE = {
  sqrtcap: { label: "√ market cap", get: (r: DiscoveryRow) => (r.market_cap_dkk ? Math.sqrt(r.market_cap_dkk) : null) },
  cap: { label: "Market cap", get: (r: DiscoveryRow) => r.market_cap_dkk ?? null },
  sqrtliq: { label: "√ traded value", get: (r: DiscoveryRow) => (r.liquidity_dkk ? Math.sqrt(r.liquidity_dkk) : null) },
  equal: { label: "Equal", get: () => 1 },
} as const;
type SizeKey = keyof typeof SIZE;

const GROUP = {
  sector: { label: "Sector", get: (r: DiscoveryRow) => r.sector ?? "Sector unknown" },
  category: { label: "Category", get: (r: DiscoveryRow) => r.category ?? "Other" },
  country: { label: "Country", get: (r: DiscoveryRow) => r.country ?? r.exchange ?? "Unknown" },
  size: { label: "Size", get: (r: DiscoveryRow) => (r.size ? `${r.size[0]!.toUpperCase()}${r.size.slice(1)} cap` : "Size unknown") },
  quadrant: { label: "Rotation vs ACWI", get: (r: DiscoveryRow) => r.quadrant ?? "n/a" },
} as const;
type GroupKey = keyof typeof GROUP;

const SIZE_ORDER = { large: 3, mid: 2, small: 1 } as const;

function flags(r: DiscoveryRow) {
  return (
    <span className="flags-inline">
      {r.off_radar && <Badge kind="accent">new to radar</Badge>}
      {r.new_high && <Badge kind="pos">52w high</Badge>}
      {r.trend_turn && <Badge kind="pos">trend turn</Badge>}
      {r.thin && <Badge kind="warn">thin</Badge>}
      {r.check_data && <Badge kind="neg">check data</Badge>}
      {r.stale && <Badge kind="neg">stale</Badge>}
    </span>
  );
}

function columns(kind: DiscoveryMarket["kind"]): Col<DiscoveryRow>[] {
  const stock = kind === "stock";
  return [
    { key: "name", label: "Name", align: "l", sort: (r) => r.name ?? r.ticker, search: (r) => `${r.name ?? ""} ${r.ticker} ${r.isin ?? ""}`,
      csv: (r) => r.ticker, csvHeader: "Ticker", render: (r) => <TickerLink symbol={r.ticker} name={r.name} nameFirst /> },
    ...(stock ? [
      { key: "country", label: "Country", align: "l", sort: (r) => r.country, filter: { kind: "enum" },
        render: (r) => <span className="muted">{r.country ?? "–"}</span> },
      { key: "sector", label: "Sector", align: "l", sort: (r) => r.sector, search: (r) => `${r.sector ?? ""} ${r.industry ?? ""}`,
        filter: { kind: "enum" }, render: (r) => <span className="muted">{r.sector ?? "–"}</span> },
      { key: "industry", label: "Industry", align: "l", sort: (r) => r.industry, filter: { kind: "enum" }, hidden: true,
        render: (r) => <span className="muted">{r.industry ?? "–"}</span> },
      { key: "size", label: "Size", align: "l", sort: (r) => (r.size ? SIZE_ORDER[r.size] : null), filter: { kind: "enum", value: (r) => r.size },
        help: "disc_size", render: (r) => <span className="muted">{r.size ?? "–"}</span> },
      { key: "cap", label: "Mkt cap", name: "Market cap (DKK)", sort: (r) => r.market_cap_dkk, help: "disc_cap",
        render: (r) => <span className="num">{compact(r.market_cap_dkk)}</span> },
    ] as Col<DiscoveryRow>[] : [
      { key: "category", label: "Category", align: "l", sort: (r) => r.category, filter: { kind: "enum" },
        render: (r) => <span className="muted">{r.category ?? "–"}</span> },
      { key: "pl", label: "Positive list", align: "l", sort: (r) => r.positive_list, help: "positive_list", filter: { kind: "enum" },
        render: (r) => r.positive_list === "yes" ? <Badge kind="pos">yes</Badge> : r.positive_list === "no" ? <Badge kind="neg">no</Badge>
          : <span className="muted">?</span> },
      { key: "isin", label: "ISIN", align: "l", sort: (r) => r.isin, help: "isin", hidden: true,
        render: (r) => r.isin ?? <span className="muted">–</span> },
    ] as Col<DiscoveryRow>[]),
    { key: "score", label: "Score", sort: (r) => r.score, help: "disc_score", filter: { kind: "range", unit: "num" },
      render: (r) => <b className="num">{num(r.score, 0)}</b> },
    { key: "dscore", label: "Δ score", name: "Score change (1m)", sort: (r) => r.d_score, help: "d_score", filter: { kind: "range", unit: "num" },
      render: (r) => <span className={`num ${fmt.tone(r.d_score)}`}>{fmt.signed(r.d_score)}</span> },
    ...(stock ? stockValCols<DiscoveryRow>() : fundValCols<DiscoveryRow>()),
    { key: "r1w", label: "1w", sort: (r) => r.r1w, render: (r) => <Pct v={r.r1w} />, help: "r1w", heat: true },
    { key: "r1m", label: "1m", sort: (r) => r.r1m, render: (r) => <Pct v={r.r1m} />, help: "r1m", heat: true },
    { key: "r3m", label: "3m", sort: (r) => r.r3m, render: (r) => <Pct v={r.r3m} />, help: "r3m", heat: true, filter: { kind: "range", unit: "pct" } },
    { key: "r6m", label: "6m", sort: (r) => r.r6m, render: (r) => <Pct v={r.r6m} />, help: "r6m", heat: true },
    { key: "r12_1", label: "12-1m", sort: (r) => r.r12_1, render: (r) => <Pct v={r.r12_1} />, help: "r12_1", hidden: true },
    { key: "from_high", label: "From high", name: "From 52w high", sort: (r) => r.from_high, help: "from_high", filter: { kind: "range", unit: "pct" },
      render: (r) => <span className="num">{pct(r.from_high)}</span> },
    { key: "liq", label: "Traded/day", name: "Traded value per day (DKK)", sort: (r) => r.liquidity_dkk, help: "liquidity",
      render: (r) => <span className={`num ${r.thin ? "warn" : ""}`}>{compact(r.liquidity_dkk)}</span> },
    { key: "quadrant", label: "vs ACWI", name: "Rotation vs ACWI", align: "l", sort: (r) => r.quadrant, help: "quadrant", filter: { kind: "enum" },
      render: (r) => <Quadrant q={r.quadrant} /> },
    { key: "trend", label: "Trend", sort: (r) => r.trend_ok, help: "trend_ok", filter: { kind: "bool" }, render: (r) => <Check v={r.trend_ok} /> },
    { key: "flags", label: "Flags", align: "l", help: "disc_flags", csv: false, render: flags },
    { key: "off", label: "New to radar", sort: (r) => r.off_radar, help: "off_radar", filter: { kind: "bool" }, hidden: true,
      render: (r) => <Check v={r.off_radar} /> },
    { key: "newhigh", label: "52w high", name: "New 52w high on volume", sort: (r) => r.new_high, help: "new_high", filter: { kind: "bool" },
      hidden: true, render: (r) => <Check v={r.new_high} /> },
    { key: "turn", label: "Trend turn", sort: (r) => r.trend_turn, help: "trend_turn", filter: { kind: "bool" }, hidden: true,
      render: (r) => <Check v={r.trend_turn} /> },
    { key: "thin", label: "Thin", name: "Thinly traded", sort: (r) => r.thin, help: "liquidity", filter: { kind: "bool" }, hidden: true,
      render: (r) => <Check v={r.thin} /> },
    { key: "star", label: "", name: "Watch", render: (r) => <WatchStar symbol={r.ticker} />, csv: false },
  ];
}

type Preset = { key: string; label: string; help: string; stockOnly?: boolean; state: TableState };
const PRESETS: Preset[] = [
  { key: "radar", label: "Under the radar", stockOnly: true,
    help: "Not tracked by the radar yet, small or mid cap, score 80+ and traded enough to buy and sell.",
    state: { q: "", sort: { key: "score", asc: false }, filters: {
      off: { kind: "bool", value: true }, size: { kind: "enum", values: ["small", "mid"] },
      score: { kind: "range", min: 80 }, thin: { kind: "bool", value: false } } } },
  { key: "emerging", label: "Emerging", help: "Score up 20 points or more in a month, with an intact uptrend.",
    state: { q: "", sort: { key: "dscore", asc: false }, filters: {
      dscore: { kind: "range", min: 20 }, trend: { kind: "bool", value: true } } } },
  { key: "breakouts", label: "Breakouts", help: "At a new 52-week high on at least 1.5× normal volume.",
    state: { q: "", sort: { key: "r1m", asc: false }, filters: { newhigh: { kind: "bool", value: true } } } },
  { key: "turnarounds", label: "Turnarounds", help: "Crossed above the 200-day average in the last 20 sessions with the 50-day rising.",
    state: { q: "", sort: { key: "dscore", asc: false }, filters: { turn: { kind: "bool", value: true } } } },
  { key: "leaders", label: "Leaders", help: "Score 80 or more within its market.",
    state: { q: "", sort: { key: "score", asc: false }, filters: { score: { kind: "range", min: 80 } } } },
];

function NoScan() {
  return (
    <>
      <PageHead title="Discover">
        Discover looks beyond the radar&apos;s own lists: Nordic and European stocks from Yahoo&apos;s screener, every STOXX
        Europe 600 and S&amp;P 500 member and the ETFs on SKAT&apos;s positive list. It runs as a separate scan so the daily
        update stays fast. The first scan takes a while (it looks up about 3,500 names once); later scans take a few
        minutes.
      </PageHead>
      <UpdatePanel job="discover" label="Run the first discovery scan" />
    </>
  );
}

function Legend({ color }: { color: ColorKey }) {
  const c = COLOR[color];
  const steps = c.steps;
  const cells = [-4, -3, -2, -1, 0, 1, 2, 3, 4];
  const bound = (lv: number) => {
    const s = steps[Math.abs(lv) - 1];
    if (lv === 0 || s === undefined) return "";
    return c.f(lv < 0 ? -s : s);
  };
  return (
    <div className="tm-legend" aria-label={`Colour scale: ${c.label}`}>
      {cells.map((lv) => (
        <span key={lv} className={`tm-sw ${lv === 0 ? "z" : lv > 0 ? `lv+${lv}` : `lv${lv}`}`} title={bound(lv)}>{lv === -4 || lv === 4 ? bound(lv) : ""}</span>
      ))}
      <span className="tm-sw na">no data</span>
    </div>
  );
}

function MarketView({ d, m }: { d: DiscoveryView; m: DiscoveryMarket }) {
  const [params, setParams] = useSearchParams();
  const [state, setState] = useTableState(ID);
  const [hovered, setHovered] = useState<string | null>(null);
  const stock = m.kind === "stock";
  const colorKey = (params.get("color") as ColorKey) in COLOR ? (params.get("color") as ColorKey) : "r1m";
  const sizeDefault: SizeKey = stock ? "sqrtcap" : "sqrtliq";
  const sizeKey = (params.get("size") as SizeKey) in SIZE ? (params.get("size") as SizeKey) : sizeDefault;
  const groupDefault: GroupKey = stock ? "sector" : "category";
  const groupKey = (params.get("by") as GroupKey) in GROUP ? (params.get("by") as GroupKey) : groupDefault;
  const set = (k: string, v: string) => setParams((p) => { const n = new URLSearchParams(p); n.set(k, v); return n; },
    { replace: true, preventScrollReset: true });

  const align = useAlignment(useMemo(() => m.rows.map((r) => r.ticker), [m.rows]), "discovery");
  const cols = useMemo(() => withViews(columns(m.kind), align), [m.kind, align]);
  const kept = useMemo(() => filterRows(m.rows, cols, state).rows, [m.rows, cols, state]);
  const c = COLOR[colorKey];
  const items: TreemapItem[] = useMemo(() => kept.map((r) => ({
    ticker: r.ticker, name: r.name, group: GROUP[groupKey].get(r), size: SIZE[sizeKey].get(r), color: c.get(r) ?? null,
    spark: r.spark,
    lines: [
      ["Score", `${fmt.score(r.score)} (${fmt.signed(r.d_score)} in 1m)`], ["1w", pct(r.r1w)], ["1m", pct(r.r1m)], ["3m", pct(r.r3m)],
      ["6m", pct(r.r6m)], ...(stock ? [["Mkt cap", fmt.dkk(r.market_cap_dkk)] as [string, string]] : []),
      ["Traded/day", fmt.dkk(r.liquidity_dkk)],
      ...(r.off_radar ? [["", "not tracked by the radar yet"] as [string, string]] : []),
    ],
  })), [kept, groupKey, sizeKey, c, stock]);
  const unknownSize = sizeKey !== "equal" ? items.filter((i) => i.size === null).length : 0;
  const presets = PRESETS.filter((p) => stock || !p.stockOnly);
  const activePreset = presets.find((p) => JSON.stringify(p.state.filters) === JSON.stringify(state.filters))?.key;

  return (
    <>
      <div className="presets" role="group" aria-label="Ready-made screens">
        {presets.map((p) => (
          <button key={p.key} type="button" className={`btn small ${activePreset === p.key ? "primary" : ""}`} title={p.help}
            aria-pressed={activePreset === p.key} onClick={() => setState(p.state, { push: true })}>{p.label}</button>
        ))}
        <button type="button" className="btn small" onClick={() => setState(EMPTY, { push: true })}
          disabled={!Object.keys(state.filters).length && !state.q}>All names</button>
        {activePreset && <span className="small muted">{presets.find((p) => p.key === activePreset)!.help}</span>}
      </div>
      <div className="card tm-card">
        <div className="lc-head tm-head">
          <span className="small muted">{kept.length} of {m.rows.length} names{unknownSize > 0 && ` · ${unknownSize} with unknown size drawn smallest`}</span>
          <label className="small">Colour <select value={colorKey} onChange={(e) => set("color", e.target.value)}>
            {Object.entries(COLOR).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>
          <label className="small">Size <select value={sizeKey} onChange={(e) => set("size", e.target.value)}>
            {Object.entries(SIZE).filter(([k]) => stock || !k.includes("cap")).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>
          <label className="small">Group <select value={groupKey} onChange={(e) => set("by", e.target.value)}>
            {Object.entries(GROUP).filter(([k]) => (stock ? k !== "category" : !["sector", "country", "size"].includes(k)))
              .map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>
          <Legend color={colorKey} />
        </div>
        <Treemap items={items} steps={c.steps} format={c.f} title={`${m.label}: ${c.label}`} highlight={hovered} onHover={setHovered} />
        <p className="small muted tm-narrow">The heat map needs a wider screen; the table below has the same names.</p>
      </div>
      <div className="sticky-tools"><TableToolbar id={ID} csvName={`discover-${m.key}`} rows={m.rows} cols={cols} /></div>
      <div className="card">
        <DataTable id={ID} toolbar={false} rows={m.rows} cols={cols} rowKey={(r) => r.ticker} highlight={hovered} onHover={setHovered} />
      </div>
      <p className="small muted">
        Prices as of {date(d.asof)}; list of names from {date(d.universe_asof)}. Small means under {compact(d.thresholds.size_mid_dkk)} DKK,
        large from {compact(d.thresholds.size_large_dkk)} DKK; &ldquo;thin&rdquo; trades under {compact(d.thresholds.liquidity_floor_dkk)} DKK a day.
      </p>
    </>
  );
}

export function Discover() {
  const q = useQuery({ queryKey: ["discover"], queryFn: api.discover, retry: false, staleTime: 5 * 60_000 });
  const [params, setParams] = useSearchParams();
  if (q.isPending) return <><PageHead title="Discover" /><div className="skeleton" style={{ height: 500 }} aria-busy="true" /></>;
  if (q.isError) {
    if (q.error instanceof ApiError && q.error.status === 503) return <NoScan />;
    return <><PageHead title="Discover" /><div className="error">Couldn&apos;t load: {q.error.message}</div></>;
  }
  const d = q.data;
  const m = d.markets.find((x) => x.key === params.get("mkt")) ?? d.markets[0]!;
  const pick = (key: string) => setParams((p) => {
    const n = new URLSearchParams();
    n.set("mkt", key);
    for (const [k, v] of p) if (k === "color") n.set(k, v);   // filters and grouping belong to the market just left
    return n;
  }, { preventScrollReset: true });
  return (
    <>
      <PageHead title="Discover" asof={d.asof} generated={d.generated} ageDays={d.age_days} stale={false}>
        A wider net than the radar&apos;s own lists, to find names before they reach the momentum leaders. Scores are the same
        formula as the Momentum page (12-1, 6 and 3-month returns), ranked within each market, so a Nordic small cap
        competes with Nordic names. Tiles default to √ market cap so small companies stay visible. Small caps are noisier
        and thinly traded names can jump: treat every hit as a reason to research, not a buy signal.
      </PageHead>
      {d.stale && (
        <div className="notes" role="alert">This scan is {d.age_days} days old. <UpdatePanel job="discover" compact label="Scan again" /></div>
      )}
      <div className="disc-markets">
        <div className="seg" role="tablist" aria-label="Market">
          {d.markets.map((x) => (
            <button key={x.key} type="button" role="tab" aria-selected={x.key === m.key} aria-pressed={x.key === m.key} onClick={() => pick(x.key)}>
              {x.label} <span className="muted">{x.scored}</span>
            </button>
          ))}
        </div>
        {!d.stale && <UpdatePanel job="discover" compact label="Scan again" />}
      </div>
      {m.rows.length === 0
        ? <p className="empty">No names in this market yet: the last scan couldn&apos;t build it (see Data &amp; coverage).</p>
        : <MarketView key={m.key} d={d} m={m} />}
    </>
  );
}

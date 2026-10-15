import {
  ColorType,
  createChart,
  HistogramSeries,
  LineSeries,
  LineStyle,
  PriceScaleMode,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type LineData,
  type Time,
  type WhitespaceData,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { Series } from "../api/client";
import { indexAt, RANGES, rebase, type RangeKey } from "../lib/chartRange";
import { compact, date, num, pct, price, tone, type Maybe } from "../lib/format";
import { browserStore } from "../lib/nav";

export type Level = { price: Maybe; label: string; kind: "stop" | "target" | "analyst" };

/** What the viewer has switched on; remembered in this browser. */
type Show = { sma50: boolean; sma200: boolean; bb: boolean; volume: boolean; levels: boolean; rsi: boolean; rel: boolean; log: boolean };
const SHOW_DEFAULT: Show = { sma50: true, sma200: true, bb: false, volume: true, levels: true, rsi: true, rel: true, log: false };
const SHOW_KEY = "chart.show";
const RANGE_KEY = "chart.range";

function loadShow(): Show {
  try {
    const v: unknown = JSON.parse(browserStore.get(SHOW_KEY) ?? "{}");
    return { ...SHOW_DEFAULT, ...(v && typeof v === "object" ? v : {}) };
  } catch {
    return SHOW_DEFAULT;
  }
}

function loadRange(): RangeKey {
  const v = browserStore.get(RANGE_KEY);
  return RANGES.includes(v as RangeKey) ? (v as RangeKey) : "1Y";
}

function css(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function line(s: Series, values: (number | null)[]): (LineData<Time> | WhitespaceData<Time>)[] {
  return s.dates.map((d, i) => {
    const v = values[i];
    return v === null || v === undefined ? { time: d as Time } : { time: d as Time, value: v };
  });
}

const pp = (v: Maybe) => pct(v).replace("%", " pp");

type Handles = {
  chart: IChartApi;
  sma50: ISeriesApi<"Line">; sma200: ISeriesApi<"Line">; bb: ISeriesApi<"Line">[];
  vol: ISeriesApi<"Histogram">; rel: ISeriesApi<"Line"> | null; levels: { line: IPriceLine; label: string }[];
};

/** Price (with 50/200-day averages, Bollinger bands, stop/target lines and volume), RSI and relative strength
 *  vs ACWI in linked panes. Values are drawn as the API sends them; relative strength is rebased to 100 at the
 *  start of the chosen range. */
export function PriceChart({ series, levels, currency }: { series: Series; levels: Level[]; currency?: string | null }) {
  const host = useRef<HTMLDivElement>(null);
  const h = useRef<Handles | null>(null);
  const [range, setRange] = useState<RangeKey>(loadRange);
  const [show, setShow] = useState<Show>(loadShow);
  const [hi, setHi] = useState<number | null>(null);      // index of the hovered session

  const stats = series.ranges[range];
  const from = useMemo(() => indexAt(series.dates, stats?.start), [series, stats]);
  const rel = useMemo(() => rebase(series.rel_acwi, from), [series, from]);

  // the latest view settings, for re-applying them when the chart is rebuilt
  const view = useRef({ from, rel, show });
  view.current = { from, rel, show };

  const sync = () => {
    const x = h.current;
    if (!x) return;
    const { from: f, rel: r, show: s } = view.current;
    x.sma50.applyOptions({ visible: s.sma50 });
    x.sma200.applyOptions({ visible: s.sma200 });
    for (const b of x.bb) b.applyOptions({ visible: s.bb });
    x.vol.applyOptions({ visible: s.volume });
    for (const l of x.levels) l.line.applyOptions({ lineVisible: s.levels, axisLabelVisible: s.levels, title: s.levels ? l.label : "" });
    x.chart.priceScale("right", 0).applyOptions({ mode: s.log ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal });
    x.rel?.setData(line(series, r));
    x.chart.timeScale().setVisibleLogicalRange({ from: f, to: series.dates.length - 1 });
  };

  useEffect(() => {
    if (!host.current) return;
    const colors = () => ({ ink2: css("--ink-2"), line: css("--line"), muted: css("--muted"), s1: css("--s1"),
      s2: css("--s2"), s3: css("--s3"), s4: css("--s4"), pos: css("--pos"), neg: css("--neg"), accent: css("--accent") });
    let c = colors();
    const chart = createChart(host.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: c.ink2, fontSize: 11,
        panes: { separatorColor: c.line, separatorHoverColor: c.line } },
      grid: { vertLines: { visible: false }, horzLines: { color: c.line } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      crosshair: { mode: 0 },
      // the wheel scrolls the page; zoom with the range buttons, drag or pinch
      handleScroll: { mouseWheel: false, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { mouseWheel: false, pinch: true, axisPressedMouseMove: true },
    });

    const close = chart.addSeries(LineSeries, { color: c.s1, lineWidth: 2, title: "", priceLineVisible: false,
      priceFormat: { type: "price", precision: 2, minMove: 0.01 } });
    close.setData(line(series, series.close));
    const sma50 = chart.addSeries(LineSeries, { color: c.s2, lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
      crosshairMarkerVisible: false });
    sma50.setData(line(series, series.sma50));
    const sma200 = chart.addSeries(LineSeries, { color: c.s3, lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
      crosshairMarkerVisible: false });
    sma200.setData(line(series, series.sma200));
    const bb = [series.bb_upper, series.bb_lower].map((band) => {
      const s = chart.addSeries(LineSeries, { color: c.muted, lineWidth: 1, lineStyle: LineStyle.Dotted, priceLineVisible: false,
        lastValueVisible: false, crosshairMarkerVisible: false });
      s.setData(line(series, band));
      return s;
    });
    const lines: Handles["levels"] = [];
    for (const lv of levels) {
      if (lv.price === null || lv.price === undefined || !Number.isFinite(lv.price)) continue;
      lines.push({ label: lv.label, line: close.createPriceLine({
        price: lv.price, title: lv.label, lineWidth: 1, axisLabelVisible: true,
        color: lv.kind === "stop" ? c.neg : lv.kind === "target" ? c.pos : c.accent,
        lineStyle: lv.kind === "analyst" ? LineStyle.Dotted : LineStyle.Dashed,
      }) });
    }

    const vol = chart.addSeries(HistogramSeries, { priceScaleId: "vol", priceFormat: { type: "volume" },
      lastValueVisible: false, priceLineVisible: false });
    vol.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    vol.setData(series.dates.map((d, i) => {
      const v = series.volume[i];
      const up = i > 0 && (series.close[i] ?? 0) >= (series.close[i - 1] ?? 0);
      return v === null || v === undefined ? { time: d as Time }
        : { time: d as Time, value: v, color: `${up ? c.pos : c.neg}55` };
    }));

    // the lower panes exist only when switched on (a pane without series takes no room)
    const { show: s } = view.current;
    let pane = 0;
    if (s.rsi) {
      pane += 1;
      const rsi = chart.addSeries(LineSeries, { color: c.s4, lineWidth: 1, priceLineVisible: false, title: "RSI 14",
        autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }) }, pane);
      rsi.setData(line(series, series.rsi));
      for (const lvl of [30, 70]) rsi.createPriceLine({ price: lvl, color: c.muted, lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: false, title: "" });
    }
    let rel: ISeriesApi<"Line"> | null = null;
    if (s.rel) {
      pane += 1;
      rel = chart.addSeries(LineSeries, { color: c.accent, lineWidth: 1, priceLineVisible: false, title: "vs ACWI" }, pane);
      rel.createPriceLine({ price: 100, color: c.muted, lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: false, title: "" });
    }

    const index = new Map(series.dates.map((d, i) => [d, i]));
    chart.subscribeCrosshairMove((p) => setHi(p.time && p.point ? (index.get(String(p.time)) ?? null) : null));

    const panes = chart.panes();
    const sub = panes.length - 1;
    panes[0]?.setStretchFactor(sub === 0 ? 1 : sub === 1 ? 0.75 : 0.62);
    for (const p of panes.slice(1)) p.setStretchFactor(sub === 1 ? 0.25 : 0.19);

    h.current = { chart, sma50, sma200, bb, vol, rel, levels: lines };
    sync();

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const retheme = () => {
      c = colors();
      chart.applyOptions({ layout: { textColor: c.ink2, panes: { separatorColor: c.line } }, grid: { horzLines: { color: c.line } } });
    };
    media.addEventListener("change", retheme);
    return () => {
      media.removeEventListener("change", retheme);
      chart.remove();
      h.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series, levels, show.rsi, show.rel]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(sync, [from, rel, show]);

  const toggle = (k: keyof Show) => setShow((s) => {
    const next = { ...s, [k]: !s[k] };
    browserStore.set(SHOW_KEY, JSON.stringify(next));
    return next;
  });
  const pick = (k: RangeKey) => {
    setRange(k);
    browserStore.set(RANGE_KEY, k);
  };
  const shown = levels.filter((l) => l.price !== null && l.price !== undefined);
  const years = (series.dates.length - 1) / 252;
  const Item = ({ k, color, children, dotted }: { k: keyof Show; color: string; children: ReactNode; dotted?: boolean }) => (
    <button type="button" className="lg-item" aria-pressed={show[k]} onClick={() => toggle(k)} title={show[k] ? "Click to hide" : "Click to show"}>
      <i style={dotted ? { borderTop: `2px dotted ${color}`, background: "none" } : { background: color }} />{children}
    </button>
  );

  return (
    <div>
      <div className="chart-tools">
        <div className="seg" role="group" aria-label="Range">
          {RANGES.map((k) => (
            <button key={k} aria-pressed={range === k} onClick={() => pick(k)}>{k}</button>
          ))}
        </div>
        <button type="button" className="lg-item" aria-pressed={show.log} onClick={() => toggle("log")}
          title="Logarithmic price scale: equal percentage moves take equal room">log</button>
      </div>
      <div className="range-sum" aria-live="polite">
        <span><b>{range}</b> <b className={`num ${tone(stats?.ret)}`}>{pct(stats?.ret)}</b></span>
        <span>ACWI <span className={`num ${tone(stats?.acwi)}`}>{pct(stats?.acwi)}</span></span>
        <span><b className={`num ${tone(stats?.vs_acwi)}`}>{pp(stats?.vs_acwi)}</b> vs ACWI</span>
        <span className="muted">low–high <span className="num">{price(stats?.low)}–{price(stats?.high, currency)}</span></span>
        <span className="muted">from the close on {date(stats?.start)}</span>
        {stats?.short && <span className="muted">· only {num(years, 1)} years stored</span>}
      </div>
      <div className="legend chart-legend">
        <span className="lg-fixed"><i style={{ background: "var(--s1)" }} />Price (adj.)</span>
        <Item k="sma50" color="var(--s2)">50d</Item>
        <Item k="sma200" color="var(--s3)">200d</Item>
        <Item k="bb" color="var(--muted)" dotted>Bollinger 20/2</Item>
        <Item k="volume" color="var(--ink-2)">Volume</Item>
        {shown.length > 0 && (
          <button type="button" className="lg-item" aria-pressed={show.levels} onClick={() => toggle("levels")} title={show.levels ? "Click to hide" : "Click to show"}>
            {shown.map((l) => (
              <span key={l.label} className="lg-sub">
                <i style={{ background: l.kind === "stop" ? "var(--neg)" : l.kind === "target" ? "var(--pos)" : "var(--accent)" }} />
                {l.label} {price(l.price, currency)}
              </span>
            ))}
          </button>
        )}
        <Item k="rsi" color="var(--s4)">RSI pane</Item>
        <Item k="rel" color="var(--accent)">vs ACWI pane</Item>
      </div>
      <div className="readout small" aria-live="polite">
        {hi !== null ? (
          <>
            <b>{date(series.dates[hi])}</b>
            <span>close <b className="num">{price(series.close[hi], currency)}</b></span>
            <span>50d <b className="num">{price(series.sma50[hi])}</b></span>
            <span>200d <b className="num">{price(series.sma200[hi])}</b></span>
            <span>RSI <b className="num">{num(series.rsi[hi], 1)}</b></span>
            <span>vs ACWI <b className="num">{num(rel[hi], 1)}</b></span>
            <span>volume <b className="num">{compact(series.volume[hi])}</b></span>
          </>
        ) : <span className="muted">Hover the chart to read the values of any session. Click a legend item to hide or show it.</span>}
      </div>
      <div ref={host} className="chart" />
      <div className="small muted">
        Panes: price with volume{show.rsi && " · RSI 14 (30/70)"}{show.rel && " · relative strength vs ACWI (100 = start of the chosen range)"}
      </div>
    </div>
  );
}

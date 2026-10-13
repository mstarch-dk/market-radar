import {
  ColorType,
  createChart,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type LineData,
  type Time,
  type WhitespaceData,
} from "lightweight-charts";
import { useEffect, useRef, useState } from "react";
import type { Series } from "../api/client";
import { price, type Maybe } from "../lib/format";

const RANGES = [["3M", 63], ["6M", 126], ["1Y", 252], ["3Y", 756]] as const;

export type Level = { price: Maybe; label: string; kind: "stop" | "target" | "analyst" };

function css(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function line(s: Series, values: (number | null)[]): (LineData<Time> | WhitespaceData<Time>)[] {
  return s.dates.map((d, i) => {
    const v = values[i];
    return v === null || v === undefined ? { time: d as Time } : { time: d as Time, value: v };
  });
}

/** Price (with 50/200-day averages, Bollinger bands, stop/target lines and volume), RSI and relative strength
 *  vs ACWI in linked panes. Values are drawn as the API sends them. */
export function PriceChart({ series, levels, currency }: { series: Series; levels: Level[]; currency?: string | null }) {
  const host = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [range, setRange] = useState<number>(252);

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
    chartRef.current = chart;

    const close = chart.addSeries(LineSeries, { color: c.s1, lineWidth: 2, title: "", priceLineVisible: false,
      priceFormat: { type: "price", precision: 2, minMove: 0.01 } });
    close.setData(line(series, series.close));
    const sma50 = chart.addSeries(LineSeries, { color: c.s2, lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
      crosshairMarkerVisible: false });
    sma50.setData(line(series, series.sma50));
    const sma200 = chart.addSeries(LineSeries, { color: c.s3, lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
      crosshairMarkerVisible: false });
    sma200.setData(line(series, series.sma200));
    for (const band of [series.bb_upper, series.bb_lower]) {
      chart.addSeries(LineSeries, { color: c.muted, lineWidth: 1, lineStyle: LineStyle.Dotted, priceLineVisible: false,
        lastValueVisible: false, crosshairMarkerVisible: false }).setData(line(series, band));
    }
    for (const lv of levels) {
      if (lv.price === null || lv.price === undefined || !Number.isFinite(lv.price)) continue;
      close.createPriceLine({
        price: lv.price, title: lv.label, lineWidth: 1, axisLabelVisible: true,
        color: lv.kind === "stop" ? c.neg : lv.kind === "target" ? c.pos : c.accent,
        lineStyle: lv.kind === "analyst" ? LineStyle.Dotted : LineStyle.Dashed,
      });
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

    const rsi = chart.addSeries(LineSeries, { color: c.s4, lineWidth: 1, priceLineVisible: false, title: "RSI 14",
      autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }) }, 1);
    rsi.setData(line(series, series.rsi));
    for (const lvl of [30, 70]) rsi.createPriceLine({ price: lvl, color: c.muted, lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: false, title: "" });

    const rel = chart.addSeries(LineSeries, { color: c.accent, lineWidth: 1, priceLineVisible: false, title: "vs ACWI" }, 2);
    rel.setData(line(series, series.rel_acwi));
    rel.createPriceLine({ price: 100, color: c.muted, lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: false, title: "" });

    const panes = chart.panes();
    panes[0]?.setStretchFactor(0.62);
    panes[1]?.setStretchFactor(0.19);
    panes[2]?.setStretchFactor(0.19);

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const retheme = () => {
      c = colors();
      chart.applyOptions({ layout: { textColor: c.ink2, panes: { separatorColor: c.line } }, grid: { horzLines: { color: c.line } } });
    };
    media.addEventListener("change", retheme);
    return () => {
      media.removeEventListener("change", retheme);
      chart.remove();
      chartRef.current = null;
    };
  }, [series, levels]);

  useEffect(() => {
    const n = series.dates.length;
    chartRef.current?.timeScale().setVisibleLogicalRange({ from: Math.max(0, n - range), to: n - 1 });
  }, [range, series]);

  const shown = levels.filter((l) => l.price !== null && l.price !== undefined);
  return (
    <div>
      <div className="chart-tools">
        <div className="seg" role="group" aria-label="Range">
          {RANGES.map(([label, days]) => (
            <button key={label} aria-pressed={range === days} onClick={() => setRange(days)}>{label}</button>
          ))}
        </div>
        <div className="legend">
          <span><i style={{ background: "var(--s1)" }} />Price (adj.)</span>
          <span><i style={{ background: "var(--s2)" }} />50d</span>
          <span><i style={{ background: "var(--s3)" }} />200d</span>
          <span><i style={{ background: "var(--muted)" }} />Bollinger 20/2</span>
          {shown.map((l) => (
            <span key={l.label}>
              <i style={{ background: l.kind === "stop" ? "var(--neg)" : l.kind === "target" ? "var(--pos)" : "var(--accent)" }} />
              {l.label} {price(l.price, currency)}
            </span>
          ))}
        </div>
      </div>
      <div ref={host} className="chart" />
      <div className="small muted">Panes: price with volume · RSI 14 (30/70) · relative strength vs ACWI (100 = start of the 3-year window)</div>
    </div>
  );
}

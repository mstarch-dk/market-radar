import { ColorType, createChart, LineSeries, LineStyle, type IChartApi, type MouseEventParams, type Time } from "lightweight-charts";
import { useEffect, useRef, useState } from "react";
import type { LineChartData } from "../api/client";
import { date, num } from "../lib/format";

const COLORS = ["--s1", "--s2", "--s3", "--s4", "--s5", "--s6"];
const color = (i: number) => COLORS[i % COLORS.length] ?? "--s1";
const RANGES = [["6M", 183], ["1Y", 365], ["3Y", 1096], ["All", 0]] as const;

function css(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function shiftDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

/** One dashboard line chart: up to six series on a shared time axis, dotted reference lines, range buttons and
 *  a crosshair readout of every series' value on the hovered date. A missing value (null) is a gap in the line. */
export function LineChart({ chart, height = 260 }: { chart: LineChartData; height?: number }) {
  const host = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const sparse = (chart.series[0]?.dates.length ?? 0) < 120;          // monthly data: show it all by default
  const [range, setRange] = useState<number>(sparse ? 0 : 365);
  const [hover, setHover] = useState<{ time: string; values: (number | undefined)[] } | null>(null);

  useEffect(() => {
    if (!host.current) return;
    const theme = () => ({ ink2: css("--ink-2"), line: css("--line"), muted: css("--muted") });
    let c = theme();
    const ch = createChart(host.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: c.ink2, fontSize: 11 },
      grid: { vertLines: { visible: false }, horzLines: { color: c.line } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      crosshair: { mode: 0 },
      handleScroll: { mouseWheel: false, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { mouseWheel: false, pinch: true, axisPressedMouseMove: true },
    });
    chartRef.current = ch;
    const fmt = { type: "price" as const, precision: chart.decimals, minMove: 10 ** -chart.decimals };
    const lines = chart.series.map((s, i) => {
      const ls = ch.addSeries(LineSeries, { color: css(color(i)), lineWidth: i === 0 ? 2 : 1,
        priceLineVisible: false, lastValueVisible: i === 0, priceFormat: fmt });
      ls.setData(s.dates.map((d, j) => {
        const v = s.values[j];
        return v == null ? { time: d as Time } : { time: d as Time, value: v };   // whitespace: a gap, not 0
      }));
      return ls;
    });
    for (const y of chart.hlines) {
      lines[0]?.createPriceLine({ price: y, color: c.muted, lineWidth: 1, lineStyle: LineStyle.Dotted,
        axisLabelVisible: false, title: "" });
    }
    const onMove = (p: MouseEventParams<Time>) => {
      if (!p.time || !p.point) {
        setHover(null);
        return;
      }
      setHover({ time: String(p.time), values: lines.map((l) => (p.seriesData.get(l) as { value?: number } | undefined)?.value) });
    };
    ch.subscribeCrosshairMove(onMove);

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const retheme = () => {
      c = theme();
      ch.applyOptions({ layout: { textColor: c.ink2 }, grid: { horzLines: { color: c.line } } });
      lines.forEach((l, i) => l.applyOptions({ color: css(color(i)) }));
    };
    media.addEventListener("change", retheme);
    return () => {
      media.removeEventListener("change", retheme);
      ch.unsubscribeCrosshairMove(onMove);
      ch.remove();
      chartRef.current = null;
    };
  }, [chart]);

  useEffect(() => {
    const ch = chartRef.current;
    const dates = chart.series.flatMap((s) => [s.dates[0], s.dates[s.dates.length - 1]]).filter((d): d is string => !!d).sort();
    const last = dates[dates.length - 1];
    if (!ch || !last) return;
    if (range === 0) ch.timeScale().fitContent();
    else ch.timeScale().setVisibleRange({ from: shiftDays(last, range) as Time, to: last as Time });
  }, [range, chart]);

  return (
    <figure className="card line-chart">
      <div className="lc-head">
        <figcaption>{chart.title}</figcaption>
        <div className="seg" role="group" aria-label="Range">
          {RANGES.map(([label, days]) => (
            <button key={label} type="button" aria-pressed={range === days} onClick={() => setRange(days)}>{label}</button>
          ))}
        </div>
      </div>
      <div className="legend" aria-live="polite">
        {hover && <span className="muted">{date(hover.time)}</span>}
        {chart.series.map((s, i) => (chart.series.length > 1 || hover) && (
          <span key={s.name}>
            <i style={{ background: `var(${color(i)})` }} />{s.name}
            {hover && <b className="num"> {num(hover.values[i], chart.decimals)}</b>}
          </span>
        ))}
      </div>
      <div ref={host} style={{ height }} />
    </figure>
  );
}

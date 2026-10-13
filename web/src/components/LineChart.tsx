import { ColorType, createChart, LineSeries, LineStyle, type Time } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { LineChartData } from "../api/client";

const COLORS = ["--s1", "--s2", "--s3", "--s4"];
const color = (i: number) => COLORS[i % COLORS.length] ?? "--s1";

function css(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** One dashboard line chart: up to four series on a shared time axis, with dotted reference lines. */
export function LineChart({ chart, height = 260 }: { chart: LineChartData; height?: number }) {
  const host = useRef<HTMLDivElement>(null);

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
    const step = 10 ** -chart.decimals;
    const fmt = { type: "price" as const, precision: chart.decimals, minMove: step };
    const lines = chart.series.map((s, i) => {
      const ls = ch.addSeries(LineSeries, { color: css(color(i)), lineWidth: i === 0 ? 2 : 1,
        priceLineVisible: false, lastValueVisible: i === 0, priceFormat: fmt });
      ls.setData(s.dates.map((d, j) => ({ time: d as Time, value: s.values[j] })));
      return ls;
    });
    for (const y of chart.hlines) {
      lines[0]?.createPriceLine({ price: y, color: c.muted, lineWidth: 1, lineStyle: LineStyle.Dotted,
        axisLabelVisible: false, title: "" });
    }
    ch.timeScale().fitContent();

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const retheme = () => {
      c = theme();
      ch.applyOptions({ layout: { textColor: c.ink2 }, grid: { horzLines: { color: c.line } } });
      lines.forEach((l, i) => l.applyOptions({ color: css(color(i)) }));
    };
    media.addEventListener("change", retheme);
    return () => {
      media.removeEventListener("change", retheme);
      ch.remove();
    };
  }, [chart]);

  return (
    <figure className="card line-chart">
      <figcaption>{chart.title}</figcaption>
      {chart.series.length > 1 && (
        <div className="legend">
          {chart.series.map((s, i) => (
            <span key={s.name}><i style={{ background: `var(${color(i)})` }} />{s.name}</span>
          ))}
        </div>
      )}
      <div ref={host} style={{ height }} />
    </figure>
  );
}

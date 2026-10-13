import type { ReactNode } from "react";
import type { components } from "../api/schema";
import { Tip } from "./Tip";

export type GaugeData = components["schemas"]["Gauge"];

/** CSS class for a gauge level: lv-4..lv-1 warm (warning), lv0 grey, lv+1..lv+4 green (good). */
export const lvClass = (g?: GaugeData | null) => (!g || g.level === 0 ? "lv0" : g.level > 0 ? `lv+${g.level}` : `lv${g.level}`);

export function fmtGauge(v: number, ref: Pick<GaugeData, "unit">): string {
  return ref.unit === "pct" ? `${+(v * 100).toFixed(1)}%` : `${+v.toFixed(2)}`;
}
const fmt = fmtGauge;

/** "0.5 below 70" — the nearest threshold and how far the reading is from it. */
export function nearest(g: GaugeData): string | null {
  if (!g.ticks.length) return null;
  const t = g.ticks.reduce((a, b) => (Math.abs(b - g.value) < Math.abs(a - g.value) ? b : a));
  const d = g.value - t;
  if (Math.abs(d) < 1e-9) return `at the ${fmt(t, g)} threshold`;
  return `${fmt(Math.abs(d), g).replace(/^-/, "")} ${d < 0 ? "below" : "above"} the ${fmt(t, g)} threshold`;
}

export function gaugeTip(g: GaugeData, name?: string): ReactNode {
  const near = nearest(g);
  return (
    <>
      <b>{name ? `${name}: ` : ""}{g.label}</b> ({fmt(g.value, g)}){near && <>, {near}</>}.
      <br />{g.scale === "sequential" ? "One-way risk scale: grey is calm, deeper orange/red is more risk." :
        "Green leans favourable, orange/red is a warning; grey is neutral."}
    </>
  );
}

/** The gauge's word on a chip tinted by its level. */
export function GaugeBadge({ g, name }: { g?: GaugeData | null; name?: string }) {
  if (!g) return null;
  return <Tip content={gaugeTip(g, name)}><span className={`gchip ${lvClass(g)}`}>{g.label}</span></Tip>;
}

/** A small axis with threshold ticks and a marker coloured by the level. */
export function GaugeBar({ g }: { g?: GaugeData | null }) {
  if (!g) return null;
  const x = (v: number) => `${Math.max(0, Math.min(100, ((v - g.lo) / (g.hi - g.lo || 1)) * 100))}%`;
  return (
    <span className="gbar" aria-hidden>
      {g.ticks.map((t) => <span key={t} className="tick" style={{ left: x(t) }} />)}
      <span className={`mark ${lvClass(g)}`} style={{ left: x(g.value) }} />
    </span>
  );
}

/** A number tinted by its gauge level (the number itself stays the content). */
export function Graded({ g, children }: { g?: GaugeData | null; children: ReactNode }) {
  if (!g) return <>{children}</>;
  return <Tip content={gaugeTip(g)}><span className={`gtint gnum ${lvClass(g)}`}>{children}</span></Tip>;
}

/** The lowest level among a row's gauges (sort key for "most worrying first"). */
export const worst = (gs: Record<string, GaugeData> | undefined) =>
  gs && Object.keys(gs).length ? Math.min(...Object.values(gs).map((g) => g.level)) : null;

/** One dot per gauge, for scanning a table row; the tooltip lists them. */
export function GaugeDots({ gauges, names }: { gauges: Record<string, GaugeData>; names: Record<string, string> }) {
  const keys = Object.keys(names).filter((k) => gauges[k]);
  if (!keys.length) return <span className="muted">–</span>;
  return (
    <Tip content={<>{keys.map((k) => <div key={k}>{gaugeTip(gauges[k]!, names[k])}</div>)}</>}>
      <span className="gdots">{keys.map((k) => <span key={k} className={`gdot ${lvClass(gauges[k])}`} />)}</span>
    </Tip>
  );
}

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { RrgTrail } from "../api/client";
import { date, pct, tone } from "../lib/format";
import { tickerPath } from "./TickerLink";

const W = 640, H = 460, M = { l: 44, r: 16, t: 16, b: 40 };
const QUAD_COLOR: Record<string, string> = {
  Leading: "var(--pos)", Weakening: "var(--warn)", Lagging: "var(--neg)", Improving: "var(--accent)", "n/a": "var(--muted)",
};

export type RrgExtra = { rel_r1m?: number | null; rel_r3m?: number | null };

/** Relative rotation graph: x = RS-Ratio (relative trend), y = RS-Momentum (its acceleration), each ETF's weekly
 *  tail ending in a dot. Hovering a dot (or its table row, via `highlight`) brings it forward and dims the rest;
 *  clicking opens the ETF. `extra` adds relative returns to the tooltip. */
export function RrgChart({ trails, title, highlight, onHover, extra }: {
  trails: RrgTrail[];
  title: string;
  highlight?: string | null;
  onHover?: (ticker: string | null) => void;
  extra?: Record<string, RrgExtra>;
}) {
  const nav = useNavigate();
  const [labels, setLabels] = useState(true);
  const [tails, setTails] = useState(true);
  const [own, setOwn] = useState<string | null>(null);
  const active = own ?? highlight ?? null;
  const hover = (t: string | null) => {
    setOwn(t);
    onHover?.(t);
  };

  const xs = trails.flatMap((t) => t.tail.map((p) => p.x));
  const ys = trails.flatMap((t) => t.tail.map((p) => p.y));
  const pad = 0.4;
  const [x0, x1] = xs.length ? [Math.min(...xs, 100) - pad, Math.max(...xs, 100) + pad] : [97, 103];
  const [y0, y1] = ys.length ? [Math.min(...ys, 100) - pad, Math.max(...ys, 100) + pad] : [97, 103];
  const sx = (x: number) => M.l + ((x - x0) / (x1 - x0)) * (W - M.l - M.r);
  const sy = (y: number) => H - M.b - ((y - y0) / (y1 - y0)) * (H - M.t - M.b);
  const cx = sx(100), cy = sy(100);
  const quads = [
    { q: "Leading", x: cx, y: M.t, w: W - M.r - cx, h: cy - M.t, ax: W - M.r - 6, ay: M.t + 14, anchor: "end" },
    { q: "Weakening", x: cx, y: cy, w: W - M.r - cx, h: H - M.b - cy, ax: W - M.r - 6, ay: H - M.b - 6, anchor: "end" },
    { q: "Lagging", x: M.l, y: cy, w: cx - M.l, h: H - M.b - cy, ax: M.l + 6, ay: H - M.b - 6, anchor: "start" },
    { q: "Improving", x: M.l, y: M.t, w: cx - M.l, h: cy - M.t, ax: M.l + 6, ay: M.t + 14, anchor: "start" },
  ] as const;
  const open = (t: string) => nav(tickerPath(t));
  // draw the highlighted trail last so it sits on top
  const ordered = active ? [...trails.filter((t) => t.ticker !== active), ...trails.filter((t) => t.ticker === active)] : trails;
  const tip = active ? trails.find((t) => t.ticker === active) : undefined;
  const tipLast = tip?.tail[tip.tail.length - 1];

  return (
    <figure className="card rrg">
      <div className="lc-head">
        <figcaption>{title}</figcaption>
        <div className="seg" role="group" aria-label="Show">
          <button type="button" aria-pressed={labels} onClick={() => setLabels(!labels)}>Labels</button>
          <button type="button" aria-pressed={tails} onClick={() => setTails(!tails)}>Tails</button>
        </div>
      </div>
      {trails.length === 0 ? <p className="empty">No ETF to show: none has enough history, or the table filters exclude them all.</p> : (
        <div className="rrg-box">
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title}>
            {quads.map((r) => (
              <g key={r.q}>
                <rect x={r.x} y={r.y} width={Math.max(r.w, 0)} height={Math.max(r.h, 0)} fill={QUAD_COLOR[r.q]} opacity={0.07} />
                <text x={r.ax} y={r.ay} textAnchor={r.anchor} className="quad-label" fill={QUAD_COLOR[r.q]}>{r.q.toUpperCase()}</text>
              </g>
            ))}
            <line x1={cx} x2={cx} y1={M.t} y2={H - M.b} className="axis" />
            <line x1={M.l} x2={W - M.r} y1={cy} y2={cy} className="axis" />
            <text x={(W + M.l - M.r) / 2} y={H - 8} textAnchor="middle" className="axis-title">RS-Ratio (relative trend) →</text>
            <text transform={`translate(12 ${(H - M.b + M.t) / 2}) rotate(-90)`} textAnchor="middle" className="axis-title">
              RS-Momentum (acceleration) →
            </text>
            {ordered.map((t) => {
              const color = QUAD_COLOR[t.quadrant] ?? QUAD_COLOR["n/a"];
              const last = t.tail[t.tail.length - 1];
              if (!last) return null;
              const on = active === t.ticker;
              const dim = active !== null && !on;
              return (
                <g key={t.ticker} className={`trail ${dim ? "dim" : ""} ${on ? "on" : ""}`} role="link" tabIndex={0}
                  aria-label={`${t.name} (${t.ticker}): ${t.quadrant}`}
                  onClick={() => open(t.ticker)} onKeyDown={(e) => { if (e.key === "Enter") open(t.ticker); }}
                  onMouseEnter={() => hover(t.ticker)} onMouseLeave={() => hover(null)}
                  onFocus={() => hover(t.ticker)} onBlur={() => hover(null)}>
                  {(tails || on) && (
                    <polyline points={t.tail.map((p) => `${sx(p.x)},${sy(p.y)}`).join(" ")} fill="none" stroke={color}
                      strokeWidth={on ? 2.5 : 1.5} opacity={on ? 0.95 : 0.4} />
                  )}
                  <circle cx={sx(last.x)} cy={sy(last.y)} r={on ? 7 : 5.5} fill={color} stroke="var(--surface)" strokeWidth={2} />
                  {(labels || on) && <text x={sx(last.x)} y={sy(last.y) - 9} textAnchor="middle" className="trail-label">{t.name}</text>}
                </g>
              );
            })}
          </svg>
          {tip && tipLast && (
            <div className="rrg-tip" style={{
              left: `${(sx(tipLast.x) / W) * 100}%`, top: `${(sy(tipLast.y) / H) * 100}%`,
              transform: `translate(${sx(tipLast.x) > W * 0.6 ? "calc(-100% - 12px)" : "12px"}, ${sy(tipLast.y) > H * 0.6 ? "calc(-100% - 8px)" : "8px"})`,
            }}>
              <b>{tip.name}</b> <span className="muted">{tip.ticker}</span>
              <div>{tip.quadrant} · week to {date(tipLast.date)}</div>
              <div className="muted">RS-Ratio {tipLast.x.toFixed(2)} · RS-Momentum {tipLast.y.toFixed(2)}</div>
              {extra?.[tip.ticker] && (
                <div>Rel 1m <b className={tone(extra[tip.ticker]!.rel_r1m)}>{pct(extra[tip.ticker]!.rel_r1m)}</b> · Rel 3m{" "}
                  <b className={tone(extra[tip.ticker]!.rel_r3m)}>{pct(extra[tip.ticker]!.rel_r3m)}</b></div>
              )}
            </div>
          )}
        </div>
      )}
    </figure>
  );
}

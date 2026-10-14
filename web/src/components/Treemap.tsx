import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { compact, pct, tone, num } from "../lib/format";
import { nested, type Group } from "../lib/treemap";
import { Sparkline } from "./Sparkline";
import { tickerPath } from "./TickerLink";

const W = 1200, H = 680;
const MIX = ["0%", "18%", "30%", "44%", "58%"];

export type TreemapItem = {
  ticker: string;
  name?: string | null;
  group: string;
  size: number | null;          // null: unknown, drawn at the smallest known size
  color: number | null;         // the value that sets the colour (null: grey)
  spark?: number[];
  lines?: [string, string][];   // extra tooltip lines: label, value
};

/** -4..4 from a value and the four thresholds of its positive (and mirrored negative) arm. */
export function level(v: number | null | undefined, steps: readonly number[]): number {
  if (v === null || v === undefined || !Number.isFinite(v)) return NaN;
  const a = Math.abs(v);
  let n = 0;
  for (const s of steps) if (a >= s) n++;
  return v < 0 ? -n : n;
}

function fill(lv: number): string {
  if (Number.isNaN(lv)) return "var(--surface-2)";
  if (lv === 0) return "color-mix(in srgb, var(--gm-0) 30%, var(--surface))";
  const arm = lv > 0 ? "p" : "n";
  return `color-mix(in srgb, var(--gm-${arm}${Math.abs(lv)}) ${MIX[Math.abs(lv)]}, var(--surface))`;
}

const short = (t: string) => t.replace(/\.[A-Z]{1,3}$/, "");

/** A heat map of many names: tiles grouped (e.g. by sector), sized by the chosen measure and coloured by a graded
 *  value. Hovering shows the name's numbers (and highlights its table row through `onHover`); clicking opens it. */
export function Treemap({ items, steps, format, title, highlight, onHover }: {
  items: TreemapItem[];
  steps: readonly number[];
  format: (v: number | null) => string;
  title: string;
  highlight?: string | null;
  onHover?: (ticker: string | null) => void;
}) {
  const nav = useNavigate();
  const [own, setOwn] = useState<string | null>(null);
  const active = own ?? highlight ?? null;
  const hover = (t: string | null) => {
    setOwn(t);
    onHover?.(t);
  };

  const layout = useMemo(() => {
    const known = items.map((i) => i.size).filter((s): s is number => s !== null && Number.isFinite(s) && s > 0);
    const floor = known.length ? Math.min(...known) : 1;
    const groups = new Map<string, Group<TreemapItem>>();
    for (const it of items) {
      const g = groups.get(it.group) ?? { key: it.group, items: [] };
      g.items.push({ item: it, value: it.size !== null && it.size > 0 ? it.size : floor });
      groups.set(it.group, g);
    }
    return nested([...groups.values()], { x: 0, y: 0, w: W, h: H }, 18, 1.5);
  }, [items]);
  const tiles = useMemo(() => layout.flatMap((g) => g.tiles), [layout]);
  const tip = active ? tiles.find((t) => t.item.ticker === active) : undefined;

  if (!items.length) return <p className="empty">No names to show: the filters exclude them all.</p>;
  return (
    <div className="tm-box">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title} className="treemap" onMouseLeave={() => hover(null)}>
        {layout.map((g) => (
          <g key={g.key}>
            <rect x={g.x} y={g.y} width={g.w} height={g.h} className="tm-group" />
            {g.h > 45 && g.w > 50 && (
              <text x={g.x + 5} y={g.y + 13} className="tm-group-label">
                {g.key.length * 6.5 > g.w - 30 ? `${g.key.slice(0, Math.max(3, Math.floor((g.w - 30) / 6.5)))}…` : g.key}
                <tspan className="tm-count"> {g.tiles.length}</tspan>
              </text>
            )}
          </g>
        ))}
        {tiles.map((t) => {
          const it = t.item;
          const lv = level(it.color, steps);
          const big = t.w > 38 && t.h > 20;
          const fs = Math.max(9, Math.min(15, t.w / 6, t.h / 2.6));
          return (
            <g key={it.ticker} className={`tm-tile ${active === it.ticker ? "on" : ""}`} role="link" tabIndex={big ? 0 : -1}
              aria-label={`${it.name ?? it.ticker} (${it.ticker}): ${format(it.color)}`}
              onClick={() => nav(tickerPath(it.ticker))} onKeyDown={(e) => { if (e.key === "Enter") nav(tickerPath(it.ticker)); }}
              onMouseEnter={() => hover(it.ticker)} onFocus={() => hover(it.ticker)} onBlur={() => hover(null)}>
              <rect x={t.x} y={t.y} width={Math.max(t.w, 0)} height={Math.max(t.h, 0)} fill={fill(lv)} />
              {big && (
                <text x={t.x + t.w / 2} y={t.y + t.h / 2 + (t.h > fs * 2.6 ? -fs * 0.15 : fs * 0.35)} textAnchor="middle" fontSize={fs}
                  className="tm-label">
                  {short(it.ticker)}
                  {t.h > fs * 2.6 && <tspan x={t.x + t.w / 2} dy={fs * 1.15} fontSize={fs * 0.82} className="tm-value">{format(it.color)}</tspan>}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {tip && (
        <div className="rrg-tip tm-tip" style={{
          left: `${((tip.x + tip.w / 2) / W) * 100}%`, top: `${((tip.y + tip.h / 2) / H) * 100}%`,
          transform: `translate(${tip.x + tip.w / 2 > W * 0.6 ? "calc(-100% - 10px)" : "10px"}, ${tip.y + tip.h / 2 > H * 0.55 ? "calc(-100% - 6px)" : "6px"})`,
        }}>
          <b>{tip.item.name ?? tip.item.ticker}</b> <span className="muted">{tip.item.ticker}</span>
          <div className="muted">{tip.item.group}</div>
          {tip.item.spark && tip.item.spark.length > 1 && <Sparkline values={tip.item.spark} width={200} height={34} />}
          <div className="tm-lines">
            {(tip.item.lines ?? []).map(([k, v]) => <span key={k}>{k} <b>{v}</b></span>)}
          </div>
        </div>
      )}
    </div>
  );
}

/** Tooltip helpers for the Discover page. */
export const fmt = {
  pct: (v: number | null | undefined) => pct(v ?? null),
  score: (v: number | null | undefined) => num(v ?? null, 0),
  signed: (v: number | null | undefined) => (v === null || v === undefined || !Number.isFinite(v) ? "–" : `${v > 0 ? "+" : ""}${v.toFixed(0)}`),
  dkk: (v: number | null | undefined) => (v === null || v === undefined ? "–" : `${compact(v)} DKK`),
  tone,
};

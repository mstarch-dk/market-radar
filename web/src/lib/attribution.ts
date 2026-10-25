// Geometry for the Attribution tab: the reconciliation's waterfall and the monthly stacked effects. Numbers only
// come from the API; a missing one stays missing (no bar), never drawn as 0.
import { isNum, type Maybe } from "./format";

export const EFFECTS = ["allocation", "selection", "interaction", "currency", "cross"] as const;
export type Effect = (typeof EFFECTS)[number];

export type Step = { key: string; label: string; value: Maybe; from: number | null; to: number | null };

/** The steps from 0 to the active return: each step starts where the previous one ended. After a missing step the
 *  later ones have no position (`from`/`to` null): where they would start is unknown. */
export function waterfall(parts: { key: string; label: string; value: Maybe }[]): Step[] {
  let at: number | null = 0;
  return parts.map((p) => {
    if (at === null || !isNum(p.value)) {
      at = null;
      return { ...p, from: null, to: null };
    }
    const step: Step = { ...p, from: at, to: at + p.value };
    at = step.to;
    return step;
  });
}

/** The range a set of steps (and a total bar from 0) spans, always including 0. */
export function extent(values: (number | null)[]): [number, number] {
  const v = values.filter((x): x is number => x !== null && Number.isFinite(x));
  return [Math.min(0, ...v), Math.max(0, ...v)];
}

export type Segment = { effect: Effect; y0: number; y1: number };

/** One month's effects stacked: positive ones upwards from 0, negative ones downwards, in EFFECTS order. */
export function stack(m: Record<Effect, number>): Segment[] {
  let up = 0;
  let down = 0;
  const out: Segment[] = [];
  for (const e of EFFECTS) {
    const v = m[e];
    if (!Number.isFinite(v) || v === 0) continue;
    if (v > 0) {
      out.push({ effect: e, y0: up, y1: up + v });
      up += v;
    } else {
      out.push({ effect: e, y0: down + v, y1: down });
      down += v;
    }
  }
  return out;
}

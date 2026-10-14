// Squarified treemap layout (Bruls, Huizing & van Wijk): rectangles whose areas are proportional to their values,
// laid out in rows that keep each tile as close to square as possible. Pure functions, so they can be tested.

export type Box = { x: number; y: number; w: number; h: number };
export type Tile<T> = Box & { item: T };
type Area<T> = { item: T; a: number };

function worst<T>(row: Area<T>[], side: number): number {
  let sum = 0, max = 0, min = Infinity;
  for (const r of row) {
    sum += r.a;
    max = Math.max(max, r.a);
    min = Math.min(min, r.a);
  }
  const s2 = sum * sum, w2 = side * side;
  return Math.max((w2 * max) / s2, s2 / (w2 * min));
}

function place<T>(row: Area<T>[], rect: Box, out: Tile<T>[]): Box {
  const sum = row.reduce((s, r) => s + r.a, 0);
  if (rect.w >= rect.h) {                     // a column along the left edge
    const w = rect.h > 0 ? sum / rect.h : 0;
    let y = rect.y;
    for (const r of row) {
      const h = w > 0 ? r.a / w : 0;
      out.push({ x: rect.x, y, w, h, item: r.item });
      y += h;
    }
    return { x: rect.x + w, y: rect.y, w: rect.w - w, h: rect.h };
  }
  const h = rect.w > 0 ? sum / rect.w : 0;    // a row along the top edge
  let x = rect.x;
  for (const r of row) {
    const w = h > 0 ? r.a / h : 0;
    out.push({ x, y: rect.y, w, h, item: r.item });
    x += w;
  }
  return { x: rect.x, y: rect.y + h, w: rect.w, h: rect.h - h };
}

/** Lay `items` out in `box`, each tile's area proportional to its value. Values ≤ 0 or not finite are left out. */
export function squarify<T>(items: { item: T; value: number }[], box: Box): Tile<T>[] {
  const valid = items.filter((i) => Number.isFinite(i.value) && i.value > 0).sort((a, b) => b.value - a.value);
  const total = valid.reduce((s, i) => s + i.value, 0);
  if (!total || box.w <= 0 || box.h <= 0) return [];
  const scale = (box.w * box.h) / total;
  const areas = valid.map((i) => ({ item: i.item, a: i.value * scale }));
  const out: Tile<T>[] = [];
  let rect = { ...box };
  let row: Area<T>[] = [];
  let i = 0;
  while (i < areas.length) {
    const side = Math.min(rect.w, rect.h);
    const next = [...row, areas[i]!];
    if (row.length === 0 || worst(next, side) <= worst(row, side)) {
      row = next;
      i++;
    } else {
      rect = place(row, rect, out);
      row = [];
    }
  }
  if (row.length) place(row, rect, out);
  return out;
}

export type Group<T> = { key: string; items: { item: T; value: number }[] };
export type GroupTile<T> = Box & { key: string; total: number; tiles: Tile<T>[] };

/** Two levels: groups sized by their total, then each group's items inside it, below a header strip. */
export function nested<T>(groups: Group<T>[], box: Box, header = 16, pad = 1): GroupTile<T>[] {
  const sized = groups.map((g) => ({
    item: g, value: g.items.reduce((s, i) => s + (Number.isFinite(i.value) && i.value > 0 ? i.value : 0), 0),
  }));
  return squarify(sized, box).map((gt) => {
    const showHeader = gt.h > header * 2.5 && gt.w > 40;
    const inner = { x: gt.x + pad, y: gt.y + (showHeader ? header : pad), w: gt.w - 2 * pad, h: gt.h - (showHeader ? header : pad) - pad };
    return { x: gt.x, y: gt.y, w: gt.w, h: gt.h, key: gt.item.key, total: sized.find((s) => s.item === gt.item)!.value,
      tiles: squarify(gt.item.items, inner) };
  });
}

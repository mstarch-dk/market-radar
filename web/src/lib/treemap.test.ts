import { describe, expect, it } from "vitest";
import { nested, squarify, type Box, type Tile } from "./treemap";

const BOX: Box = { x: 0, y: 0, w: 600, h: 400 };
const EPS = 1e-6;

function overlap(a: Box, b: Box): number {
  const w = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
  const h = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
  return w > 0 && h > 0 ? w * h : 0;
}

function inside(t: Box, box: Box): boolean {
  return t.x >= box.x - EPS && t.y >= box.y - EPS && t.x + t.w <= box.x + box.w + EPS && t.y + t.h <= box.y + box.h + EPS;
}

const values = [60, 30, 30, 12, 8, 6, 6, 4, 2, 1, 0.5];

describe("squarify", () => {
  const tiles = squarify(values.map((v, i) => ({ item: i, value: v })), BOX);

  it("fills the box with areas proportional to the values", () => {
    const total = values.reduce((s, v) => s + v, 0);
    expect(tiles).toHaveLength(values.length);
    expect(tiles.reduce((s, t) => s + t.w * t.h, 0)).toBeCloseTo(BOX.w * BOX.h, 6);
    for (const t of tiles) expect((t.w * t.h) / (BOX.w * BOX.h)).toBeCloseTo(values[t.item]! / total, 9);
  });

  it("keeps every tile inside the box without overlaps", () => {
    for (const t of tiles) expect(inside(t, BOX)).toBe(true);
    for (let i = 0; i < tiles.length; i++)
      for (let j = i + 1; j < tiles.length; j++) expect(overlap(tiles[i]!, tiles[j]!)).toBeLessThan(EPS);
  });

  it("keeps big tiles reasonably square", () => {
    const big = tiles.find((t) => t.item === 0)!;
    expect(Math.max(big.w / big.h, big.h / big.w)).toBeLessThan(3);
  });

  it("leaves out missing, zero and negative values, and handles empty input", () => {
    const t = squarify([{ item: "a", value: 1 }, { item: "b", value: 0 }, { item: "c", value: NaN }, { item: "d", value: -2 }], BOX);
    expect(t.map((x) => x.item)).toEqual(["a"]);
    expect(t[0]).toMatchObject({ x: 0, y: 0, w: 600, h: 400 });
    expect(squarify([], BOX)).toEqual([]);
    expect(squarify([{ item: 1, value: 1 }], { x: 0, y: 0, w: 0, h: 10 })).toEqual([]);
  });
});

describe("nested", () => {
  it("sizes groups by their totals and keeps each group's tiles inside it", () => {
    const groups = [
      { key: "Tech", items: [{ item: "A", value: 50 }, { item: "B", value: 25 }] },
      { key: "Banks", items: [{ item: "C", value: 20 }, { item: "D", value: 5 }] },
    ];
    const out = nested(groups, BOX, 16, 1);
    expect(out.map((g) => g.key).sort()).toEqual(["Banks", "Tech"]);
    const tech = out.find((g) => g.key === "Tech")!;
    expect((tech.w * tech.h) / (BOX.w * BOX.h)).toBeCloseTo(0.75, 9);
    for (const g of out) {
      for (const t of g.tiles as Tile<string>[]) expect(inside(t, g)).toBe(true);
    }
    const all = out.flatMap((g) => g.tiles);
    for (let i = 0; i < all.length; i++)
      for (let j = i + 1; j < all.length; j++) expect(overlap(all[i]!, all[j]!)).toBeLessThan(EPS);
  });
});

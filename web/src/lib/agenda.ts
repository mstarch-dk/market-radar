// The calendar page's layout, as pure functions (dates are "YYYY-MM-DD" strings, done in UTC so no time zone moves a
// day): the filters, the ISO weeks of the agenda and the month grid. The items and their levels come from the API.

import type { AgendaView } from "../api/client";

export type Item = AgendaView["items"][number];
export type Level = Item["level"];
export type Kind = Item["kind"];
export type Who = "all" | "holding" | "watch";

export const KINDS: [Kind, string][] = [
  ["earnings", "Earnings"], ["ex_dividend", "Ex-dividend"], ["review", "My reviews"], ["time_stop", "Time stops"]];

export const LEVEL_LABEL: Record<Level, string> = { high: "high", normal: "normal", info: "info" };

/** The badge look of a level: high asks for attention (amber), normal is plain accent, info is quiet. */
export const LEVEL_KIND: Record<Level, string> = { high: "warn", normal: "accent", info: "na" };

const DAY = 86_400_000;

const toMs = (iso: string) => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10));
const toIso = (ms: number) => new Date(ms).toISOString().slice(0, 10);

export function addDays(iso: string, n: number): string {
  return toIso(toMs(iso) + n * DAY);
}

/** Monday = 0 … Sunday = 6. */
const weekday = (iso: string) => (new Date(toMs(iso)).getUTCDay() + 6) % 7;

/** The ISO week of a day: its Monday, and "2026-W44" (the week's year is that of its Thursday). */
export function isoWeek(iso: string): { key: string; monday: string; week: number } {
  const monday = addDays(iso, -weekday(iso));
  const thursday = addDays(monday, 3);
  const jan1 = Date.UTC(+thursday.slice(0, 4), 0, 1);
  const week = Math.floor((toMs(thursday) - jan1) / DAY / 7) + 1;
  return { key: `${thursday.slice(0, 4)}-W${String(week).padStart(2, "0")}`, monday, week };
}

/** The held / watched filter and the kinds. Your own dates (reviews, time stops) are about what you own or decided,
 *  so they stay under "holding" as well as "all". */
export function filterItems(items: Item[], who: Who, kinds: ReadonlySet<Kind>): Item[] {
  return items.filter((i) => kinds.has(i.kind) && (
    who === "all" || i.status === who || (who === "holding" && i.status === "own")));
}

/** The agenda: items grouped by ISO week in date order (an ongoing window counts from the day it started). */
export function byWeek(items: Item[]): { key: string; week: number; monday: string; items: Item[] }[] {
  const out = new Map<string, { key: string; week: number; monday: string; items: Item[] }>();
  for (const i of [...items].sort((a, b) => a.date.localeCompare(b.date))) {
    const w = isoWeek(i.date);
    if (!out.has(w.key)) out.set(w.key, { ...w, items: [] });
    out.get(w.key)!.items.push(i);
  }
  return [...out.values()];
}

/** How an item sits on one day of the grid: a single date, or the start, middle or end of a range (drawn lighter). */
export type Part = "day" | "start" | "mid" | "end";
export type Cell = { date: string; inMonth: boolean; today: boolean; entries: { item: Item; part: Part }[] };

/** The months ("YYYY-MM") a window of days touches, from `today` on. */
export function monthsOf(today: string, days: number): string[] {
  const out: string[] = [];
  for (let m = today.slice(0, 7); m <= addDays(today, days).slice(0, 7);) {
    out.push(m);
    const [y, mo] = [+m.slice(0, 4), +m.slice(5, 7)];
    m = mo === 12 ? `${y + 1}-01` : `${y}-${String(mo + 1).padStart(2, "0")}`;
  }
  return out;
}

/** A month as whole Monday-to-Sunday weeks of cells. Each item appears on every day it spans: a range from its first
 *  to its last day (clipped to the grid), a single date on its day. Within a day: by level, then weight. */
export function monthGrid(items: Item[], month: string, today: string): Cell[][] {
  const first = `${month}-01`;
  const start = addDays(first, -weekday(first));
  const nextMonth = monthsOf(first, 31).find((m) => m > month)!;
  const last = addDays(`${nextMonth}-01`, -1);
  const end = addDays(last, 6 - weekday(last));
  const rank = (i: Item) => ["high", "normal", "info"].indexOf(i.level);
  const sorted = [...items].sort((a, b) => rank(a) - rank(b) || (b.weight ?? 0) - (a.weight ?? 0));
  const weeks: Cell[][] = [];
  for (let d = start; d <= end; d = addDays(d, 1)) {
    if (weekday(d) === 0) weeks.push([]);
    const entries = sorted.flatMap((item) => {
      const to = item.date_end ?? item.date;
      if (d < item.date || d > to) return [];
      const part: Part = item.date === to ? "day" : d === item.date ? "start" : d === to ? "end" : "mid";
      return [{ item, part }];
    });
    weeks[weeks.length - 1]!.push({ date: d, inMonth: d.slice(0, 7) === month, today: d === today, entries });
  }
  return weeks;
}

/** "28 Oct" or, for a range, "28 Oct – 3 Nov": a range is never shown as its first day. */
export function when(i: Pick<Item, "date" | "date_end">): string {
  const f = (iso: string) => new Date(toMs(iso)).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
  return i.date_end && i.date_end !== i.date ? `${f(i.date)} – ${f(i.date_end)}` : f(i.date);
}

/** "in 4 d", "today", "3 d ago" (an overdue review, or a window under way). */
export function inDays(n: number): string {
  return n === 0 ? "today" : n > 0 ? `in ${n} d` : `${-n} d ago`;
}

/** The items of `soon`, in its order (the API's ids). */
export function soonItems(v: Pick<AgendaView, "items" | "soon">): Item[] {
  const byId = new Map(v.items.map((i) => [i.id, i]));
  return v.soon.map((id) => byId.get(id)).filter((i): i is Item => i !== undefined);
}

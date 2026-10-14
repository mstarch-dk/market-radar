/** Which portfolios a page shows, kept in the URL as `?pf=`: "real" (default: yours), "virtual", "all", a list
 *  of ids ("3,5") or tags ("tag:sim-a,tag:sim-b"). Ids and tags may be mixed. */
export type PortfolioSel =
  | { scope: "real" | "virtual" | "all" }
  | { ids: number[]; tags: string[] };

export const DEFAULT_SEL: PortfolioSel = { scope: "real" };

export function parseSel(raw: string | null | undefined): PortfolioSel {
  const v = (raw ?? "").trim();
  if (v === "virtual" || v === "all") return { scope: v };
  const ids: number[] = [];
  const tags: string[] = [];
  for (const part of v.split(",").map((p) => p.trim()).filter(Boolean)) {
    if (part.startsWith("tag:")) {
      const t = part.slice(4).trim().toLowerCase();
      if (t && !tags.includes(t)) tags.push(t);
    } else if (/^\d+$/.test(part)) {
      const n = Number(part);
      if (!ids.includes(n)) ids.push(n);
    }
  }
  return ids.length || tags.length ? { ids, tags } : DEFAULT_SEL;
}

export function formatSel(sel: PortfolioSel): string {
  if ("scope" in sel) return sel.scope;
  return [...sel.ids.map(String), ...sel.tags.map((t) => `tag:${t}`)].join(",") || "real";
}

/** Query-string parameters for the API (`portfolio`, `tag`, `scope`); empty for the default (yours). */
export function selQuery(sel: PortfolioSel): string {
  const q = new URLSearchParams();
  if ("scope" in sel) {
    if (sel.scope !== "real") q.set("scope", sel.scope);
  } else {
    sel.ids.forEach((id) => q.append("portfolio", String(id)));
    sel.tags.forEach((t) => q.append("tag", t));
  }
  return q.toString();
}

export const isDefaultSel = (sel: PortfolioSel) => "scope" in sel && sel.scope === "real";

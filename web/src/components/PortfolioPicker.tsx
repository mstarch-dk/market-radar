import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { DEFAULT_SEL, formatSel, isDefaultSel, parseSel, type PortfolioSel } from "../lib/portfolioSel";

/** The portfolio selection in the URL (`?pf=`), so a view of a virtual portfolio can be bookmarked or shared. */
export function usePortfolioSel(): [PortfolioSel, (s: PortfolioSel) => void] {
  const [params, setParams] = useSearchParams();
  const sel = parseSel(params.get("pf"));
  const set = (s: PortfolioSel) => setParams((p) => {
    const next = new URLSearchParams(p);
    if (isDefaultSel(s)) next.delete("pf"); else next.set("pf", formatSel(s));
    return next;
  }, { replace: true });
  return [sel, set];
}

/** Choose whose numbers a page shows: yours (the real portfolios, default), all virtual ones, one portfolio, or
 *  every portfolio with a tag (an A/B group). */
export function PortfolioPicker({ sel, onChange }: { sel: PortfolioSel; onChange: (s: PortfolioSel) => void }) {
  const { data: portfolios = [] } = useQuery({ queryKey: ["portfolios"], queryFn: api.portfolios });
  const { data: tags = [] } = useQuery({ queryKey: ["portfolio-tags"], queryFn: api.tags });
  const value = formatSel(sel);
  const known = new Set(["real", "virtual", "all", ...portfolios.map((p) => String(p.id)), ...tags.map((t) => `tag:${t.tag}`)]);
  const real = portfolios.filter((p) => p.mode === "real" && !p.archived);
  const virtual = portfolios.filter((p) => p.mode === "virtual" && !p.archived);
  const archived = portfolios.filter((p) => p.archived);
  return (
    <label className="pf-picker small">Portfolio
      <select value={value} onChange={(e) => onChange(parseSel(e.target.value))} aria-label="Portfolio">
        <option value="real">Yours: every real portfolio</option>
        {!known.has(value) && <option value={value}>{value}</option>}
        {real.length > 0 && <optgroup label="Real">{real.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</optgroup>}
        {virtual.length > 0 && (
          <optgroup label="Virtual">
            <option value="virtual">Every virtual portfolio</option>
            {virtual.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </optgroup>
        )}
        {tags.length > 0 && <optgroup label="Tagged">{tags.map((t) => <option key={t.tag} value={`tag:${t.tag}`}>#{t.tag} ({t.n})</option>)}</optgroup>}
        {archived.length > 0 && <optgroup label="Archived">{archived.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</optgroup>}
        <option value="all">Everything, virtual included</option>
      </select>
      {!isDefaultSel(sel) && <button type="button" className="linkish" onClick={() => onChange(DEFAULT_SEL)}>back to yours</button>}
    </label>
  );
}

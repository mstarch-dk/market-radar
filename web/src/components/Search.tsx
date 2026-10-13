import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

/** Yahoo symbol search; Enter on free text opens it as a symbol directly. */
export function Search({ autoFocus = false }: { autoFocus?: boolean }) {
  const nav = useNavigate();
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setQ(text.trim()), 250);
    return () => clearTimeout(t);
  }, [text]);

  const { data: hits = [], isFetching } = useQuery({
    queryKey: ["search", q],
    queryFn: () => api.search(q),
    enabled: q.length >= 1,
    staleTime: 5 * 60_000,
  });

  const go = (symbol: string) => {
    setOpen(false);
    setText("");
    nav(`/ticker/${encodeURIComponent(symbol.toUpperCase())}`);
  };

  return (
    <div className="search">
      <input
        type="search"
        placeholder="Search a company, ETF or Yahoo symbol (e.g. NOVO-B.CO)"
        aria-label="Search ticker"
        autoFocus={autoFocus}
        value={text}
        onChange={(e) => { setText(e.target.value); setSel(0); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { setSel((s) => Math.min(s + 1, hits.length - 1)); e.preventDefault(); }
          if (e.key === "ArrowUp") { setSel((s) => Math.max(s - 1, 0)); e.preventDefault(); }
          if (e.key === "Escape") setOpen(false);
          if (e.key === "Enter" && text.trim()) {
            const hit = q === text.trim() ? hits[sel] : undefined;
            go(hit ? hit.symbol : text.trim());
          }
        }}
      />
      {open && text.trim() && (hits.length > 0 || isFetching) && (
        <div className="results" role="listbox">
          {hits.map((h, i) => (
            <button key={h.symbol} role="option" aria-selected={i === sel} onMouseDown={() => go(h.symbol)}>
              <span className="sym">{h.symbol}</span>
              <span>{h.name}{h.tracked && <span className="badge accent" style={{ marginLeft: 6 }}>tracked</span>}</span>
              <span className="ex">{h.exchange} · {h.quote_type}</span>
            </button>
          ))}
          {isFetching && hits.length === 0 && <div className="muted small" style={{ padding: "8px 12px" }}>Searching…</div>}
        </div>
      )}
    </div>
  );
}

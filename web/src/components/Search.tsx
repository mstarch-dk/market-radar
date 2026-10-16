import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { HitRow, useSymbolSearch } from "./SymbolPicker";

/** Yahoo symbol search; Enter on free text opens it as a symbol directly. */
export function Search({ autoFocus = false }: { autoFocus?: boolean }) {
  const nav = useNavigate();
  const [text, setText] = useState("");
  const [sel, setSel] = useState(0);
  const [open, setOpen] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  // "/" anywhere (outside a text field) jumps to the search box
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey) return;
      if (t && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName))) return;
      e.preventDefault();
      input.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const { q, hits, isFetching } = useSymbolSearch(text);

  const go = (symbol: string) => {
    setOpen(false);
    setText("");
    nav(`/ticker/${encodeURIComponent(symbol.toUpperCase())}`);
  };

  return (
    <div className="search">
      <input
        ref={input}
        type="search"
        placeholder="Search a company, ETF or Yahoo symbol (press / to focus)"
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
              <HitRow h={h} />
            </button>
          ))}
          {isFetching && hits.length === 0 && <div className="muted small" style={{ padding: "8px 12px" }}>Searching…</div>}
        </div>
      )}
    </div>
  );
}

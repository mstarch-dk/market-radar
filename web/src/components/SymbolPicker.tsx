import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, type SearchHit } from "../api/client";

/** Yahoo symbol search for a text field: debounced, cached; shared by the header search and the ticker field. */
export function useSymbolSearch(text: string, enabled = true) {
  const [q, setQ] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setQ(text.trim()), 250);
    return () => clearTimeout(t);
  }, [text]);
  const { data: hits = [], isFetching } = useQuery({ queryKey: ["search", q], queryFn: () => api.search(q),
    enabled: enabled && q.length >= 1, staleTime: 5 * 60_000 });
  return { q, hits, isFetching };
}

export function HitRow({ h }: { h: SearchHit }) {
  return (
    <>
      <span className="sym">{h.symbol}</span>
      <span>{h.name}{h.tracked && <span className="badge accent" style={{ marginLeft: 6 }}>tracked</span>}</span>
      <span className="ex">{h.exchange}{h.quote_type && ` · ${h.quote_type}`}</span>
    </>
  );
}

/** A ticker field with Yahoo search suggestions (exchange shown, so NOVO-B.CO isn't confused with NVO): arrow keys
 *  and Enter pick one, and the chosen company's name shows under the field. Free text is allowed: the API checks
 *  the symbol when the trade is validated. */
export function SymbolPicker({ value, onChange, autoFocus }: { value: string; onChange: (s: string) => void; autoFocus?: boolean }) {
  const [text, setText] = useState(value);
  const [open, setOpen] = useState(false);
  const [sel, setSel] = useState(0);
  const [picked, setPicked] = useState<SearchHit | null>(null);
  useEffect(() => setText(value), [value]);
  const { q, hits, isFetching } = useSymbolSearch(text, open);
  // the name of a symbol that wasn't picked from the list (typed, or a row being edited)
  const known = useQuery({ queryKey: ["search", value], queryFn: () => api.search(value), enabled: !!value && picked?.symbol !== value,
    staleTime: 5 * 60_000 });
  const info = picked?.symbol === value ? picked : known.data?.find((h) => h.symbol === value);
  const pick = (h: SearchHit | string) => {
    const s = typeof h === "string" ? h.trim().toUpperCase() : h.symbol;
    setPicked(typeof h === "string" ? null : h);
    setText(s);
    onChange(s);
    setOpen(false);
  };
  const shown = q === text.trim() ? hits.slice(0, 8) : [];
  return (
    <div className="search symbol-picker">
      <input value={text} autoFocus={autoFocus} placeholder="Company name or symbol, e.g. Novo Nordisk" aria-label="Ticker"
        role="combobox" aria-expanded={open && shown.length > 0} aria-autocomplete="list"
        onChange={(e) => { setText(e.target.value); setSel(0); setOpen(true); }}
        onFocus={() => text && setOpen(true)}
        onBlur={() => { setTimeout(() => setOpen(false), 150); if (text.trim().toUpperCase() !== value) onChange(text.trim().toUpperCase()); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { setOpen(true); setSel((s) => Math.max(0, Math.min(s + 1, shown.length - 1))); e.preventDefault(); }
          if (e.key === "ArrowUp") { setSel((s) => Math.max(s - 1, 0)); e.preventDefault(); }
          if (e.key === "Escape") setOpen(false);
          if (e.key === "Enter") { e.preventDefault(); if (text.trim()) pick(open && shown[sel] ? shown[sel] : text); }
        }} />
      {open && text.trim() && (shown.length > 0 || isFetching) && (
        <div className="results" role="listbox">
          {shown.map((h, i) => (
            <button type="button" key={h.symbol} role="option" aria-selected={i === sel} onMouseDown={() => pick(h)}>
              <HitRow h={h} />
            </button>
          ))}
          {isFetching && shown.length === 0 && <div className="muted small" style={{ padding: "8px 12px" }}>Searching…</div>}
        </div>
      )}
      {info && !open && <span className="hint picked">{info.name}{info.exchange && ` · ${info.exchange}`}{info.quote_type && ` · ${info.quote_type}`}</span>}
    </div>
  );
}

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../api/client";

/** A ticker field with Yahoo search suggestions (exchange shown, so NOVO-B.CO isn't confused with NVO). Free text
 *  is allowed: the API checks the symbol when the trade is validated. */
export function SymbolPicker({ value, onChange, autoFocus }: { value: string; onChange: (s: string) => void; autoFocus?: boolean }) {
  const [text, setText] = useState(value);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  useEffect(() => setText(value), [value]);
  useEffect(() => {
    const t = setTimeout(() => setQ(text.trim()), 250);
    return () => clearTimeout(t);
  }, [text]);
  const { data: hits = [] } = useQuery({ queryKey: ["search", q], queryFn: () => api.search(q), enabled: open && q.length >= 2,
    staleTime: 5 * 60_000 });
  const pick = (s: string) => {
    setText(s);
    onChange(s);
    setOpen(false);
  };
  return (
    <div className="search symbol-picker">
      <input value={text} autoFocus={autoFocus} placeholder="e.g. NOVO-B.CO or Novo Nordisk" aria-label="Ticker"
        onChange={(e) => { setText(e.target.value); setOpen(true); }}
        onBlur={() => { setTimeout(() => setOpen(false), 150); if (text.trim().toUpperCase() !== value) onChange(text.trim().toUpperCase()); }}
        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); pick(hits[0]?.symbol ?? text.trim().toUpperCase()); } }} />
      {open && hits.length > 0 && (
        <div className="results">
          {hits.slice(0, 6).map((h) => (
            <button type="button" key={h.symbol} onMouseDown={() => pick(h.symbol)}>
              <span className="sym">{h.symbol}</span><span>{h.name}</span><span className="ex">{h.exchange}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

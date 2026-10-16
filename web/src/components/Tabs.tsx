import type { ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

/** The page's tab, kept in the URL as `?tab=` (so a tab can be bookmarked and Back returns to the previous one).
 *  An unknown or missing value gives `fallback`; choosing the fallback clears the parameter. */
export function useTabParam<T extends string>(tabs: readonly T[], fallback: T): [T, (t: T) => void] {
  const [params, setParams] = useSearchParams();
  const raw = params.get("tab");
  const tab = tabs.find((t) => t === raw) ?? fallback;
  const set = (t: T) => setParams((p) => {
    const next = new URLSearchParams(p);
    if (t === fallback) next.delete("tab"); else next.set("tab", t);
    return next;
  });
  return [tab, set];
}

/** A row of tabs (the `.seg` look): each tab is [value, label]. */
export function Tabs<T extends string>({ tabs, value, onChange, label, className = "" }: {
  tabs: [T, ReactNode][];
  value: T;
  onChange: (t: T) => void;
  label: string;
  className?: string;
}) {
  return (
    <div className={`seg page-tabs ${className}`} role="tablist" aria-label={label}>
      {tabs.map(([t, l]) => (
        <button key={t} type="button" role="tab" aria-selected={t === value} aria-pressed={t === value} onClick={() => onChange(t)}>
          {l}
        </button>
      ))}
    </div>
  );
}

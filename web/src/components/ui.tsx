import type { ReactNode } from "react";
import type { SectionMeta } from "../api/client";
import { date, tone, type Maybe } from "../lib/format";
import type { GlossaryKey } from "../lib/glossary";
import { Term } from "./Term";
import { Tip } from "./Tip";

export function Card({ title, meta, wide, children, className = "" }: {
  title: string;
  meta?: SectionMeta | null;
  wide?: boolean;
  children: ReactNode;
  className?: string;
}) {
  const missing = meta?.status === "missing";
  return (
    <section className={`card ${wide ? "wide" : ""} ${className}`}>
      <h2>
        {title}
        {meta?.status === "stale" && <span className="badge warn">stale</span>}
        {meta && (
          <span className="meta" title={meta.source}>
            {meta.asof ? `as of ${date(meta.asof)}` : meta.source}
          </span>
        )}
      </h2>
      {missing ? <p className="empty">No data from {meta?.source}.</p> : children}
    </section>
  );
}

export function Badge({ children, kind = "", title }: { children: ReactNode; kind?: string; title?: string }) {
  const b = <span className={`badge ${kind}`}>{children}</span>;
  return title ? <Tip content={title}>{b}</Tip> : b;
}

/** A definition list; rows with `hide` are skipped so empty fields don't pad the card. */
export function KV({ rows }: { rows: [label: ReactNode, value: ReactNode, opts?: { tone?: Maybe; hint?: ReactNode; hide?: boolean; help?: GlossaryKey }][] }) {
  return (
    <dl className="kv">
      {rows.filter(([, , o]) => !o?.hide).map(([label, value, o], i) => (
        <div key={i} style={{ display: "contents" }}>
          <dt>{o?.help ? <Term k={o.help}>{label}</Term> : label}</dt>
          <dd className={o?.tone !== undefined ? tone(o.tone) : ""}>
            {value}
            {o?.hint && <span className="hint">{o.hint}</span>}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function Signed({ v, children }: { v: Maybe; children: ReactNode }) {
  return <span className={tone(v)}>{children}</span>;
}

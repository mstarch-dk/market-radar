import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ApiError } from "../api/client";
import { date, pct, tone, type Maybe } from "../lib/format";
import { Badge } from "./ui";

/** Small display pieces shared by the dashboard pages. Values arrive computed; these only format them. */

export function Pct({ v, digits = 1 }: { v: Maybe; digits?: number }) {
  return <span className={tone(v)}>{pct(v, digits)}</span>;
}

export const QUAD_KIND: Record<string, string> = { Leading: "pos", Weakening: "warn", Lagging: "neg", Improving: "accent" };

export function Quadrant({ q }: { q: string | null | undefined }) {
  if (!q || q === "n/a") return <span className="muted">n/a</span>;
  return <Badge kind={QUAD_KIND[q] ?? ""}>{q}</Badge>;
}

export function RankChange({ v }: { v: number | null | undefined }) {
  if (v === null || v === undefined) return <span className="muted" title="not in the earlier snapshot">new</span>;
  if (v > 0) return <span className="pos">▲{v}</span>;
  if (v < 0) return <span className="neg">▼{-v}</span>;
  return <span className="muted">–</span>;
}

export function Check({ v }: { v: boolean | null | undefined }) {
  return v === true ? <span className="pos">✓</span> : v === false ? <span className="neg">✗</span> : <span className="muted">–</span>;
}

export const STATUS_KIND: Record<string, string> = {
  "risk-on": "pos", "risk-off": "neg", neutral: "", "n/a": "na", stale: "warn", ok: "pos", missing: "neg",
};

export function Signal({ s }: { s: string }) {
  return <Badge kind={STATUS_KIND[s] ?? ""}>{s}</Badge>;
}

export function regimeKind(label: string | null | undefined): string {
  return label === "Risk-on" ? "pos" : label === "Risk-off" ? "neg" : "warn";
}

/** Page title plus "data as of / built" from the last `radar run`. */
export function PageHead({ title, asof, generated, children }: {
  title: string;
  asof?: string;
  generated?: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-head">
      <h1>{title}</h1>
      {asof && (
        <div className="sub">
          Data as of {date(asof)}{generated && <> · built {generated.replace("T", " ").slice(0, 16)}</>} · benchmark MSCI ACWI
        </div>
      )}
      {children && <div className="note">{children}</div>}
    </div>
  );
}

/** Loading, "no dashboard yet" and error states for a dashboard query; renders `children` with the data. */
export function Loaded<T>({ q, title, children }: { q: UseQueryResult<T>; title: string; children: (data: T) => ReactNode }) {
  if (q.isPending) return <><PageHead title={title} /><div className="skeleton" style={{ height: 400 }} aria-busy="true" /></>;
  if (q.isError) {
    const e = q.error;
    return (
      <>
        <PageHead title={title} />
        <div className="error">
          {e instanceof ApiError && e.status === 503
            ? <>No dashboard data yet. Run <code>uv run radar run</code> (or <code>uv run radar report</code> on cached data), then reload.</>
            : `Couldn't load: ${e.message}`}
        </div>
      </>
    );
  }
  return <>{children(q.data)}</>;
}

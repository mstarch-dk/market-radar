import type { AlignCompact } from "../api/client";
import { ALIGN_KIND, ALIGN_TEXT, alignSort } from "../lib/views";
import type { Col } from "./columns";
import { Badge } from "./ui";

function AlignBadge({ a }: { a?: AlignCompact }) {
  if (!a || a.label === "unrelated") return <span className="muted">–</span>;
  const why = a.views.flatMap((v) => v.reasons).join("; ");
  return <Badge kind={ALIGN_KIND[a.label]} title={why}>{ALIGN_TEXT[a.label]}</Badge>;
}

/** Inserts a "Views" column (how each row lines up with your market views) after the first column. Without
 *  views the columns are returned unchanged. */
export function withViews<T extends { ticker: string }>(cols: Col<T>[], align: Record<string, AlignCompact>): Col<T>[] {
  if (!Object.keys(align).length) return cols;
  const col: Col<T> = {
    key: "views", label: "Views", name: "My market views", align: "l", help: "views_align",
    sort: (r) => alignSort(align[r.ticker]), filter: { kind: "enum", value: (r) => align[r.ticker]?.label },
    csv: (r) => align[r.ticker]?.label, render: (r) => <AlignBadge a={align[r.ticker]} />,
  };
  return [cols[0]!, col, ...cols.slice(1)];
}

import type { ReactNode } from "react";
import type { GlossaryKey } from "../lib/glossary";
import type { ColSpec } from "../lib/tableState";

export type Col<T> = ColSpec<T> & {
  label: ReactNode;
  /** Plain-text name for menus, filter chips and the CSV header (defaults to `label` when it is a string). */
  name?: string;
  render: (row: T) => ReactNode;
  align?: "l" | "r";
  help?: GlossaryKey;
  /** Tint the cell by the sign and size of its value (return columns). */
  heat?: boolean;
  /** Hidden until switched on in the Columns menu. */
  hidden?: boolean;
  /** Raw value for CSV export (defaults to the sort value); `false` leaves the column out of the export. */
  csv?: ((row: T) => unknown) | false;
  /** CSV header when the raw value differs from what the column shows (e.g. "Ticker" under "Company"). */
  csvHeader?: string;
};

export const colName = <T,>(c: Col<T>) => c.name ?? (typeof c.label === "string" ? c.label : c.key);

/** Columns hidden by default, as useHiddenColumns expects them. */
export const defaultHidden = <T,>(cols: Col<T>[]) => cols.filter((c) => c.hidden).map((c) => c.key);

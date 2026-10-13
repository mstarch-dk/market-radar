import type { ReactNode } from "react";
import { glossary, type GlossaryKey } from "../lib/glossary";
import { Tip } from "./Tip";

/** A metric label that explains itself on hover or focus (dotted underline). */
export function Term({ k, children }: { k: GlossaryKey; children: ReactNode }) {
  const text = glossary(k);
  if (!text) return <>{children}</>;
  return <Tip content={text} className="term">{children}</Tip>;
}

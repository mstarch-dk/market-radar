import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { glossary, type GlossaryKey } from "../lib/glossary";
import { useGuideTree } from "../lib/guide";
import { Tip } from "./Tip";

/** A metric label that explains itself on hover or focus (dotted underline), with a link to the textbook section
 *  when guide/guide.yaml maps the term to one. The link opens in a new tab so the page being read stays put. */
export function Term({ k, children }: { k: GlossaryKey; children: ReactNode }) {
  const text = glossary(k);
  const more = useGuideTree().data?.glossary_links[k];
  if (!text) return <>{children}</>;
  const content = more
    ? <>{text} <Link to={`/guide/${more}`} className="tip-more" target="_blank" rel="noopener">Læs mere i lærebogen →</Link></>
    : text;
  return <Tip content={content} className="term" interactive={!!more}>{children}</Tip>;
}

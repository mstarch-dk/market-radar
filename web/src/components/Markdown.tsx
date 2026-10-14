import "katex/dist/katex.min.css";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import { Link } from "react-router-dom";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { calloutKind, classifyHref } from "../lib/guide";

/** The Markdown renderer shared by the Guide and the Notebook: GFM tables, KaTeX math, callouts, links that stay in
 *  the app, and heading ids from the server (so links and "on this page" lists agree with it). Import it only from
 *  lazy-loaded pages: it brings react-markdown and KaTeX along. */

export type Heading = { level: number; text: string; id: string };

type HastNode = { type: string; tagName?: string; value?: string; properties?: Record<string, unknown>; children?: HastNode[] };

/** A rehype step that gives h1–h4 the server's ids in document order (one slug rule, in guide.py). */
function rehypeIds(ids: string[]) {
  return () => (tree: HastNode) => {
    let i = 0;
    const walk = (n: HastNode) => {
      if (n.type === "element" && /^h[1-4]$/.test(n.tagName ?? "")) {
        const id = ids[i++];
        if (id) n.properties = { ...n.properties, id };
      }
      n.children?.forEach(walk);
    };
    walk(tree);
  };
}

function hastText(n: HastNode | undefined): string {
  if (!n) return "";
  if (n.type === "text") return n.value ?? "";
  return (n.children ?? []).map(hastText).join("");
}

export function Markdown({ markdown, headings, anchorLabel = "Link to this section" }: {
  markdown: string;
  headings: Heading[];
  anchorLabel?: string;
}) {
  const heading = (Tag: "h1" | "h2" | "h3" | "h4") => ({ id, children }: { id?: string; children?: ReactNode }) => (
    <Tag id={id}>{children}{id && Tag !== "h1" && <a className="anchor" href={`#${id}`} aria-label={anchorLabel}>#</a>}</Tag>
  );
  const ids = useMemo(() => rehypeIds(headings.map((h) => h.id)), [headings]);
  const components: Components = {
    h1: heading("h1"), h2: heading("h2"), h3: heading("h3"), h4: heading("h4"),
    a: ({ href = "", children }) => {
      const k = classifyHref(href);
      if (k.kind === "external") return <a href={k.to} target="_blank" rel="noopener noreferrer">{children}</a>;
      if (k.kind === "anchor") return <a href={k.to}>{children}</a>;
      return <Link to={k.to}>{children}</Link>;
    },
    blockquote: ({ node, children }) => {
      const kind = calloutKind(hastText(node as unknown as HastNode));
      return <blockquote className={kind ? `callout ${kind}` : undefined}>{children}</blockquote>;
    },
    table: ({ children }) => <div className="prose-table"><table>{children}</table></div>,
  };
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[ids, rehypeKatex]} components={components}>
      {markdown}
    </ReactMarkdown>
  );
}

/** The h2/h3 the reader is in (the last one scrolled past the top). */
export function useActiveHeading(headings: Heading[] | undefined) {
  const [active, setActive] = useState<string | null>(null);
  useEffect(() => {
    if (!headings) return;
    const ids = headings.filter((h) => h.level === 2 || h.level === 3).map((h) => h.id);
    const onScroll = () => {
      let cur: string | null = null;
      for (const id of ids) {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top < 120) cur = id;
      }
      setActive(cur);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [headings]);
  return active;
}

/** Scroll to the #heading in the URL once the text is there, else to the top. */
export function useScrollToHash(ready: unknown, hash: string) {
  useEffect(() => {
    if (!ready) return;
    const el = hash ? document.getElementById(decodeURIComponent(hash.slice(1))) : null;
    if (el) el.scrollIntoView();
    else window.scrollTo(0, 0);
  }, [ready, hash]);
}

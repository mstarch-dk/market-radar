import "katex/dist/katex.min.css";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import { Link, NavLink, Route, Routes, useLocation, useParams } from "react-router-dom";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { api, ApiError, type GuideChapter, type GuideTree } from "../api/client";
import { calloutKind, classifyHref, useGuideTree } from "../lib/guide";

/** The Danish books (guide/ in the repo): a user guide and a textbook, with a sidebar, search and a table of
 *  contents per chapter. Loaded on demand, so the Markdown and KaTeX code stays out of the rest of the app. */
export default function Guide() {
  const tree = useGuideTree();
  if (tree.isPending) return <div className="skeleton" style={{ height: 400 }} aria-busy="true" />;
  if (tree.isError) return <div className="error">Bøgerne kunne ikke hentes: {tree.error.message}</div>;
  return (
    <Routes>
      <Route index element={<Landing tree={tree.data} />} />
      <Route path=":book/:slug" element={<Chapter tree={tree.data} />} />
      <Route path="*" element={<Landing tree={tree.data} />} />
    </Routes>
  );
}

function useNarrow(px = 900) {
  const q = `(max-width: ${px}px)`;
  const [narrow, setNarrow] = useState(() => window.matchMedia(q).matches);
  useEffect(() => {
    const m = window.matchMedia(q);
    const on = () => setNarrow(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, [q]);
  return narrow;
}

function useTitle(title: string) {
  useEffect(() => {
    const before = document.title;
    document.title = `${title} · Market Radar`;
    return () => { document.title = before; };
  }, [title]);
}

// ---------------- search ----------------

function Search({ autoFocus }: { autoFocus?: boolean }) {
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setQ(text.trim()), 250);
    return () => clearTimeout(t);
  }, [text]);
  const res = useQuery({ queryKey: ["guide-search", q], queryFn: () => api.guideSearch(q), enabled: q.length >= 2 });
  return (
    <div className="guide-search" role="search">
      <input type="search" placeholder="Søg i bøgerne…" aria-label="Søg i bøgerne" value={text} autoFocus={autoFocus}
        onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Escape") setText(""); }} />
      {q.length >= 2 && (
        <div className="guide-hits" aria-live="polite">
          {res.isPending ? <p className="muted small">Søger…</p>
            : res.isError ? <p className="neg small">Søgningen fejlede: {res.error.message}</p>
            : res.data.length === 0 ? <p className="muted small">Intet fundet for &ldquo;{q}&rdquo;.</p>
            : res.data.map((h, i) => (
              <Link key={i} className="guide-hit" onClick={() => setText("")}
                to={`/guide/${h.book}/${h.slug}${h.anchor ? `#${h.anchor}` : ""}`}>
                <b>{h.title}</b>{h.section && <span className="muted"> › {h.section}</span>}
                <span className="small muted">{h.snippet}</span>
              </Link>
            ))}
        </div>
      )}
    </div>
  );
}

// ---------------- landing ----------------

function Landing({ tree }: { tree: GuideTree }) {
  useTitle("Guide");
  return (
    <div className="guide-landing">
      <div className="page-head">
        <h1>Guide</h1>
        <div className="note">To bøger på dansk: en brugervejledning til appen og en lærebog om teorien bag den.
          Begge findes også som Markdown-filer i mappen <code>guide/</code>.</div>
      </div>
      <Search autoFocus />
      <div className="guide-books">
        {tree.books.map((b) => (
          <section key={b.id} className="card guide-book">
            <h2><Link to={`/guide/${b.id}/${b.parts[0]?.chapters[0]?.slug ?? ""}`}>{b.title}</Link></h2>
            <p className="muted">{b.intro}</p>
            {b.parts.map((p) => (
              <div key={p.title} className="guide-book-part">
                <h3>{p.title}</h3>
                <ol>
                  {p.chapters.map((c) => <li key={c.slug}><Link to={`/guide/${b.id}/${c.slug}`}>{c.title}</Link></li>)}
                </ol>
              </div>
            ))}
          </section>
        ))}
      </div>
    </div>
  );
}

// ---------------- sidebar ----------------

function BookNav({ tree, book, slug }: { tree: GuideTree; book: string; slug: string }) {
  const b = tree.books.find((x) => x.id === book) ?? tree.books[0]!;
  return (
    <nav aria-label="Indhold">
      <div className="guide-switch" role="tablist">
        {tree.books.map((x) => (
          <Link key={x.id} role="tab" aria-selected={x.id === b.id} className={x.id === b.id ? "on" : ""}
            to={`/guide/${x.id}/${x.parts[0]?.chapters[0]?.slug ?? ""}`}>{x.title}</Link>
        ))}
      </div>
      {b.parts.map((p) => {
        const here = p.chapters.some((c) => c.slug === slug);
        return (
          <details key={p.title} className="guide-part" open={here || undefined}>
            <summary>{p.title}</summary>
            <ol>
              {p.chapters.map((c) => (
                <li key={c.slug}>
                  <NavLink to={`/guide/${b.id}/${c.slug}`} aria-current={c.slug === slug ? "page" : undefined}>{c.title}</NavLink>
                </li>
              ))}
            </ol>
          </details>
        );
      })}
    </nav>
  );
}

function OnThisPage({ ch, active }: { ch: GuideChapter; active: string | null }) {
  const items = ch.headings.filter((h) => h.level === 2 || h.level === 3);
  if (!items.length) return null;
  return (
    <nav aria-label="På denne side">
      <p className="guide-toc-title">På denne side</p>
      <ul>
        {items.map((h) => (
          <li key={h.id} className={`l${h.level} ${active === h.id ? "on" : ""}`}><a href={`#${h.id}`}>{h.text}</a></li>
        ))}
      </ul>
    </nav>
  );
}

// ---------------- the chapter ----------------

type HastNode = { type: string; tagName?: string; value?: string; properties?: Record<string, unknown>; children?: HastNode[] };

/** A rehype step that gives h1–h4 the server's ids in document order, so links (#anker) and "På denne side"
 *  always agree with the server (one slug rule, in guide.py). */
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

function Markdown({ ch }: { ch: GuideChapter }) {
  const heading = (Tag: "h1" | "h2" | "h3" | "h4") => ({ id, children }: { id?: string; children?: ReactNode }) => (
    <Tag id={id}>{children}{id && Tag !== "h1" && <a className="anchor" href={`#${id}`} aria-label="Link til afsnittet">#</a>}</Tag>
  );
  const ids = useMemo(() => rehypeIds(ch.headings.map((h) => h.id)), [ch]);
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
      {ch.markdown}
    </ReactMarkdown>
  );
}

function useActiveHeading(ch: GuideChapter | undefined) {
  const [active, setActive] = useState<string | null>(null);
  useEffect(() => {
    if (!ch) return;
    const ids = ch.headings.filter((h) => h.level === 2 || h.level === 3).map((h) => h.id);
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
  }, [ch]);
  return active;
}

function Chapter({ tree }: { tree: GuideTree }) {
  const { book = "", slug = "" } = useParams();
  const { hash } = useLocation();
  const narrow = useNarrow();
  const q = useQuery({ queryKey: ["guide-chapter", book, slug], queryFn: () => api.guideChapter(book, slug), retry: false });
  const ch = q.data;
  useTitle(ch?.title ?? "Guide");
  const active = useActiveHeading(ch);

  useEffect(() => {      // a link with #anker lands on its heading once the text is there; otherwise the top
    if (!ch) return;
    const el = hash ? document.getElementById(decodeURIComponent(hash.slice(1))) : null;
    if (el) el.scrollIntoView();
    else window.scrollTo(0, 0);
  }, [ch, hash]);

  const nav = useMemo(() => <BookNav tree={tree} book={book} slug={slug} />, [tree, book, slug]);
  const body = q.isPending ? <div className="skeleton" style={{ height: 500 }} aria-busy="true" />
    : q.isError ? (
      <div className="error">{q.error instanceof ApiError && q.error.status === 404
        ? <>Kapitlet findes ikke. <Link to="/guide">Til oversigten</Link></>
        : <>Kapitlet kunne ikke hentes: {q.error.message}</>}</div>
    ) : (
      <article className="prose">
        <p className="guide-crumb small muted">
          <Link to="/guide">Guide</Link> › {ch!.book_title} › {ch!.part}
        </p>
        <Markdown ch={ch!} />
        <p className="small muted guide-updated">Senest ændret {ch!.updated}.</p>
        <nav className="guide-pager" aria-label="Forrige og næste kapitel">
          {ch!.prev ? <Link to={`/guide/${ch!.prev.book}/${ch!.prev.slug}`} className="prev"><span className="small muted">← Forrige</span>{ch!.prev.title}</Link> : <span />}
          {ch!.next ? <Link to={`/guide/${ch!.next.book}/${ch!.next.slug}`} className="next"><span className="small muted">Næste →</span>{ch!.next.title}</Link> : <span />}
        </nav>
      </article>
    );

  if (narrow) {
    return (
      <div className="guide narrow">
        <Search />
        <details className="guide-fold"><summary>Indhold</summary>{nav}</details>
        {ch && ch.headings.some((h) => h.level === 2) && (
          <details className="guide-fold"><summary>På siden</summary><OnThisPage ch={ch} active={active} /></details>
        )}
        {body}
      </div>
    );
  }
  return (
    <div className="guide">
      <aside className="guide-side"><Search />{nav}</aside>
      <main className="guide-main">{body}</main>
      <aside className="guide-toc">{ch && <OnThisPage ch={ch} active={active} />}</aside>
    </div>
  );
}

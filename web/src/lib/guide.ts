// The Danish books (guide/ in the repo, served by /api/guide): link handling, callouts and the app's links into them.
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export type HrefKind =
  | { kind: "guide"; to: string }      // another chapter: bog/slug#anker → /guide/bog/slug#anker
  | { kind: "app"; to: string }        // an app page: /regime
  | { kind: "anchor"; to: string }     // a heading in this chapter: #anker
  | { kind: "external"; to: string };  // anything with a scheme (https:, mailto:)

const BOOKS = ["brugervejledning", "laerebog"];

/** How a link written in a chapter should behave in the app. Pure, so it can be tested. */
export function classifyHref(href: string): HrefKind {
  if (/^[a-z][a-z0-9+.-]*:/i.test(href)) return { kind: "external", to: href };
  if (href.startsWith("#")) return { kind: "anchor", to: href };
  if (href.startsWith("/")) return { kind: "app", to: href };
  const clean = href.replace(/^\.\//, "");
  const book = clean.split("/")[0] ?? "";
  if (BOOKS.includes(book)) return { kind: "guide", to: `/guide/${clean}` };
  return { kind: "external", to: href };
}

export type Callout = "note" | "example" | "tip";

const CALLOUTS: Record<string, Callout> = { "bemærk": "note", "eksempel": "example", "tip": "tip" };

/** A blockquote that starts with **Bemærk:**, **Eksempel:** or **Tip:** is a coloured box. */
export function calloutKind(firstText: string): Callout | null {
  const m = /^\s*(bemærk|eksempel|tip)\s*:/i.exec(firstText);
  return m ? CALLOUTS[m[1]!.toLowerCase()] ?? null : null;
}

/** The chapter about the app page at `pathname` ("Om denne side"), from the manifest's page_links. */
export function pageChapter(pageLinks: Record<string, string>, pathname: string): string | null {
  if (pathname.startsWith("/guide")) return null;
  if (pageLinks[pathname]) return pageLinks[pathname]!;
  const prefix = Object.keys(pageLinks).filter((p) => p !== "/" && pathname.startsWith(`${p}/`))
    .sort((a, b) => b.length - a.length)[0];
  return prefix ? pageLinks[prefix]! : null;
}

/** The books' table of contents and link maps (they only change when the app is updated). */
export function useGuideTree() {
  return useQuery({ queryKey: ["guide-tree"], queryFn: api.guideTree, staleTime: Infinity, retry: false });
}

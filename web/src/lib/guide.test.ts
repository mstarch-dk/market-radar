import { describe, expect, it } from "vitest";
import { calloutKind, classifyHref, pageChapter } from "./guide";

describe("guide links", () => {
  it("routes chapter links into the guide, app links to the page, and the rest out", () => {
    expect(classifyHref("laerebog/rrg#rs-ratio")).toEqual({ kind: "guide", to: "/guide/laerebog/rrg#rs-ratio" });
    expect(classifyHref("./brugervejledning/regime")).toEqual({ kind: "guide", to: "/guide/brugervejledning/regime" });
    expect(classifyHref("/regime")).toEqual({ kind: "app", to: "/regime" });
    expect(classifyHref("#teori")).toEqual({ kind: "anchor", to: "#teori" });
    expect(classifyHref("https://skat.dk")).toEqual({ kind: "external", to: "https://skat.dk" });
    expect(classifyHref("mailto:a@b.c").kind).toBe("external");
  });

  it("finds the chapter about the current page, ticker pages included", () => {
    const links = { "/": "brugervejledning/navigation", "/regime": "brugervejledning/regime", "/ticker": "brugervejledning/tickerprofil" };
    expect(pageChapter(links, "/regime")).toBe("brugervejledning/regime");
    expect(pageChapter(links, "/ticker/NOVO-B.CO")).toBe("brugervejledning/tickerprofil");
    expect(pageChapter(links, "/")).toBe("brugervejledning/navigation");
    expect(pageChapter(links, "/unknown")).toBeNull();
    expect(pageChapter(links, "/guide/laerebog/rrg")).toBeNull();
  });

  it("turns Bemærk/Eksempel/Tip blockquotes into callouts", () => {
    expect(calloutKind("Bemærk: data er forsinket")).toBe("note");
    expect(calloutKind("  eksempel: 100 kr.")).toBe("example");
    expect(calloutKind("Tip: tryk /")).toBe("tip");
    expect(calloutKind("Et citat")).toBeNull();
  });
});

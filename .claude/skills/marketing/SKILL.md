---
name: marketing
description: Build or refresh the Danish marketing material for Market Radar (marketing/site/index.html and marketing/market-radar.pdf) with fresh screenshots from a demo copy of the app that holds only a fictional investor. Detects features added since the last edition and adds sections and shots for them. Use when the user asks for marketing material, a brochure, a feature overview or screenshots of the app, asks to update them after new features, or runs /marketing.
---

# Marketing material

Produce an up-to-date Danish brochure (HTML page and A4 PDF) that shows advanced Danish hobby investors what
Market Radar does, with screenshots of the real app running on real market data and a **fictional** portfolio.
Every run is a new *edition*: it starts from the last one (`marketing/edition.json`) and brings it up to date
with the app as it is now.

Everything lives in `marketing/`. All of it is committed except the screenshots (`site/img/`, local build output
rebuilt every run), so the repo holds only the latest PDF:
- `demo/seed.yaml`: the fictional investor (portfolios, trades, a virtual A/B fork, watchlist, market views)
- `shots.yaml`: every screenshot (page, element to crop to, actions, light/dark, desktop/mobile)
- `features.yaml`: the feature inventory: section in the page, routes, commands, shots
- `site/index.html`: the brochure's source (its images: `site/img/*.png`, gitignored); `market-radar.pdf`: the edition
- `edition.json`: what the last edition covered (commit, date, features, shots)

The tool is `scripts/marketing.py` (run it as `uv run --group marketing python scripts/marketing.py …`; in Git
Bash prefix commands that take app paths with `MSYS_NO_PATHCONV=1`). It drives the Microsoft Edge that is
installed on the machine through Playwright, so no browser download is needed.

## Ground rules
- **Never show real data.** The demo runs from `.demo/`, a copy of the working tree without `userdata/`,
  `notes/`, `imports/*` or anything else personal (publish/exclude.txt), with its own database. Never point a
  shot at port 8780 (the user's own app), never copy `userdata/` into `.demo/`, and never put a real holding,
  account or broker relationship into `seed.yaml`. `check` runs the leak check from `scripts/publish_public.py`
  over `marketing/` and confirms the demo database holds only the seed's portfolios.
- Facts come from the app, its config and docs. Every number in the text (indicator count, number of names,
  markets, positive-list year, thresholds, a reading quoted in a caption) is re-read for this edition from the
  demo (`.demo/reports/*.json`, the API on port 8790), `config/*.yaml` or the code. Never carry a number over
  from the last edition unchecked.
- Material is analysis-tool marketing, not investment advice. Keep "analyse, ikke rådgivning".

## Steps

1. **What changed since the last edition.**
   - Read `marketing/edition.json`, then `git log --oneline <commit>..HEAD` and
     `git diff --stat <commit> -- web/src/pages web/src/App.tsx docs .claude/skills src/radar/cli.py config`.
     Also look at uncommitted work (`git status`): the demo copies the working tree, so it shows that too.
   - Compare with `features.yaml`: list **new** features (a new page or route, a new card or table, a new
     command or skill), **changed** ones (new columns, filters, flags, a different method or threshold) and
     **removed** ones. Read the relevant docs (`docs/web-app.md` pages and endpoints, `docs/commands.md`) and
     the code for anything unclear: the brochure must describe what the feature really does.
   - Don't ask the user to confirm: add, update or remove features, shots and sections on your own, and
     report what you did at the end.
2. **The demo world.** Stop a running demo server first (`preview_stop`), because `workspace` rebuilds
   `.demo/`.
   - `scripts/marketing.py workspace`: copy, market data, `uv sync`, web build.
   - `preview_start` with `radar-demo` (port 8790; `.claude/launch.json`).
   - `scripts/marketing.py seed`: fills the database through the app's API, then runs `radar run` in
     `.demo/`.
   - If a new feature needs demo content to show anything (a new kind of row, a setting, a note), add it to
     `seed.yaml` (and to `seed()` if the API needs a new call). Rebuild from `workspace`, so the seed stays
     the only source.
   - A seed warning (for example negative cash) means the seed is wrong: fix the seed, don't ignore the
     warning.
3. **Explore** new or changed pages.
   - `scripts/marketing.py explore /path …` saves full-page captures to `.demo/explore/`; look at them with
     Read.
   - The built-in browser pane (tab from `preview_start`) is for reading the DOM to find locators:
     `read_page`, `find`, or `javascript_tool` listing headings with their parent's class.
   - Pick frames that show the feature with data in it: no empty states, no error banners, no welcome page.
   - Add or adjust entries in `shots.yaml`:
     - Crop to elements (`section.group` with a heading, `.card`, `.page-head` … `to:` …), never to pixels.
     - Use `edge: top` to stop at the next heading.
     - Use `{pf:NAME}` / `{forked:NAME}` for portfolio ids and dates.
   - Then link each new shot to its feature in `features.yaml`.
4. **Capture**: `scripts/marketing.py shots` (or `shots ID…` while iterating). Then **look at every new or
   changed image** with Read:
   - Data loaded: no spinners, no "–" where data should be.
   - No unintended stale banner.
   - The frame shows what the caption will claim.
   - Only demo names appear in personal tables.
   - A crop that cuts through a table or catches half of the next heading needs a better locator.
   - If a demo setting makes a column meaningless (for example a market view that matches every name in a
     region), change the seed.
5. **Write and update the text** in `marketing/site/index.html`.
   - Keep the structure: hero, purpose (*Formål og vision*), the numbered use cases (*Hovedanvendelser*),
     the feature grid (*Funktioner*), data sources and blind spots (*Datagrundlag*), strengths and limits
     (*Styrker og begrænsninger*), getting started (*Kom i gang*), and the footer.
   - Give a new feature a use case (`<div class="case" id="<section>">` with `.txt` and a figure) when it
     changes how someone works. Otherwise, a line in an existing case plus a cell in the feature grid.
   - Update the use-case count in the heading, the feature grid, *Styrker og begrænsninger* if a limit went
     away or a new one appeared, and the footer: the screenshot date, plus the demo portfolio's contents from
     `seed.yaml`.
   - Every `id` in `features.yaml` must exist in the page, and every shot must be used once.
6. **Build and check.**
   - Run `scripts/marketing.py pdf` and `scripts/marketing.py check`, and fix everything `check` reports.
   - Render the PDF pages and look at them, for example with
     `uv run --no-project --with pymupdf python -I <script>` into the scratchpad as a contact sheet.
   - Check for a figure split from its caption, a nearly empty page, or an image too small to read. Adjust
     the `@media print` rules (`break-before: page` per section) in index.html.
   - Then run `scripts/marketing.py edition --data-asof <the demo's data date>`.
7. **Report.**
   - Send the PDF with SendUserFile and list what changed in this edition: new or updated sections, new
     shots, removed ones, seed changes.
   - List anything in the app that looked wrong in the screenshots (a cropped table, a misaligned column).
     That is an app bug to raise, not to hide with a crop.
   - Stop the demo server. Don't commit unless asked.

## Writing in Danish
- **Audience:** experienced Danish hobby investors, with frie midler and an aktiesparekonto. They know what
  momentum, ETFs and a P/E are, and they want to see what the tool can be used for and how it works, not to be
  sold to.
- **Detailed and plain.** Per feature:
  - what it shows
  - how it is calculated (method, horizon, benchmark)
  - what you can use it for
  - where it stops (its limits)
  Prefer a concrete example from the screenshot to an adjective.
- **No hype.** Not: revolutionerende, unik, banebrydende, game-changer, garanteret, slå markedet, hemmelig,
  eksplosiv, "du kan ikke undvære", superlatives, exclamation marks. Momentum and scores are "et sted at starte
  research, ikke en købsliste".
- **App labels stay in English** as they appear in the app (*Since buy (DKK)*, *My market views*, *Scan
  again*), in italics, with a Danish explanation. The page says the interface is in English.
- **Danish context where it matters:** ASK 17 % lagerbeskatning vs frie midler, SKATs positivliste, UCITS
  alternatives with ISIN, DKK returns, import from Danish brokers. Check tax facts against what the app itself
  says (Themes page text, `docs/`) and don't add tax rules the app doesn't use.
- **Danish typography:** decimal comma in prose (0,33; 17 %), thousands with a dot (1.500), "ca.", en dash for
  ranges (1–6 måneder), curly quotes “…”.
- Captions: a bold label, then one or two sentences on what the picture shows and how to read it. Don't
  quote numbers that change every day unless the caption is about that reading, and then re-read it.

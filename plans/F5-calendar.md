# F5 Calendar: the coming weeks for what you own and watch: implementation plan

*Written 2026-10-25, from [the product owner review](analyses/product_owner.md) (feature F5, the calendar part),
against `main` at `eca4df8` (after the X-ray, F1). Analysis, not advice.*

## 1. Goal and non-goals

**Goal.** One place that answers *what's coming for my money in the next days and weeks, and which of it needs my
attention*. It is a calendar of the earnings dates (and ex-dividend dates) of the names you hold and watch, plus your
own review dates. Each item is highlighted by stated rules: how much of your money is at stake, how close the price is
to your review level, whether estimates are being cut, and whether the date is even confirmed. The same items reach
the monthly brief through `summary.json`. Nothing is a recommendation: the page says *what* and *why it's
highlighted*, never what to do.

User stories (MVP):

1. I open *Kalender* under *Mine* and see the next five weeks as an agenda grouped by week. Each held or watched
   stock's next earnings date shows as estimated or as a range, with the source and the date it was read. A month
   grid shows the same items.
2. At the top, *De næste 7 dage* lists the items that need attention, highest first. Each one gives its reasons: "5.2 %
   of your portfolio", "price 3 % above your review level", "EPS estimate cut 4 % in 30 days", "no set
   date: Yahoo expects 28 Oct–3 Nov".
3. Held names stand out from watched ones. I can filter by held, watched or both, and by kind (earnings,
   ex-dividend, my reviews), for one portfolio, a tag or all, with the usual picker.
4. A held stock with **no known date** is listed under *Ingen dato kendt*, never left out silently. A fund has no
   earnings: the page says how many funds it left out.
5. The holdings table on *Beholdninger & watchlist* gets an *earnings in N d* flag. On *Forsiden*, a *Snart* strip
   shows the high items of the next 7 days. Both use the same code as the page, so they never disagree.
6. My own dates appear too: journal entries' `review_by` and proposals' time stops (with the exit check's
   Intact/Weakening/Triggered status).
7. The monthly brief gets a *Kommende uger* section from `summary.json["calendar"]`.
8. The same data is available from the CLI: `uv run radar calendar [NAME…] [--tag T] [--days N] [--json]`.

**Non-goals for this plan** (to `plans/F5-feed.md` or later):

- The *change feed* ("since your last visit", events diffed between report builds, history-tier event log).
- Desktop notifications (OS-native, local only).
- The macro calendar (Fed/ECB/Nationalbanken meetings, FRED release dates). Tax deadlines (F3).
- Typical earnings move from past reports (needs past report dates; see open question 2).
- An `.ics` export for Outlook or Google Calendar (open question 3).
- Earnings for the whole momentum universe. The calendar is for *your* names; the profile page already covers any
  ticker.

## 2. Licence check

No new data source. Yahoo (via yfinance, already in `DATA_LICENSE.md`) is read the way the profile page reads it
(`t.calendar`, `eps_trend`, `eps_revisions` in `external.fetch_detail`). Only the *Used for* column changes: add
"calendar: earnings and dividend dates and estimate revisions of held and watched names" to the Yahoo row, in
`DATA_LICENSE.md` and `guide/brugervejledning/datalicenser.md`. Personal use only: the calendar is never exported to
an external service.

## 3. What the code does today (findings that shape the design)

| # | Finding | Where | Consequence |
|---|---|---|---|
| C1 | The weekly screener snapshot stores `earnings_date` as one local day from `earningsTimestamp`. It has no range and no time of day, and it isn't filtered for the past, so a date that has just passed can stand for up to a week | `sources/valuation.py:119-124`, `STOCKS_FILE` (history tier) | Use it only as a fallback, and only when the date is ≥ today. Label it "screener, week of …". |
| C2 | The per-ticker detail has Yahoo's calendar block (`Earnings Date` list, which can be a range, `Earnings High/Low/Average`, `Revenue …`, `Ex-Dividend Date`, `Dividend Date`). `parse_calendar` keeps only the first upcoming date and the averages | `sources/external.py:421, 575-583` | Extend `parse_calendar` to keep the range (`earnings_start`/`earnings_end`, `is_range = start != end`; neither form means the company has confirmed the date) and the high/low estimates. The profile keeps reading the same function, so it agrees with the calendar. |
| C3 | The detail is fetched only when a profile or `radar info` is opened (24 h cache, `CACHE/profiles/`). Nothing refreshes it for held or watched names | `external.detail`, `profile.py:256` | A new update step, `calendar`, refreshes the detail for held and watched stocks on a schedule (4.3). This also warms the profile cache. |
| C4 | The detail cache keeps only the latest copy, so a date that moves leaves no trace | `PROFILE_DIR` (cache tier) | Each refresh appends a dated row to a **history-tier** file (`history/calendar.parquet`). This detects *date moved*, and it is the first event source F5's feed will read. It can't be downloaded again later. |
| C5 | `held_or_watched()` (positions + watchlist overlay) is what `update_analyst` already uses | `universe.py:109`, `updater.py:100-107` | The step uses the same list, filtered to stocks (`quoteType` not ETF/fund). |
| C6 | `mine.table` rows carry `levels` (review/stop) and flags. `earnings_date` arrives in the row only through `dashboard.with_valuation` | `mine.py:100-208`, `api/holdings.py:33-52` | Reuse the levels for the *near your review level* reason. The *earnings in N d* flag is added from the calendar's resolved date, not from the snapshot. |
| C7 | The journal has `review_by` and `review_due`. Proposals have `time_stop` and `check_exits` (status per pick), CLI only | `notebook.py:32,86-90,101`; `propose/store.py:220-298` | Read both through their existing functions. They are cheap to add and are already part of F5's MVP in the review. |
| C8 | The brief skill reads `summary.json` but never uses `earnings_date`. The keys are a contract with the skills | `.claude/skills/market-brief/SKILL.md:20-35,92-98`; `reporting/report.py:36-77` | Add a `calendar` key and a *Kommende uger* step in the skill, in the same PR. |
| C9 | `calendar` is a stdlib module name | – | The feature module is `src/radar/agenda.py`, and the user-facing name is *Kalender*. |

## 4. Design

### 4.1 Modules, by layer

| Layer | Module | Change |
|---|---|---|
| sources | `sources/external.py` | `parse_calendar` keeps the range and the high/low estimates (C2). New `update_calendar(tickers, today)` (the schedule in 4.3) calls `detail(t, refresh=True)` for the tickers due and appends their parsed rows to `CALENDAR_FILE = HISTORY / "calendar.parquet"`. New `load_calendar()`. |
| domain/pure | `agenda.py` → `resolve_earnings(sym, detail_row, snapshot_row, today)` | The one place a "next earnings date" is decided. The order is detail (fetched within `stale_days`) → screener snapshot (≥ today) → none. It returns `{start, end, is_range, source, read_on, stale, moved_from}`. It is a pure function, unit tested. |
| features | `agenda.py` (new top-level module, like `xray.py`) | `build(selection, today, days)` produces the items (earnings, ex-dividend, journal reviews, proposal time stops) and the highlight rules (4.5). The *Snart* list, the *no date* list and the notes come from the same data. It has no I/O of its own: it reads the history file, the valuation context, `mine.table`, `notebook.listing` and `propose.store.check_exits`. |
| features | `api_models/agenda.py` | `AgendaView`, `AgendaItem`, `Reason` (`extra="forbid"`), re-exported by `api_models`. |
| interfaces | `api/agenda.py` | `GET /api/calendar`, a router included last in `api/app.py`. `/api/me` gets the *earnings in N d* flag from `agenda.next_earnings_map(...)`. |
| interfaces | `cli/portfolios.py` | `radar calendar` next to `radar xray`. |
| reporting | `reporting/report.py` | `summary["calendar"]` for the default selection (real portfolios + watchlist), `days = calendar.days`. |
| updater | `updater.py` | The `calendar` step in `update_external`, after `valuation_stocks` (it needs the snapshot's stock list and dates). |
| web | `web/src/pages/Calendar.tsx`, `components/AgendaList.tsx`, `components/MonthGrid.tsx`, `components/SoonStrip.tsx` | The page `/calendar` in *Mine* after *X-ray*. A *Snart* strip on Home. A flag badge on Me. |
| skills | `.claude/skills/market-brief/SKILL.md` | The *Kommende uger* step (4.7). |

Layers: add `agenda` to the features layer in `pyproject.toml` (import-linter). `agenda.py` may import `mine`,
`notebook`, `propose.store` (read-only function) and `sources`. Check that `propose.store` is reachable from the
features layer without a forbidden contract. If it isn't, expose `check_exits` through the `propose` facade, which is
what `cli/propose.py` uses.

### 4.2 Data model

`history/calendar.parquet` (tier **history**, `paths.REGISTRY`), append-only, one row per (ticker, fetched). Columns:

```text
ticker, fetched (date), earnings_start, earnings_end (date | null), eps_avg, eps_low, eps_high,
rev_avg, rev_low, rev_high, ex_dividend, dividend_date (date | null), eps_chg_30d, eps_up_30d, eps_down_30d,
source ("yahoo_detail")
```

- `eps_*_30d` come from the same detail (`parse_eps_trend`, period `0q`, the quarter being reported).
- A ticker with an empty calendar block still gets a row with nulls, so "Yahoo had no date on day X" is recorded
  too. A fetch that fails writes no row and keeps the previous ones (`guard` pattern). If *every* fetch fails, the
  step fails loudly.
- No `userstore` table: everything is derived. Read and dismissed state belongs to the feed (F5-feed), not here.

### 4.3 The update step and its schedule

`update_calendar(held_or_watched stocks)` refreshes a ticker when:

- it has no row yet, or
- its last row is older than `refresh.max_age_days`, or
- its next known date is within `refresh.near_days` and the row is older than `refresh.near_max_age_hours`, or
- its last known date is in the past (the report has happened, so the next date is wanted).

The tickers are fetched in parallel through `net.pool` like `update_analyst`, inside the per-host budget in
`network:`. Step 1 measures the request count: `fetch_detail` makes about six Yahoo calls per ticker. If 40 names
cost too much, a lean `fetch_calendar` (calendar + eps_trend + eps_revisions only) is the fallback, and the decision
is recorded in the PR.

### 4.4 Settings

```yaml
calendar:
  days: 35                 # the page's default window; also the brief's (the brief is monthly)
  soon_days: 7             # "De næste 7 dage" and the earnings-in-N-days flag
  stale_days: 10           # a detail row older than this is not used for the date (fallback to the snapshot)
  refresh: {max_age_days: 3, near_days: 14, near_max_age_hours: 20}
  include: {watchlist: true, ex_dividend: true, reviews: true}
  highlight:
    big_position: 0.05     # a holding at least this share of the selection's invested value
    near_level: 0.05       # price within this distance of the review/stop level (mine levels)
    revision_cut: -0.02    # EPS estimate for the quarter cut by at least this over 30 days
```

Every key goes in `config/settings.yaml` and `config_schema.py` (`Calendar`). The guide quotes them with
`{{settings:calendar.…}}`.

### 4.5 Method: the highlight rules

Each item gets **reasons**, and its **level** follows from them. The rules are fixed and stated. There is no score,
and no rule says "buy" or "sell".

| Reason (key) | Applies to | Rule | Source |
|---|---|---|---|
| `held` | earnings, ex-div | the name is in the selection's holdings | `mine.table` status |
| `big_position` | held earnings | weight ≥ `highlight.big_position` of invested value | `holdings_book` (`portfolios/exposure.py`) |
| `near_level` | held earnings | last price within `near_level` of the review or stop level, above or below | `mine` `levels` |
| `momentum_weak` | held earnings | the flag *losing momentum* or *below 200d* is set | `mine` flags |
| `estimates_cut` | earnings | `eps_chg_30d ≤ revision_cut`, or `down_30d > up_30d` | history row |
| `estimates_raised` | earnings | the mirror of `estimates_cut` (shown, never escalates) | history row |
| `unconfirmed` | earnings | `start != end` (a range) | history row |
| `moved` | earnings | the resolved date differs from the previous row's date | history rows |
| `stale_date` | earnings | the date comes from the snapshot fallback, or from a detail older than `stale_days` | `resolve_earnings` |
| `review_due` / `time_stop` | own dates | the journal `review_by` / proposal `time_stop` falls in the window. For a proposal pick, its exit status is attached | notebook, `check_exits` |

**Level:**

- `high`: held, within `soon_days`, with at least one of `big_position`, `near_level`, `momentum_weak`,
  `estimates_cut`. Also a proposal pick whose status is *Triggered*.
- `normal`: any other held earnings in the window, and own review dates.
- `info`: watched names, ex-dividend dates, `estimates_raised`.

Within a day, items sort by level, then weight. Each reason has a text with the number in it ("5.2% of the
portfolio"), built in `agenda.py` from the numbers so the web, CLI and brief show the same text. The texts are in
English like the rest of the app's interface; the brief, which is Danish, words them in Danish from the key and the
value.

**Truthfulness.**

- A range is shown as a range, never as its first day.
- No date known: the stock is listed in `no_date`, with the reason (no detail, empty Yahoo block, date passed and no
  new one).
- Funds are counted in `excluded_funds`.
- Every earnings item carries `source` and `read_on`.
- Days-until is computed against the `today` the request passes in (the report's `asof` in `summary.json`), so a
  rebuild on the same data gives the same items. F5-feed relies on this.

### 4.6 API and CLI

`GET /api/calendar?portfolio=&tag=&scope=&days=` → `AgendaView`:

```text
AgendaView
  asof, generated, today, days, selection: {ids, names, scope}
  items: [{id, kind (earnings|ex_dividend|review|time_stop), date, date_end | null, symbol | null, name,
           status (holding|watch|own), level (high|normal|info), weight | null,
           reasons: [{key, text, value | null}],
           earnings: {is_range, source, read_on, eps_avg, eps_low, eps_high, rev_avg, moved_from | null} | null,
           link}]                         # link: /ticker/X, /notebook/…, /experiments…
  soon: [item ids]                        # high items within soon_days, in order
  no_date: [{symbol, name, status, reason}]
  excluded_funds: int
  notes: [str]
```

- `id` is stable: `kind:symbol:date`. F5-feed will key its events on it.
- Computed live, like `/api/me`, cached per (selection, market mtime, calendar-file mtime, transactions version) with
  the `performance._cached` pattern. Without prices, it still answers (dates don't need prices) and leaves out
  `near_level` with a note.
- `pnpm -C web gen:api`, `client.ts` gets `calendar(sel, days)`.
- CLI: `uv run radar calendar [NAME…] [--tag T] [--scope …] [--days N] [--json]`. It prints *Next 7 days*, then a
  table per week (date, symbol, held/watch, level, reasons), then *no date known*. `--json` prints the `AgendaView`
  dict.

### 4.7 Integration with the market brief

- `summary.json["calendar"]` = `AgendaView` for the default selection with `days = calendar.days`, minus
  `selection`. The docstring's contract list in `report.py` gets the key.
- `/market-brief` SKILL.md, in *Din portefølje i den sammenhæng*: a new step **Kommende uger**:
  - List the `high` items first, then the other held earnings, each with its reasons as given. Don't invent new
    reasons.
  - Put watched names in one line.
  - For each `high` earnings item, research on the web what the market is watching (consensus, guidance, the last
    quarter's surprise) and cite the sources.
  - Say "no date known" for `no_date` holdings.
  - Never recommend acting before a report. The caveat says that stop levels don't protect against an overnight gap.
- The `/research` and `/propose-portfolio` skills currently read the next date via `radar info`. They can switch to
  `radar calendar --json` (one line each, same PR) so all skills agree.

### 4.8 Web

- **`/calendar`**, label *Kalender*, blurb "Det der sker for dine navne de næste uger", in *Mine* after *X-ray*.
  Selection in the URL as `?pf=`, with `PortfolioPicker`. Layout:
  1. **De næste 7 dage**: cards for the `soon` items (level colour via `Badge`, reasons as chips, `TickerLink`).
     When the list is empty: "Intet der kræver opmærksomhed de næste 7 dage". Empty never means "no data": the
     `no_date` count shows next to it.
  2. **Tabs `Agenda | Måned`** (`useTabParam`).
     - *Agenda*: grouped by ISO week, with a `DataTable` row per item and filters for held/watched/both and for kind.
     - *Måned*: `MonthGrid`, a plain CSS grid (no new dependency) with dots per item, coloured by level. A range
       spans its days, drawn lighter.
  3. **Ingen dato kendt** and the excluded-fund count.
  4. **Noter** and the guide link (`page_links`).
- **Me**: the `earnings in N d` flag, which the existing flag rendering shows.
- **Home**: `SoonStrip`, the `high` items of the next `soon_days` for the default selection (one request, hidden when
  empty).
- Terms (`Term`, `lib/glossary.ts`): *bekræftet dato*, *estimatrevision*, *gennemgangsniveau* (already there),
  linking to the textbook.

## 5. Steps as PRs

Each PR is green on `uv run pytest -q`, `uv run ruff check`, `uv run mypy`, `uv run lint-imports`, and carries its
guide changes.

| # | PR | Contents | Behaviour change |
|---|---|---|---|
| 1 | **Calendar data** | `parse_calendar` range + high/low (profile unchanged in what it shows, plus "range" when there is one). `update_calendar`, `load_calendar`, `CALENDAR_FILE` in `paths.REGISTRY` (history). The `calendar` updater step. Settings `calendar.refresh` / `stale_days`. A request-count measurement noted in the PR. `DATA_LICENSE.md` + `datalicenser.md` *Used for*. `data-og-daekning.md` (the new step). | New update step and history file |
| 2 | **`agenda.py` core** | `resolve_earnings`, the item builders (earnings, ex-div, review, time stop), highlight rules and levels, reason texts. All settings in 4.4. Pure functions tested on the synthetic world. | None visible |
| 3 | **API, CLI, flag** | `api_models/agenda.py`, `api/agenda.py`, `radar calendar`, the `earnings in N d` flag in `/api/me`. `pyproject.toml` layers. `docs/web-app.md`, `docs/commands.md`, `CLAUDE.md` main commands. `beholdninger.md` *Flagene*. | New endpoint, command, flag |
| 4 | **Brief integration** | `summary["calendar"]`, the contract docstring, the `market-brief` SKILL.md step. The `research` / `propose-portfolio` skills read `radar calendar --json`. `maanedsbrief.md` (what the brief now includes). | `summary.json` gains a key |
| 5 | **Web page** | `Calendar.tsx`, `AgendaList`, `MonthGrid`, nav, `main.tsx` route, client, glossary, `page_links`. New chapter `guide/brugervejledning/kalender.md` in `guide.yaml` (*Dig og dine penge*, after *xray*). `navigation.md` (Mine row). Textbook (section 8). | New page |
| 6 | **Home strip** | `SoonStrip` on Home. `navigation.md` *Forsiden*. | Home shows a strip |
| 7 | **Release** | `CHANGELOG.md`, *Nyheder*, marketing `features.yaml` entry. Screenshots in the demo copy. | – |

Dependencies: 2 needs 1 (history columns). 3 and 4 need 2 and are independent of each other. 5 needs 3. 6 needs 5's
components. 7 comes last.

## 6. Backlog

Ready to be copied into issues. Each task names its PR (step), its dependencies, its size (S ≤ ½ day, M ≤ 2 days) and
its acceptance criterion.

| ID | Task | PR | Deps | Size | Done when |
|---|---|---|---|---|---|
| F5-01 | Extend `parse_calendar` with range, high/low estimates, `is_range` | 1 | – | S | `test_parse_calendar_range` passes. The profile shows a range when Yahoo gives two dates. |
| F5-02 | `CALENDAR_FILE` + `paths.REGISTRY` entry (history), `load_calendar` | 1 | – | S | `test_registry` covers the file. Layout docs list it. |
| F5-03 | `update_calendar` with the refresh schedule, parallel fetch, guard | 1 | F5-01, F5-02 | M | `test_calendar_schedule`, `test_calendar_append_only`, `test_calendar_all_fail_loud` |
| F5-04 | Updater step after `valuation_stocks`; settings `calendar.refresh`, `stale_days` (yaml + schema) | 1 | F5-03 | S | `radar run` on the test world writes rows. Settings test passes. |
| F5-05 | Measure Yahoo requests for held+watched; decide `detail` vs lean fetch; record in PR | 1 | F5-04 | S | The number and the decision are in the PR description. |
| F5-06 | Licence *Used for* rows; `data-og-daekning.md` | 1 | – | S | `test_guide.py` passes. |
| F5-07 | `resolve_earnings` (detail → snapshot ≥ today → none, `moved_from`) | 2 | F5-03 | S | `test_resolve_earnings_order`, `test_snapshot_past_date_ignored` |
| F5-08 | Item builders: earnings, ex-div, journal `review_by`, proposal `time_stop` + exit status | 2 | F5-07 | M | `test_agenda_items_kinds`, funds counted in `excluded_funds` |
| F5-09 | Highlight rules, levels, reason texts (English, as the app); settings `calendar.highlight`, `days`, `soon_days`, `include` | 2 | F5-08 | M | `test_highlight_rules` (one case per reason), `test_levels` |
| F5-10 | `no_date` list with reasons; notes | 2 | F5-08 | S | `test_no_date_listed_never_dropped` |
| F5-11 | `AgendaView` models, `/api/calendar`, cache key, no-prices behaviour; `gen:api` | 3 | F5-09 | M | `test_calendar_api_contract`, `test_calendar_without_prices` |
| F5-12 | `radar calendar` CLI (tables, `--json`) | 3 | F5-09 | S | `test_cli_calendar` |
| F5-13 | `earnings in N d` flag in `/api/me` from `agenda.next_earnings_map` | 3 | F5-07 | S | `test_me_flag_matches_calendar` |
| F5-14 | Docs: `web-app.md`, `commands.md`, `CLAUDE.md`, `beholdninger.md` *Flagene*; layers in `pyproject.toml` | 3 | F5-11 | S | `lint-imports`, `test_layers.py`, `test_guide.py` pass |
| F5-15 | `summary["calendar"]` + contract docstring | 4 | F5-09 | S | `test_summary_calendar_key`, `test_summary_deterministic` |
| F5-16 | `market-brief` SKILL.md *Kommende uger*; `research`/`propose-portfolio` read `radar calendar --json`; `maanedsbrief.md` | 4 | F5-15, F5-12 | S | A dry-run brief on the demo copy has the section with the given reasons. |
| F5-17 | `Calendar.tsx`: picker, *De næste 7 dage*, Agenda tab with filters, *Ingen dato kendt* | 5 | F5-11 | M | `pnpm -C web test` (`nav.test.ts` includes `/calendar`), `pnpm -C web build` |
| F5-18 | `MonthGrid` component (CSS grid, ranges drawn lighter) | 5 | F5-17 | M | Component test: a range spans its days; levels coloured. |
| F5-19 | Nav, route, `page_links`, glossary terms | 5 | F5-17 | S | `test_guide.py` page-link test passes. |
| F5-20 | Guide chapter `kalender.md`, `navigation.md`; textbook sections | 5 | F5-17 | M | `test_guide.py` passes; `{{settings:…}}` used for every threshold. |
| F5-21 | `SoonStrip` on Home; `navigation.md` *Forsiden* | 6 | F5-17 | S | Hidden when empty; same items as the page's `soon`. |
| F5-22 | Release: `CHANGELOG.md`, *Nyheder*, `features.yaml`, demo-copy screenshots | 7 | all | S | Definition of done (section 9) ticked. |

## 7. Tests

| Test | File | Checks |
|---|---|---|
| `test_parse_calendar_range` | `tests/test_external.py` | Two dates → start/end, `is_range=True`. One date → `is_range=False`. Past dates dropped. High/low kept. |
| `test_calendar_schedule` | `tests/test_external.py` | Who is due: no row, older than `max_age_days`, near date and older than `near_max_age_hours`, last date passed. |
| `test_calendar_append_only` | same | A refresh adds rows and never rewrites old ones. A failed fetch writes nothing. |
| `test_calendar_all_fail_loud` | same | Every fetch fails → the step raises, and the file is unchanged. |
| `test_resolve_earnings_order` | `tests/test_agenda.py` | The detail wins. A stale detail falls back to the snapshot. A snapshot date in the past → none, with reason. `moved_from` is set when the date changed. |
| `test_agenda_items_kinds` | same | Earnings, ex-dividend, journal review, proposal time stop each appear with the right `kind`, `status`, `link`. Funds are counted, not listed. |
| `test_highlight_rules` | same | One case per reason key in 4.5 at the threshold and just past it. |
| `test_levels` | same | Held + soon + escalator → high. Held without escalator → normal. Watched → info even with `estimates_cut`. Triggered time stop → high. |
| `test_no_date_listed_never_dropped` | same | A held stock with no date is in `no_date`, never in `items` with a guessed date. |
| `test_summary_deterministic` | `tests/test_report.py` | Two builds on the same data → the same `calendar` key (dates against `asof`, not the clock). |
| `test_summary_calendar_key` | same | The key is present, validates against `AgendaView`, and holds the default selection. |
| `test_calendar_api_contract` | `tests/test_api.py` | `GET /api/calendar` validates. An empty selection → 200 with notes. |
| `test_calendar_without_prices` | same | No prices → 200, no `near_level` reasons, a note. |
| `test_me_flag_matches_calendar` | `tests/test_api.py` | The `/api/me` flag's N equals the calendar's days-until for the same symbol. |
| `test_cli_calendar` | `tests/test_cli_smoke.py` | `radar calendar --json` prints valid JSON on the test world. |
| layers | `tests/test_layers.py`, `lint-imports` | `agenda` is in features. Nothing below imports it. |
| web | `pnpm -C web test` | Nav has `/calendar`. `MonthGrid` range rendering. The reason-chip formatting. |

The synthetic world (`docs/testing.md`) gets a calendar fixture: a held stock with a range, one with a single
date, one with no date, one watched, one fund, a journal entry with `review_by`, and a frozen proposal with a time
stop.

## 8. Docs

- **User guide**:
  - New chapter `brugervejledning/kalender.md` (*Kalender*): what is on the page, where the dates come from and how
    sure they are (range vs one date, read on, the fallback), the highlight rules with their thresholds via
    `{{settings:calendar.highlight.big_position|pct}}` etc., *Ingen dato kendt*, the CLI.
  - Linked from `navigation.md` (Mine row, *Forsiden*), `beholdninger.md` (*Flagene*) and `maanedsbrief.md`.
  - `indstillinger.md` covers the `calendar:` keys.
- **Textbook**:
  - `estimatrevisioner.md`: why revisions into a report matter, post-earnings drift (PEAD) as context, and why the
    page shows revisions but doesn't vote with them.
  - `stop-og-storrelse.md` (or the chapter on stops): a report can gap through a stop. Position size and how close
    the price is to the level are what you control.
- **Developer docs**: `docs/architecture.md` (`agenda.py` in features, the history file), `docs/commands.md`,
  `docs/web-app.md`, `CLAUDE.md` main commands (one line).
- **Data licence**: *Used for* (section 2).
- **Release**: `CHANGELOG.md`, *Nyheder*. Run `uv run pytest -q tests/test_guide.py`.

## 9. Definition of done

The review's cross-cutting checklist ([section 3.3](analyses/product_owner.md#33-cross-cutting-definition-of-done-applies-to-every-feature)),
applied:

- [ ] Source code in `sources/external.py`, the feature in `agenda.py`. `lint-imports` and `tests/test_layers.py`
      pass.
- [ ] A missing date is listed as missing with a reason. A range is never collapsed to a day. A past snapshot date
      is never shown as upcoming. A step where every fetch fails is loud and keeps the file.
- [ ] `history/calendar.parquet` is in `paths.REGISTRY` as history, append-only. Nothing is written to the repo.
- [ ] No new `userstore` table.
- [ ] Settings are in `settings.yaml` and `config_schema.py`. The guide quotes them with `{{settings:…}}`.
- [ ] `AgendaView` is strict. TypeScript types are regenerated. `pnpm -C web build` passes.
- [ ] `DATA_LICENSE.md` and `datalicenser.md` *Used for* are updated. The request budget is measured and within
      `network:`.
- [ ] `summary.json["calendar"]` is added together with the skill change. The output is deterministic for a given
      `asof`.
- [ ] Guide and textbook per section 8. `tests/test_guide.py` passes.
- [ ] `uv run pytest -q`, `uv run ruff check`, `uv run mypy`, `pnpm -C web test` are green.
- [ ] `CHANGELOG.md`, *Nyheder*, marketing `features.yaml`. Screenshots come from the demo copy, never the user's
      data folder.

## 10. Decisions taken here, and open questions

**Decided:**

- **Held and watched, both.** Watched names are `info` level and can be filtered out, so the attention list stays
  about your money.
- **A page of its own** (`/calendar`) in *Mine*, plus the Me flag and the Home strip as the in-app "notification".
  Desktop notifications wait for F5-feed, off by default as the review says.
- **Shaped for F5-feed:**
  - stable item ids;
  - dates against `asof`, not the clock;
  - a history file of observed dates, so *date moved* and *date announced* become feed events without a new source.
- **The brief gets the data in `summary.json`.** It is not left to web search. Web research is only for *what to
  watch* in a high item.

**Open:**

1. Should the screener snapshot also keep the time of day (`earningsTimestamp`: before open / after close) as a
   new nullable column in `stocks.parquet` (append-only schema change)? It tells you whether the reaction lands the
   same day or the next. Suggest: yes, as a small task in step 1, if the screener gives it for non-US names too.
2. A *typical earnings move* per name (median absolute DKK return vs ACWI over the day after the last 8 reports)
   needs past report dates. yfinance `get_earnings_dates` gives about 12 past quarters with EPS surprise, but it
   scrapes a different Yahoo page (fragility and terms to check). The alternative is to build it from this plan's own
   history file as it accrues (slow, about two years to be useful). Suggest: a follow-up plan after a terms check.
3. An `.ics` file (`radar calendar --ics` into `exports/`, personal tier) that Outlook or Google Calendar can import.
   It is useful, but it puts holdings into a calendar that may sync to a cloud service, so it would be opt-in with a
   warning. Suggest: wait until the user asks.
4. ETFs: show the earnings of an ETF's top holdings (the look-through) for a large held fund? Suggest: not in this
   plan. The X-ray's look-through is by weight, not by event.

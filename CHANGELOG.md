# Changelog

What changed in each release, newest first. The user-facing version, in Danish, is the guide chapter *Nyheder*
(`guide/brugervejledning/nyheder.md`). `scripts/release.py prepare X.Y.Z` refuses to bump the version until both
have a `## X.Y.Z` section; the release workflow uses this file's section as the release notes.

## Unreleased

- **/scout: hypotheses from what the market talks about.** A new Claude skill searches the web through fixed lenses
  (flows and ETF launches, fund-manager surveys, policy and public money, capex and supply chains, outlooks,
  regulatory and technology milestones, emerging and frontier markets, commodities, a contrarian lens). It checks
  each story against the radar's numbers (`ticker_profile`, rotation, revisions, positioning, the user's views) and
  writes `research/scout/YYYY-MM-DD.md` with 3–5 candidates. Each has a narrative stage (whisper / confirming /
  consensus: "buy on the rumour, sell on the fact"), a seven-axis rubric, a red team and a falsifier. The user
  adopts, watches or dismisses each; the run can be logged in the journal.
  - New MCP write `add_view` (dry run with the view's evidence and the views it overlaps or contradicts, saved only
    with `confirm`). New column `views.origin` (`scout:<date>:<slug>`), set once and kept through edits; the
    *Market views* page tags such views *from scout*. View validation now also checks the horizon, exposures and
    indicator directions for every writer.
  - Forward record: `scout.py` freezes every shortlisted candidate (adopted, watched and dismissed: the control
    group) in `exports/scout/`, dated today, never overwritten, and its tickers join the daily update.
    `evidence.scout_review` follows each proxy basket against ACWI, with means per decision and per stage from
    `evidence.scout_min` candidates. MCP `scout_freeze` / `scout_review`, CLI `radar scout review`, and a *Scout
    candidates* table on the Evidence page. `propose.store._basket_path` is now the public `basket_path`.
  - The notebook has a `scout` kind (Notebook → Research → *Scout reports*), and journal entries a `type` field
    (`hypothesis`: no ticker). `/market-brief` adds a scout line; `/journal review` checks open hypotheses
    (catalyst arrived, falsifier triggered, basket vs ACWI).
  - Guide: a new chapter *Scout: hypoteser fra markedets snak* and a textbook chapter *Rygter, opmærksomhed og
    fortællinger*. The open web, searched by Claude, is listed in `DATA_LICENSE.md` (links and own summaries only).

- **Danish index funds are looked through in the X-ray.** Yahoo lists Danish investment funds
  (investeringsforeninger) as stocks with no sector and no fund data, so they showed as `unknown`. The new
  `config/index_funds.yaml` maps 26 listed Danish index equity funds (Danske Invest, Sparindex, Nordea Invest,
  BankInvest, Sydinvest) to the index each tracks, from the providers' factsheets and reports. An index is a list
  of countries, and the fund is counted as ACWI's holdings in them (the iShares ACWI file the X-ray already
  reads), re-weighted to 1. No new data source.
  - New class `index_fund` in `exposure.ticker_meta`, with region and currency weights next to the sector
    weights; `exposures` spreads every dimension. A share class hedged to DKK (`hedged: DKK`) counts as DKK under
    currency, with the index's sectors and regions.
  - Attribution spreads index funds by their index's sector, region and currency mix.
  - Index funds count as diversified (`exposure.diversified`): the per-name cap rule doesn't apply to them, and
    the concentration card's world-fund weight includes them.
  - The X-ray notes say what each held index fund is counted as, and the index's caveat (large and mid caps only;
    India, Brazil and Saudi Arabia missing from emerging markets). Small-cap, style, minimum-volatility, sector
    and theme index funds are left out on purpose: a country slice would misstate them.

## 0.4.0

The radar as tools for Claude, your own trading rules, a tax estimate, a calendar, and live progress for the
data update wherever it runs. (The version after 0.2.0; there is no 0.3.0.)

- **Follow an update live, wherever it runs.** The data update now reports which step of how many runs (prices,
  names and sectors, FRED, the 16 other sources, the report), the phase within it (done of total), and each
  problem the moment it is known: a source that failed (its cached data kept), tickers without data or without the
  last session, tickers Yahoo answered without closes. New `progress.py`; the update's steps are planned up front.
  - The price download names its phases (new, known, re-based and late tickers) and counts each to the end
    (before, it reported 0 of N before each batch and never reached N). The slow per-stock steps (Yahoo's
    screener and lookups, SEC EDGAR, Yahoo statements, names and sectors) count too.
  - A running job writes its progress and log to the operations log as it goes (`ops.Live`, the new `job_live`
    table in ops.db; at most every two seconds, a new step or issue at once, a sign of life every 30 s). So the
    app sees an update the MCP server or a terminal runs, and Claude sees one the app or a terminal runs.
  - Operations page: *Running now* at the top, for any process's job: step and phase bar, problems so far, every
    step's outcome, requests and errors so far, the log tail and *not responding* after three minutes without a
    sign of life. A finished job's log shows its steps and problems. `GET /api/ops/running`.
  - *Update data* panel: the step and its phase, problems as they happen, the steps, and an update started in a
    terminal or by Claude, read-only (`elsewhere`; starting another is refused with 409).
  - `radar run` / `update` print `[4/20] CFTC positioning…`, a long step's progress every five seconds and each
    problem as it happens (stderr).
  - MCP `job_status`: `step`, `steps`, `issues`, `issues_total`, `paused_hosts`, and an update another process
    runs. `/market-brief` now posts a short line on each check while the update runs, says at once what a failed
    source means for the brief, and sums up the problems when it is done.
  - A new server no longer marks the MCP server's running update as interrupted (it has a recent sign of life).

- **X-ray: no longer fails when a holding has no fund data date.** With pandas 3 a missing `detail_asof` became NaN
  instead of None and `/api/xray` answered 500 for any book mixing a fund with stocks.
- **Pointing a new version at an existing data folder backs it up first.** `radar setup --use` and the setup
  screen's *use this folder* recorded the new version before the first-start backup, so an older version's data
  wasn't backed up before the new version changed it. The release's upgrade test caught it.
- **XDWD.DE (Xtrackers MSCI World) counts as a broad world fund** (`risk.world_funds`): the X-ray spreads it with
  ACWI's weights, and the per-name cap in the trading rules leaves it out, like the other funds on that list.

- **My trading rules (F12).** Write down the rules you want to trade by and check an action against them: a mirror,
  never a gate (nothing is blocked or sent anywhere). New page *Trading rules* under *Mine*, `radar rules`, and the
  tables `trading_rules` and `rule_checks` in radar.db (an append-only migration).
  - Typed kinds with parameters from `config/rules.yaml` (caps per name and per theme / sector / region in the
    market views' exposure vocabulary, a core floor, a minimum trade size, a maximum number of names, a buy-back
    pause, sell cooling-off, trades per month, no averaging down, a moving-average filter, no chasing a 3-month
    run-up, a minimum momentum score, account placement by horizon, exit rule first) plus free-text *judgment*
    rules. Each has a scope (portfolios, account kind, tag, style), a severity (hard / soft / reminder: a label
    only) and a rationale. Generic templates to start from.
  - *Test an action* (`radar rules check`, `POST /api/rules/check`): one verdict per rule (breaks, near, unknown,
    complies, doesn't apply, ask yourself) with the numbers and how to comply (the largest amount under a cap,
    the first day a buy-back is allowed, when a cooling-off window clears). Weights say what they are a share of;
    unknown never counts as complying. Checked as of the action's day.
  - Standing breaches without an action: the page's *Breaks right now*, a *breaks a rule* / *near a rule* flag on
    the holdings table (`rule_flags` on `/api/me`), and `summary.json["rules"]` for the monthly brief.
  - The Portfolio editor (and `radar portfolio add`, the `add_trade` tool) shows a new trade's rule breaks as
    warnings to confirm, and logs the check with your reason when you go ahead.
  - *Would my rules have helped?* (`radar rules replay`): today's rules on your past real trades, each point in
    time, with what the name did afterwards vs ACWI. Descriptive, small-n, no significance claimed.
  - Skills: new `/rules`; `/journal` checks an action and records a *Rules* section and `style:`;
    `/propose-portfolio` keeps to the caps; `/market-brief` lists the standing breaks. MCP tools `trading_rules`,
    `rules_check`, `add_rule`, `rule_decision`.
  - The holdings bundle and `radar export` carry `rules.json`. The cap per name leaves out the broad world funds
    (`risk.world_funds`).

- **The radar as tools for Claude (MCP server).** `uv run radar mcp` serves the radar over stdio to the Claude
  client that starts it (Claude Code starts it from the committed `.mcp.json`; approve it once, `/mcp` shows it).
  No port, no new data source, and `radar serve` needn't run. Every tool returns what the matching `--json`
  command prints, with `null` for missing values; readings from the report carry `asof`, `age_days` and `stale`.
  - Readings: data folder, investor notes, market views, the summary in sections, the discovery scan cut to the
    off-radar rows a brief reads, study ages, the notebook (briefs, research, proposals, journal), portfolios,
    returns vs ACWI, X-ray, attribution, the calendar (by symbol), the Evidence page (by section), one or several
    tickers' profiles.
  - Jobs: start and follow an update, a rebuild of the readings or a study. They run like the app's, show on the
    *Operations* page, and check the same locks, so a job already running in the app or a terminal is refused,
    not started twice.
  - Engines: a basket proposal from shortlist to frozen picks (structured input, no hand-written picks file),
    evaluation, shadow portfolios, review and exit check; the hindsight basket (`radar sim picks`, run as a child
    process).
  - Two narrow writes: `write_memo` (only the notebook's folders, atomic, never over a document unless asked) and
    `add_trade` (checked like the app; saves nothing without `confirm`).
  - Tool annotations say which tools only read, which may replace a file and which reach the network.
- **The skills use the tools.** `/research`, `/compare`, `/journal`, `/market-brief`, `/propose-portfolio` and
  `/hindsight` prefer the `mcp__radar__*` tools and keep one line of CLI fallback (for a client without them). Measured
  on one data folder: `/research` reads about 66 % less, `/compare` 22–32 % less and `/market-brief` 28 % less than
  the CLI versions (`plans/mcp_server.md`, section 7). New guide chapter *Claude og radarens værktøjer*.
- **Cash flow from the latest fiscal year**: when a company's cash-flow items (operating cash flow, capex,
  dividends paid, buybacks, issuance) have no last-twelve-months figure within `fundamentals.ttm_max_age_days`
  (Yahoo has only full-year cash flow statements for many non-US companies), the latest fiscal year within
  `annual_max_age_days` is used, with a note on the card. FCF then comes wholly from that year and the FCF margin
  uses that year's revenue. Shareholder yield and the FCF metrics no longer drop out for such companies
  (e.g. SAN.MC, BBVA.MC, BARC.L) for half of each year.
- **Positions in DKK**: the *Positions* table on *Portfolio* (and on *Experiments*) has a *Value (DKK)* column, each
  position's value at its last traded close converted at the DKK rate on that close's day, so it sorts by size
  across currencies. It shows "–" when the price or rate is missing; `/api/portfolio/positions` gains `value_dkk`.
- **Tax estimate** (a *Tax* tab on *Portfolio*): the Danish tax your own records imply for an income year, an
  estimate and not tax advice. Each aktiesparekonto and pension account is one pool (lager on the whole return,
  negative tax carried forward); each tax person's frie midler accounts are taken together for share income
  (realised gains by the average-cost method in DKK at each trade's rate, dividends, lager on positive-list funds,
  listed-share losses offset and carried, the progression limit) and capital income (lager on funds off the list,
  taxed only at a rate you give). Values are at traded closes in DKK; each fund is classified from its ISIN on
  that income year's positive-list sheet, so an ETF that leaves the list changes tax that year. A holding the radar
  can't classify is named with its value and left out, never guessed; a missing value is missing, never 0.
  - Rates and limits per year in the new `config/tax_dk.yaml` (2025 and 2026, from skat.dk), each with its source
    and the day it was checked. A year without verified rules shows the amounts and no tax.
  - New inputs in `radar.db` (schema step): tax persons and who owns each account ("Me" owns them all at first),
    each holding's ISIN and class (filled from your imports, `universe.yaml` and the discovery map; yours wins),
    losses carried in from before your history. In the export and the holdings bundle as `tax.json`.
  - `radar tax year|classify|isin|person|opening` and `GET /api/tax` with edit endpoints.
  - Losses carried in are the årsopgørelse's figures and replace the radar's own chain from their year (0 allowed:
    nothing carried; a schema step rebuilds `tax_openings`, every row kept). A history that starts before the
    rules (trades from a year without rules) otherwise left every later year without tax.
  - Dividends are unknown, not 0, when the prices show an ex-dividend day on a share you held and no dividend is
    booked; capital income is unknown while a holding has no class. A negative capital base notes that its
    deduction isn't in the estimate. `radar tax classify` lists only what the real accounts traded.
  - The positive list is read per income year for the estimate; the ETF pages' flag still uses the latest sheet.
- **The proposals' ASK deposit check follows skat.dk**: the cap less the account's value on 31 December the year
  before and this year's deposits, with the cap from `config/tax_dk.yaml`. The settings `propose.ask_deposit_cap`
  and `propose.ask_cap_year` are gone (a settings.yaml that still has them fails on start and names them).
- **Run the studies from the Evidence page.** Every study card and rule study now has a button: *Run the study*
  when there is no report, *Run again* when it tested an older rule or has old data. The app runs the study's own
  command (the one on the card) in the background as a child process, shows how long it has run and its log, and
  can cancel it. One study at a time, shared with `radar study …` in a terminal (a new `study.lock`; a second run
  stops with "Not started"), and never during an update or a rebuild. `GET`/`POST`/`DELETE /api/studies/run`.
- **The local app refuses changing requests from other sites.** A POST, PUT or DELETE whose `Host` or `Origin`
  isn't this computer gets 403, so a web page open in the browser can't start an update or a study (or reach the
  app through DNS rebinding). The app's own pages and the CLI are unaffected.
- `python -m radar` runs the command line, like `radar`.

- **Calendar** (`/calendar`, under *Mine* after *X-ray*): the coming 35 days for what you hold and
  watch. Earnings and ex-dividend dates of held and watched stocks, your open journal reviews and your proposals'
  time stops, each with the reasons it is highlighted by stated rules (`calendar.highlight`: position size, price
  near the review level, fading momentum, estimate cuts; how sure the date is) and a level (high, normal, info).
  Yahoo's expected window is shown as a window, never as its first day; a stock with no known date is listed with
  the reason, and funds are counted. Agenda by week and a month grid, held/watched and kind filters, any portfolio
  selection. Days count from the last close, so the same data gives the same calendar.
  - The dates come from a new update step that reads Yahoo's calendar for held and watched stocks every
    `calendar.refresh.max_age_days` days (daily near a report) into `history/calendar.parquet` (history, kept
    across versions), so a moved date is seen. About 8 Yahoo requests per name read.
  - Home gets a *Soon* strip, *Holdings & watchlist* an `earnings in N d` flag; both are the same calendar.
  - `radar calendar [NAME…] [--tag T] [--days N] [--json]` and `GET /api/calendar`.
  - `summary.json` gains `calendar`, and the monthly brief a *Kommende uger* step from it; `/research` and
    `/propose-portfolio` read a held or watched name's next report from `radar calendar --json`.
  - New settings: `calendar:` (window, soon days, highlight thresholds, refresh schedule, what to include).

- **Held funds are classified honestly in proposals' exposure tables.** A fund is looked through (a world fund
  with ACWI's weights, a sector fund with its sector, another fund with the sector weights in its cached Yahoo
  data) or shown as *fund: not looked through*. It is never filed under the region of its exchange or the
  currency it is quoted in: an S&P 500 fund listed in London used to count as Europe. Each dimension now
  reports its coverage, and only real sectors, regions and currencies count as active weight vs ACWI. A fund's
  Yahoo data is read from the cache only; a fund you haven't opened a profile for shows as *unknown* until you do.
- **A proposal's risk figures no longer depend on its candidates.** Each set of holdings (your portfolio today,
  the basket, the portfolio after it, every alternative) is modelled on the covariance of its own names and ACWI,
  so the same holdings always get the same volatility, beta and tracking error, in proposals and the portfolio
  X-ray. Before, one covariance was shrunk over the holdings and some 60 candidates, which moved beta and
  tracking error with the candidate list; volatility barely changes.
- **Regions match ACWI's**: stocks listed outside the radar's four regions (Toronto, Sydney, São Paulo …) are
  `other`, as in ACWI's holdings file, not `us` (Canada) or `asia` (Australia).
- **Settings moved** from `propose:` to `risk:` (values unchanged): `history_weeks`, `min_weeks` (for the
  covariance) and `shrink` are now `risk.covariance`, `look_through` is `risk.world_funds` and `stress` is
  `risk.stress`. A settings.yaml with the old keys fails on start and names them. `propose.min_weeks` stays, for
  the bootstrap. New: `risk.xray`.

## 0.2.0

Your data now lives apart from the program, so a new version never touches it.

- **A data folder of its own**: `~/Market Radar` by default (Windows, macOS, Linux) holds `radar.db`, your
  notes, briefs, research, journal, exports, broker files and the history the radar builds up. Downloaded market
  data and the dashboard go to the OS cache folder and can be deleted at any time. `radar paths` lists every
  location; the Data page shows them under *Your data*.
- **First start: moving your data.** The app finds an earlier version's data in its own folder or in a folder
  next to it and copies it into the data folder (checked file by file and row by row; the old folder only gets a
  `MOVED.txt`). Or `uv run radar setup`. Every later version finds the data folder by itself.
- **Backups**: automatic once a day and before a new version first uses your data, on demand, with restore
  (what is there is backed up first) and an optional second folder (cloud sync or USB). `radar backup`,
  `radar backups`, `radar restore`.
- **Export** in open formats (CSV, JSON, Markdown, with a description of every file) and loading one back on
  another computer: the Data page, `radar export`, `radar import-export`.
- **Safer updates**: data written by a newer version opens read-only in an older one; `radar --version`; an
  opt-in daily check for a new release (`radar updates --on`, needs `updates.repo` in settings.yaml).
- **Portfolio page reorganised**: only your accounts (real portfolios), with an account strip and tabs
  (*Positions*, *Transactions*, *Imports*, *Accounts*; `?tab=`); the trade form opens above the transactions table.
- **Experiments page** (`/experiments`) for virtual portfolios: the A/B test card, a list with returns vs ACWI, and
  one experiment's holdings, trades, rebalances and returns. `GET /api/portfolios/{id}/runs` lists a sim's runs.
- **Fee schedules** per account (`portfolios.fee_schedule`, `fees.py`, presets for Saxo and Danske Bank in
  `config/fee_presets.yaml`): the trade form prefills the fee with an estimate (`fee_estimate` from validate).
- **Simulations pay the account's fees**: `radar sim exits` charges each rule and parking trade what the account's
  schedule says (minimum, maximum and the FX surcharge on non-DKK trades, as the sim books Yahoo's mid rate), else
  `backtest.fee_bps`; a buy the minimum would eat stays cash. A fork takes over its source's schedule. Each run's
  params record the fee model (`fee_model`). Opening holdings with `--start` are copied without a fee.
- Ticker lookup in the trade form: keyboard navigation, the tracked badge and the chosen name under the field.
- **Kvalitetsscore and værdiscore** beside the momentum score, from the companies' financial statements:
  - **Statements**: SEC EDGAR for US companies (with filing dates) and Yahoo's statements for every tracked
    stock, in one fact store (`fundamentals/`). Fetched a few at a time in the daily update, or
    `radar fundamentals update --all`. EDGAR needs a contact e-mail (Data page, `radar fundamentals contact`).
  - **Two scores, 0–100**, each against the sector's peers across regions:
    - Quality: FCF margin, ROIC, margin and revenue steadiness, net debt / EBITDA, interest cover, dividend record.
    - Value: FCF yield, EBIT / EV, shareholder yield, today's price against the company's own history.
    - K+V is their mean. Banks and insurers have their own set.
    - Missing figures are never 0.
  - **In the app**:
    - a new *Quality & value* page (Markets)
    - *Quality* and *Value* columns on Momentum and Holdings & watchlist
    - a *Quality & value* card on the ticker page
  - **Forward A/B test** (`radar abtest start`, or the button on the Quality & value page): three virtual baskets
    (K+V, momentum, 50/50), picked once a month and frozen, against ACWI and each other.
  - **Point-in-time study**: `radar study score --signal quality|value|qv` tests the scores at every past
    month-end on US stocks, from the facts filed by then.
  - **summary.json**: `quality_top10`, `quality_new_entrants`, `quality_coverage`, `quality` / `value` / `qv` on
    the momentum and holdings rows, and `abtest`.
  - **Skills**:
    - `/research` gets a quality and value section from `radar info`, no longer looking up FCF yield on the web.
    - `/compare` adds the scores to its rubric.
    - `/market-brief` covers the K+V leaders, their overlap with momentum and the A/B test.
    - `/hindsight` can pick a K+V basket (`radar sim picks-candidates --fund`).
- **Rebuild the readings without downloading.** `dashboard.json` records the files it was built from and its
  format. When one has changed since (a terminal `radar update` without `report`, a fundamentals run, an edited
  `settings.yaml`), the market pages show a *Rebuild the readings* banner (also on the Data page; `POST
  /api/report`). A dashboard built by an older version is rebuilt when the app starts, instead of answering 503.
  One build at a time across the app and a terminal (`report.lock`).
- **The score's rule over decades** (`radar study longrun`, `backtest/longrun.py`, `factors.py`): the momentum
  score's rule on long monthly histories without survivorship bias: 49 US industries since 1926 (Kenneth R. French
  Data Library) and 23 developed-market countries since 1986 (JKP Global Factor Data), with the variants of
  lookbacks and weights judged by `radar study score`'s rule, splits by decade, market trend and US recession,
  the base rates of the momentum, value and quality factors (losing windows, drawdowns, the last ten years) and a
  rough gauge of `radar study score`'s survivorship bias against `propose.survivorship_haircut`
  (`reports/longrun-study.json`). The histories are fetched monthly in `radar update` (`factors/returns.parquet`
  in the cache; `factors` in settings.yaml); FRED adds `DEXDNUS` and `USREC` (`macro.fred_study`).
- **Proposals weigh in the long run** (`propose.study_view`, `longrun.tilt_prior`, `propose.prior`): the rule
  study's excess is cut by the survivorship haircut (the configured one, or `radar study longrun`'s gauge when it
  implies more: `haircut_from_gauge`) and shrunk toward the tilt's long-run prior by precision (normal-normal
  update, extra prior uncertainty `tau_annual`): JKP's survivorship-free tercile portfolios of the same
  characteristics (12-1 and 6-1 momentum, FCF yield, EBITDA/EV, net payout, QMJ) in developed markets since
  2008, in today's ACWI trend when that split has enough periods; ex US and US shown beside it. `evaluate` flags
  K+V picks outside the US (`untested_kv`). The skills (`/propose-portfolio`, `/hindsight`, `/compare`) quote
  the long-run evidence. The prior is model, not rule: it doesn't make `propose-study.json` stale.
- **One kernel for the app and the studies** (`src/radar/model/`): the momentum score's percentile rule
  (`model/score.py`), the point-in-time panels and the ranked universe (`model/panels.py`), the caps
  (`model/select.py`) and the trend exit (`model/paths.py`) are defined once. My holdings, profiles, the Momentum
  and Discover pages, the regime, the A/B test, the proposals and every study call them, so what the studies
  test is what the app shows. `radar run`, the API, the A/B test and live proposals no longer import
  `radar.backtest`.
  - The momentum score is the share of names strictly below everywhere (was pandas' `rank(pct=True)` on the
    Momentum and Discover pages, the regime and the A/B test): the same order, but a region's strongest name
    now gets 100 x (N-1)/N and its weakest 0 (on a 40-name list about 2.5 points lower than before). A stock
    alone in its Discover market has no score.
  - The trend exit in `radar propose review` never triggers on the buy day, as in `radar study propose`.
- **Study reports as contracts** (`model/artifacts.py`): the study reports the proposals read
  (`propose-study.json`, `longrun-study.json`, `score-study.json`, `exit-study.json`, `redeploy-study.json`) start
  with a header (`schema_version`, `kind`, `created`, `data_asof`, `rule_hash`) and are checked against a model
  when written and read. One loader says `ok`, `stale`, `missing` or `invalid` with the reason: a proposal now
  says why an unreadable rule study gives no drift, and why the haircut fell back to the configured one
  (`haircut.gauge_note`). Reports written before keep working. The long-run prior moved to `model/prior.py`, so
  `radar.propose` never imports `radar.backtest`. `longrun-study.json`'s last month per dataset is now
  `datasets_asof` (`data_asof` is the header's date).
- **Layers checked on every test run** (`uv run lint-imports`, `tests/test_layers.py`, CI): import-linter
  contracts in `pyproject.toml` keep the kernel free of the studies and the app, the studies (`radar.backtest`)
  free of the report builder (`dashboard`, `mine`, `profile`) and the app, and the app free of the studies. The
  point-in-time replay reads which tickers get levels and which regime groups vote from `model/inputs.py`;
  `Market` moved to `market.py` and `region_for` to `universe.py` (the old names still work). A `slow` pytest
  marker (deselected like `network`; `uv run pytest -m slow`) holds the long-run study tests. Nothing in the app
  changes: `radar sim exits` on real data gives the same report.
- **Ten years of prices** (`history_years: 10`, was 6): `radar study score` gets about twice the month-ends and
  the 2020 Covid crash. The first update after upgrading downloads every price history again.
- **Portfolio proposals** (`/propose-portfolio <portfolio> <amount>`, `radar propose …`, `propose.py`): a
  fee-aware basket of new stocks for one portfolio (momentum, value or a mix; at least
  `propose.min_ticket_dkk` per name), picked by a pre-registered proposal score under caps on the portfolio after
  the addition (sector, region and currency vs ACWI's own weights, correlation, position size), frozen before the
  numbers are seen, and evaluated against ACWI, the rule-only basket, other tilts, the basket-size frontier,
  topping up, sector ETFs and random baskets. The expected excess comes only from the rule study (`radar study
  propose` → `reports/propose-study.json`); the drawdown three ways (study, vol-scaled block bootstrap, stress
  windows); a decision rule fixed beforehand. Exit criteria per pick, re-checked by `radar propose check` (used by
  `/journal review` and `/market-brief`); `radar propose shadow` / `review` track proposals against ACWI.
- New source: iShares MSCI ACWI UCITS holdings (ACWI's sector, region and currency weights), cached monthly.
- The Notebook lists proposals; guide placeholders show large numbers with Danish thousands (10.000).
- Linux start script `start-market-radar.sh`.
- Proposals read the regime with your current choice of voting groups, like the start page and profiles
  (before, the label `summary.json` had at the last `radar report`); `radar info A B` shows it the same way.
- Study reports (`reports/*-study.json`, `sim-exits*.json`, `sim-picks/`) and every `--json` output write a
  missing number as `null`, never `NaN` (which isn't JSON, and slipped past the readers' checks into a proposal's
  drift); a missing date is `null`, not `"NaT"`.
- `config/settings.yaml` is checked when it is loaded (the `stops`, `backtest`, `risk` and `propose` sections):
  a misspelt, missing or wrongly typed key fails at once naming the key, and `radar doctor` reports it under
  *Settings*, instead of a KeyError deep in a study or a proposal.
- The command line's progress lines go to stderr, so a command's `--json` output is valid JSON even when it logs
  (it wasn't for `radar sim exits --json` with a price-history note, or a study logging its progress).
- `radar portfolios add/edit` and the app check a portfolio the same way (kind, mode, dividend policy, a
  simulation stays virtual); `cli.py` is a package of command groups, each command tested.
- `radar report` checks every dashboard section, and each ticker profile, against the models the app reads before
  writing it: a shape the app can't show fails the build naming the field, instead of an error page later. A
  frozen proposal file is checked on freeze and when `review` / `check` read it.
- **The repository is public** (github.com/mstarch-dk/market-radar). `scripts/leak_check.py` replaces the old
  export script: it checks the working tree, a commit range or the whole history for personal strings and runs
  as a pre-push hook. The release and smoke workflows live in `.github/workflows/` with CI. The opt-in check
  for a new version points at the public repo. Test fixtures hold no prose from paid sources (DATA_LICENSE.md,
  *Test fixtures*).

What you need to do: start 0.2.0 and choose where your data goes (the app suggests the folder and finds the
old data). Afterwards you can delete the old program folder.

## 0.1.0

The first release.

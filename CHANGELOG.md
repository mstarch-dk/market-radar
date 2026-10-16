# Changelog

What changed in each release, newest first. The user-facing version, in Danish, is the guide chapter *Nyheder*
(`guide/brugervejledning/nyheder.md`). `scripts/release.py prepare X.Y.Z` refuses to bump the version until both
have a `## X.Y.Z` section; the release workflow uses this file's section as the release notes.

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

What you need to do: start 0.2.0 and choose where your data goes (the app suggests the folder and finds the
old data). Afterwards you can delete the old program folder.

## 0.1.0

The first release.

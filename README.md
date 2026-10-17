# Market Radar

A personal investing dashboard for a Danish investor. It runs on your own computer, from free public data, and
helps you spot:

- **The market regime:** risk-on or risk-off, from about 17 indicators (trend, breadth, volatility, credit,
  rates, earnings revisions).
- **Rotation:** which sectors, regions and themes are leading or lagging, on a rotation graph.
- **Momentum leaders:** the strongest stocks in the US, Europe, the Nordics and Asia.
- **Your own holdings and watchlist:** returns in DKK compared with simply owning the world index, mechanical
  stop/target levels, and warning signs.
- **Any ticker in depth:** price chart, technicals, risk, analyst estimates, valuation and peers.

**See it before you install:** the [brochure (PDF, in Danish)](marketing/market-radar.pdf) shows each page of
the app in screenshots, taken from a demo copy that holds only a fictional investor.

> **Not investment advice.** Market Radar is an analysis tool. The data comes from free sources (mostly Yahoo
> Finance) without any guarantee. Check anything important before you act on it.
>
> **Personal use only.** The code is MIT-licensed, but the market data it downloads is not: most of it may only
> be used for your own, non-commercial purposes. Don't host Market Radar for others or share the downloaded data.
> See [DATA_LICENSE.md](DATA_LICENSE.md) for what's allowed, source by source.

## About this project

Market Radar is the public version of a market analysis framework by Martin Starch. It asks of every idea:
is it better than simply owning the world index (MSCI ACWI)? Each copy runs on its owner's computer and
downloads its own data. What's in it:

- **The analysis engine** (`src/radar/`): data from more than fifteen sources (prices, rates, credit, earnings
  revisions, sentiment, positioning, fund holdings, financial statements), paced, cached and failing loudly
  (missing data is shown as missing, never as zero). On top of that come sector, region and theme rotation,
  momentum leaders per region, a risk-on/risk-off regime model, and returns in DKK per portfolio (TWR and MWR)
  against ACWI.
- **Studies that test the method**: the momentum score at every past month-end (information coefficient,
  quintiles, a holdout, random baskets), an exit rule tested point in time, decades of factor history, and
  fee-aware basket proposals checked against ACWI and the alternatives.
- **The app** (`web/`, React + TypeScript), served locally by FastAPI with types generated from the API models.
- **Claude Code skills** (`.claude/skills/`) for market briefs, research memos, comparisons, a decision journal
  and basket proposals, built on the radar's own data.
- **A Danish user guide and textbook** (`guide/`), shown in the app, on the methods and their limits.
- **Tests** with a synthetic market whose answers are known in advance, upgrade tests for every earlier
  release's data folder, and CI on Windows, macOS and Linux.

Much of it was written together with Claude (Anthropic's AI).

---

## Get started (Windows, Mac or Linux)

You don't need to install anything yourself. The start script sets everything up the first time.

1. **Download** the latest `market-radar-….zip` from the [Releases page](../../releases/latest) (under *Assets*).
2. **Unzip** it somewhere you'll keep it, for example `Documents\Market Radar`. Don't run it from inside the zip.
3. **Start it:**
   - **Windows:** double-click **`Start Market Radar.cmd`**. If Windows shows "Windows protected your PC",
     click *More info* → *Run anyway* (the script is plain text; you can open it in Notepad to see what it does).
   - **Mac:** right-click (or Control-click) **`Start Market Radar.command`** → *Open* → *Open*. This is only
     needed the first time; afterwards a double-click is enough.
   - **Linux:** run `./start-market-radar.sh` in a terminal.
4. A black window opens and prepares everything. The first time this takes a few minutes: it downloads
   [uv](https://docs.astral.sh/uv/), the small tool that runs Market Radar, and the Python it needs. Your browser
   then opens Market Radar at <http://127.0.0.1:8780>.
5. **Choose where your data goes.** The first start shows a setup screen. Your own data gets a folder of its own,
   outside the program folder (`~/Market Radar` by default). If you used an older version, it finds that folder
   and offers *Copy my data*; otherwise click *Start with an empty folder*.
6. **Click "Download market data".** The first download covers about 700 stocks and ETFs and takes **a few
   minutes** (about one to five, depending on your connection). You can watch the progress, and it's fine to look around meanwhile.

**Keep the black window open** while you use Market Radar. Closing it stops the app. Next time, just
double-click the start script again.

## Everyday use

- **Update data:** on the *Data & coverage* page, click *Update data* (or click the button in the yellow banner
  that appears when the data is a week old). Updates take a minute or two.
- **Your portfolio:** on the *Portfolio* page, add your trades one by one (the price of that day is filled in
  for you), or import them (the *Imports* tab) from your broker (Saxo, Nordnet, Danske Bank), Yahoo Finance or any spreadsheet. The
  import shows every row before anything is saved and can be undone. Positions, average cost (fees included) and
  your return vs the world index follow from the trades. Mark each trade's account (e.g. aktiesparekonto or frie
  midler) to see positions per account.
- **Watchlist:** click ☆ next to any ticker, or *Add to watchlist* on a ticker's page.
- **Look up anything:** type a company or Yahoo symbol in the search box (press `/` to jump there). Nordic and
  European symbols have a suffix, e.g. `NOVO-B.CO`, `RHM.DE`, `ASML.AS`.
- **Hover** over a column heading or a coloured label to see what it means. Green leans favourable, orange to
  red is a warning, grey is neutral.

## Your data stays yours

Everything you add stays on your computer and is never uploaded anywhere. It lives apart from the program, so a
new version never touches it:

| Where | What | Re-downloadable? |
|---|---|---|
| **Data folder**, `~/Market Radar` by default (Windows: `C:\Users\<you>\Market Radar`) | `radar.db` (portfolios, trades, market views, watchlist, choices), `notes/` (incl. your investor profile), `briefs/`, `research/`, `journal/`, `exports/`, `imports/` (broker files), `history/` (what the radar builds up over time: rank snapshots, valuation snapshots, analyst targets), `backups/` | **No**: back it up |
| **Cache folder**: `%LOCALAPPDATA%\MarketRadar\Cache` (Windows), `~/Library/Caches/MarketRadar` (Mac), `~/.cache/MarketRadar` (Linux) | Downloaded market data, the operations log and the built dashboard (`reports/`) | Yes: delete it any time |

The computer remembers where the data folder is (in `location.json` under `%LOCALAPPDATA%\MarketRadar`,
`~/Library/Application Support/MarketRadar` or `~/.config/MarketRadar`), so every version you unzip finds it.
`uv run radar paths` lists every location; the *Data & coverage* page shows them under *Your data*.

Keep the data folder out of OneDrive, iCloud Drive and Dropbox (a database synced while in use can be damaged);
send the backups there instead. The full story, in Danish, is in the app's guide: *Dine data, backup og opdatering*.

### Updating to a new version

Download the new zip, unzip it anywhere and start it. It finds your data folder, backs it up and opens; then
delete the old program folder. Nothing to copy. On a Mac, the right-click → *Open* step is needed again for each
newly downloaded `.command`. To go back, unzip the previous version: if the newer one changed the data format, the
older one opens your data read-only, and you can restore the backup taken just before the upgrade.

Coming from a version before the data folder (0.1.x)? The first start of the new version shows a setup screen that
finds the old folder (unzip the new version next to it), copies your data across and checks the copy. The old
folder isn't changed. Command line: `uv run radar setup`.

### Backups and export

- **Backups** are taken by themselves once a day and before a new version first uses your data (7 daily, 5 weekly
  and 12 monthly kept). Each is a zip of `radar.db`, your folders and the history, never the market data. On the
  *Data & coverage* page: *Back up now*, *Restore…* (what is there now is backed up first, so a restore can be
  undone), and a second folder every backup is copied to, such as a cloud-sync folder or a USB disk.
  Command line: `radar backup [--mirror PATH|off]`, `radar backups`, `radar restore FILE`.
- **Export** (*Export my data (CSV, JSON, Markdown)*, or `radar export`) writes everything of yours in open formats:
  `transactions.csv`, `portfolios.json`, `views.json`, your Markdown documents and an `EXPORT.md` explaining every
  column. `radar import-export FILE` reads one back.

### Moving to a new computer

Close the app, copy the whole data folder to the new computer, unzip Market Radar there and run
`uv run radar setup --use "PATH/TO/Market Radar"`. Then start the app and update the market data. (An export
works too, but leaves the history behind.)

## Optional: Claude Code skills

If you use [Claude Code](https://claude.com/claude-code), open this folder in it and you get commands that use the
radar's data:

| Command | What you get |
|---|---|
| `/market-brief` | A dated brief: what changed in regime, rotation and momentum, why (web research), and what it means for your holdings |
| `/research NOVO-B.CO` | A research memo on one stock or ETF: thesis, momentum context, valuation, risks, what would prove it wrong |
| `/compare NVDA AMD MU` | An honest side-by-side, including whether any of them beats just owning the world index |
| `/journal buy RHM.DE …` / `/journal review` | A decision journal with exit rules, and a monthly review of open decisions |
| `/propose-portfolio ASK 50000` | A fee-aware basket of new stocks for one of your portfolios (momentum, value or a mix), tested against ACWI and the alternatives, with an expected drawdown and exit criteria per pick |

First copy `investor.example.md` to `notes/investor.md` in your data folder and fill it in (your accounts, e.g.
aktiesparekonto and frie midler, your horizon and limits), so the skills fit you. The skills find the data folder
with `uv run radar paths --json` and write their files there; Claude Code may ask permission to use it, since it is
outside the project folder.

## Troubleshooting

- **The browser didn't open:** go to <http://127.0.0.1:8780> yourself while the black window is open.
- **"Market Radar is already running":** it's open in another window. Just use the browser tab.
- **Something failed in the black window:** the window runs a check (`radar doctor`) and says what's wrong and
  how to fix it. You can also run it yourself (see below).
- **Some tickers have no data:** Yahoo Finance sometimes misses a ticker for a day. The *Data & coverage* page
  lists them, and the next update usually fixes it.
- **Firewall or antivirus questions:** Market Radar only talks to its data sources (Yahoo Finance, FRED, the
  OECD, the CFTC, the ECB, FactSet, SSGA, iShares, Cboe, AAII, multpl.com and NYU Stern; the full list is in
  [DATA_LICENSE.md](DATA_LICENSE.md)), and to api.github.com only if you switch on the check for new versions. The
  app itself is only reachable from your own computer.
- **Mac: "cannot be opened because it is from an unidentified developer":** right-click the file → *Open* (see
  step 3).
- **"Your data folder can't be found":** the drive it is on isn't connected, or you moved it. Connect it and
  reload, or type where it is now and click *Use this folder* (`uv run radar setup --use PATH`).
- **"Read-only" banner:** your data was written by a newer Market Radar. Start the newest version you have.
- **Start over with market data:** close the app, delete the cache folder (`uv run radar paths` shows where) and
  download the market data again. Your data folder is kept.

## For the technically curious

- Python (managed by [uv](https://docs.astral.sh/uv/)) computes everything; a React app in `web/` shows it.
- Common commands, run in this folder:
  - `uv run radar run` (update and rebuild)
  - `uv run radar serve --open` (the app)
  - `uv run radar info NOVO-B.CO` (one ticker as JSON)
  - `uv run radar doctor` (setup check)
  - `uv run radar paths` (where your data is) and `uv run radar --version`
- Building from source needs Node 22+ and pnpm: `pnpm -C web install && pnpm -C web build`.
- Developer docs are in [`docs/`](docs/) (commands, architecture, data conventions, testing, web app). Tests:
  `uv run pytest -q` and `pnpm -C web test`.

## License

The code: [MIT](LICENSE). Use, change and share freely; no warranty.

The market data the app downloads is **not** MIT-licensed. It belongs to its sources, and most of it is for
personal, non-commercial use only: no hosting for others, no commercial use, no redistribution. Read
[DATA_LICENSE.md](DATA_LICENSE.md) before you share anything beyond the code.

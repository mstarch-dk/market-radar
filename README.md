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

> **Not investment advice.** Market Radar is an analysis tool. The data comes from free sources (mostly Yahoo
> Finance) without any guarantee. Check anything important before you act on it.
>
> **Personal use only.** The code is MIT-licensed, but the market data it downloads is not: most of it may only
> be used for your own, non-commercial purposes. Don't host Market Radar for others or share the downloaded data.
> See [DATA_LICENSE.md](DATA_LICENSE.md) for what's allowed, source by source.

---

## Get started (Windows or Mac)

You don't need to install anything yourself. The start script sets everything up the first time.

1. **Download** the latest `market-radar-….zip` from the [Releases page](../../releases/latest) (under *Assets*).
2. **Unzip** it somewhere you'll keep it, for example `Documents\Market Radar`. Don't run it from inside the zip.
3. **Start it:**
   - **Windows:** double-click **`Start Market Radar.cmd`**. If Windows shows "Windows protected your PC",
     click *More info* → *Run anyway* (the script is plain text; you can open it in Notepad to see what it does).
   - **Mac:** right-click (or Control-click) **`Start Market Radar.command`** → *Open* → *Open*. This is only
     needed the first time; afterwards a double-click is enough.
4. A black window opens and prepares everything. The first time this takes a few minutes: it downloads
   [uv](https://docs.astral.sh/uv/), the small tool that runs Market Radar, and the Python it needs. Your browser
   then opens Market Radar at <http://127.0.0.1:8780>.
5. **Click "Download market data".** The first download covers about 700 stocks and ETFs and takes **a few
   minutes** (about one to five, depending on your connection). You can watch the progress, and it's fine to look around meanwhile.

**Keep the black window open** while you use Market Radar. Closing it stops the app. Next time, just
double-click the start script again.

## Everyday use

- **Update data:** on the *Data & coverage* page, click *Update data* (or click the button in the yellow banner
  that appears when the data is a week old). Updates take a minute or two.
- **Your portfolio:** on the *Portfolio* page, add your trades one by one (the price of that day is filled in
  for you), or *Import…* them from your broker (Saxo, Nordnet, Danske Bank), Yahoo Finance or any spreadsheet. The
  import shows every row before anything is saved and can be undone. Positions, average cost (fees included) and
  your return vs the world index follow from the trades. Mark each trade's account (e.g. aktiesparekonto or frie
  midler) to see positions per account.
- **Watchlist:** click ☆ next to any ticker, or *Add to watchlist* on a ticker's page.
- **Look up anything:** type a company or Yahoo symbol in the search box (press `/` to jump there). Nordic and
  European symbols have a suffix, e.g. `NOVO-B.CO`, `RHM.DE`, `ASML.AS`.
- **Hover** over a column heading or a coloured label to see what it means. Green leans favourable, orange to
  red is a warning, grey is neutral.

## Your data stays yours

Everything you add stays in these folders on your computer and is never uploaded anywhere:

| Folder | What |
|---|---|
| `userdata/` | Your trades, accounts, watchlist changes (and automatic backups in `userdata/backups/`) |
| `imports/` | Old Yahoo import files (moved into `userdata/` automatically) |
| `data/`, `reports/` | Downloaded market data and the dashboard (can be re-downloaded) |
| `notes/` | Your own notes and investor profile (for the Claude skills) |
| `briefs/`, `research/`, `journal/` | What the Claude skills write for you |

Updating Market Radar to a newer release: unzip the new version and copy these folders across.

## Optional: Claude Code skills

If you use [Claude Code](https://claude.com/claude-code), open this folder in it and you get four commands that
use the radar's data:

| Command | What you get |
|---|---|
| `/market-brief` | A dated brief: what changed in regime, rotation and momentum, why (web research), and what it means for your holdings |
| `/research NOVO-B.CO` | A research memo on one stock or ETF: thesis, momentum context, valuation, risks, what would prove it wrong |
| `/compare NVDA AMD MU` | An honest side-by-side, including whether any of them beats just owning the world index |
| `/journal buy RHM.DE …` / `/journal review` | A decision journal with exit rules, and a monthly review of open decisions |

First copy `investor.example.md` to `notes/investor.md` and fill it in (your accounts, e.g. aktiesparekonto and
frie midler, your horizon and limits), so the skills fit you.

## Troubleshooting

- **The browser didn't open:** go to <http://127.0.0.1:8780> yourself while the black window is open.
- **"Market Radar is already running":** it's open in another window. Just use the browser tab.
- **Something failed in the black window:** the window runs a check (`radar doctor`) and says what's wrong and
  how to fix it. You can also run it yourself (see below).
- **Some tickers have no data:** Yahoo Finance sometimes misses a ticker for a day. The *Data & coverage* page
  lists them, and the next update usually fixes it.
- **Firewall or antivirus questions:** Market Radar only talks to its data sources (Yahoo Finance, FRED, the
  OECD, the CFTC, the ECB, FactSet, SSGA, iShares, Cboe, AAII, multpl.com and NYU Stern; the full list is in
  [DATA_LICENSE.md](DATA_LICENSE.md)). The app itself is only reachable from your own computer.
- **Mac: "cannot be opened because it is from an unidentified developer":** right-click the file → *Open* (see
  step 3).
- **Start over:** delete the `data/` and `reports/` folders and download the market data again. Your portfolio
  and watchlist are kept.

## For the technically curious

- Python (managed by [uv](https://docs.astral.sh/uv/)) computes everything; a React app in `web/` shows it.
- Common commands, run in this folder:
  - `uv run radar run` (update and rebuild)
  - `uv run radar serve --open` (the app)
  - `uv run radar info NOVO-B.CO` (one ticker as JSON)
  - `uv run radar doctor` (setup check)
- Building from source needs Node 22+ and pnpm: `pnpm -C web install && pnpm -C web build`.
- Developer docs are in [`docs/`](docs/) (commands, architecture, data conventions, testing, web app). Tests:
  `uv run pytest -q` and `pnpm -C web test`.

## License

The code: [MIT](LICENSE). Use, change and share freely; no warranty.

The market data the app downloads is **not** MIT-licensed. It belongs to its sources, and most of it is for
personal, non-commercial use only: no hosting for others, no commercial use, no redistribution. Read
[DATA_LICENSE.md](DATA_LICENSE.md) before you share anything beyond the code.

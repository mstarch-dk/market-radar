# Data sources and their terms

Market Radar's **code** is MIT-licensed ([LICENSE](LICENSE)). The **market data** it downloads is not covered
by that licence. It belongs to the sources listed below, each with its own terms, and most of it is only free
for **personal, non-commercial use**.

This is a plain-language summary to help you stay within those terms. It is not legal advice, and the sources
can change their terms at any time: the source's own terms always win.

## The short version

**Allowed:**

- Running Market Radar on your own computer, for your own investing, analysis and learning.
- Sharing the **code** (forking, changing, redistributing it under the MIT licence).
- Showing a screenshot or quoting a few numbers privately, e.g. to a friend or in a private note.
- Writing your own conclusions (briefs, research memos, journal entries) based on what the radar shows.

**Not allowed without a separate data licence:**

- **Hosting Market Radar as a website or service for other people.** That serves Yahoo Finance and other
  licensed data to third parties, which their terms forbid.
- **Commercial use**: paid products, newsletters, client reports, advisory work or anything else you're paid
  for that is built on the downloaded data.
- **Redistributing the data**: publishing or selling `data/`, `reports/`, exported tables or the dashboard
  JSON, or bundling downloaded data with a copy of the app.
- **Using the data feeds in another product**, or calling the sources from a shared server on behalf of many
  users.

If you want to do any of these, see [Offering Market Radar to others](#offering-market-radar-to-others).

## Source by source

| Source | Used for | Terms in brief | Personal use | Hosting or redistribution |
|---|---|---|---|---|
| **Yahoo Finance** (via the unofficial [`yfinance`](https://github.com/ranaroussi/yfinance) library) | All prices (history from before your first trade), ticker detail, analyst estimates, screener (Discover and valuation snapshots), fund data, symbol search | [Yahoo Terms of Service](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html): personal, non-commercial use only. Yahoo itself licenses the data from exchanges and data vendors. `yfinance` is not affiliated with Yahoo and is meant for personal use. | Yes | **No** |
| **FactSet** Earnings Insight (public PDF) | Forward P/E, yield gap | Copyrighted research FactSet publishes for reading. | Yes | **No** |
| **State Street (SSGA)** SPY holdings | S&P 500 constituents | Fund-site terms; constituents belong to S&P Dow Jones Indices. | Yes | **No** |
| **iShares (BlackRock)** fund holdings | ETF look-through, Discover universe | Fund-site terms; index constituents belong to the index providers (MSCI, STOXX and others). | Yes | **No** |
| **AAII** Sentiment Survey | Sentiment | Copyrighted by AAII. | Yes | **No** |
| **Cboe** put/call ratios | Sentiment | Cboe market data, subject to Cboe's website terms. | Yes | **No** |
| **FRED** (St. Louis Fed): series from **third parties** (e.g. `BAMLH0A0HYM2`, ICE BofA high-yield spread) | Credit spread | The series owner's copyright, shown in the series' notes on FRED. ICE restricts redistribution. | Yes | **No** |
| **FRED**: US government series (e.g. `DGS10`, `T10Y2Y`, `DGS3MO`, `DTWEXBGS`, `ECBDFR`) | Rates, curve, dollar | [FRED terms](https://fred.stlouisfed.org/legal/). The underlying data is generally public domain; check each series' notes. | Yes | Generally yes, with attribution |
| **multpl.com** | Shiller CAPE | Private website; terms unclear. CAPE follows Robert Shiller's published method. | Yes | Unclear: ask, or compute CAPE yourself |
| **Aswath Damodaran** (NYU Stern) | Implied equity risk premium | Freely shared academic data. | Yes | Yes, with attribution |
| **ECB Data Portal** | Euro-area yields and rates | [ECB reuse policy](https://www.ecb.europa.eu/services/disclaimer/html/index.en.html): reuse allowed with attribution. | Yes | Yes, with attribution |
| **OECD** | Composite leading indicators | [CC BY 4.0](https://www.oecd.org/en/about/terms-conditions.html). | Yes | Yes, with attribution |
| **CFTC** | Commitments of Traders (futures positioning) | US government data, public domain. | Yes | Yes |
| **SKAT** positive list (you download it into `imports/`) | UCITS / positive-list flag | Danish public-sector data. | Yes | Yes |

**MSCI ACWI**: the radar uses the iShares MSCI ACWI ETF's prices (from Yahoo), not MSCI's index data. "MSCI"
and "ACWI" are MSCI trademarks. Market Radar is not affiliated with or endorsed by MSCI, nor by any other
source above.

## Practical rules for your copy

- Keep `data/`, `reports/` and `exports/` to yourself. The repository already leaves them out of git; don't
  publish them elsewhere either.
- Don't expose `radar serve` to the internet or your network for other people to use. It listens on
  `127.0.0.1` (your computer only) on purpose.
- Respect the sources' limits. Market Radar paces its requests and pauses a host that asks it to slow down (see
  the *Operations* page). Don't remove that throttling or point many copies at one server.
- When you quote a number in something you publish, name the source.
- The brief's listening version (`/market-brief podcast`) is meant to be uploaded to your own NotebookLM
  notebook for your own listening. That sends the text to Google, so keep the notebook and the generated
  audio private: sharing or publishing them redistributes the data in them.

## Offering Market Radar to others

The intended way to share Market Radar is **each user runs their own copy**: you share the code, and every user
downloads the data themselves, for their own personal use. That is how the releases work.

A **hosted** version (a website others log into) would need, as a minimum:

1. **A licensed market-data vendor** in place of Yahoo, on a plan that explicitly allows *display to third
   parties / redistribution* for the exchanges you need (US, Nordic, European, Asian), not just internal use.
   End-of-day prices are affordable. Analyst estimates, revisions, screener fundamentals and fund holdings
   are the costly parts, and might have to be dropped.
2. **Permission or replacements** for FactSet, SSGA/iShares/index constituents, AAII, Cboe and third-party
   FRED series. Without them, leave those features out.
3. **Attribution** for the open sources (ECB, OECD, FRED, Damodaran).

Hosting raises issues beyond data licensing too, which are outside this file: **financial regulation**
(publishing scores and verdicts to others can count as investment recommendations under EU MAR, or as advice
needing authorisation from Finanstilsynet) and **GDPR** (you'd hold other people's portfolios).

## Not investment advice

Market Radar is an analysis tool. The data comes without any guarantee of accuracy, completeness or timeliness
from any of the sources above. Check anything important before you act on it.

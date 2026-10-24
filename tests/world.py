"""A small synthetic market whose answers are known in advance, shared by the report, profile and API tests.

Prices grow geometrically at G per bar, so any n-bar return is (1+g)^n - 1. S1 is held (bought at bar
BUY_AT) and E2 is on the watchlist.
"""
from datetime import date

import numpy as np
import pandas as pd

from radar import dashboard, profile, universe
from radar.sources import external, fxrates, ingest, tracked

N = 300
END = pd.Timestamp(date.today())
IDX = pd.bdate_range(end=END, periods=N)
T = np.arange(N)
G = {"ACWI": 0.0004, "S1": 0.0012, "S2": 0.0010, "S3": 0.0008, "S4": 0.0006, "S5": 0.0004, "S6": 0.0002,
     "E1": 0.0009, "E2": 0.0005, "E3": 0.0001, "THEME1": 0.0007, "THEME2": 0.0003}
BUY_AT = 50

UNIVERSE = {
    "benchmark": {"ticker": "ACWI", "name": "MSCI ACWI"},
    "watchlist": [],
    "sector_etfs": {"us": {"Technology": "LEAD"}},
    "etf_groups": {
        "sectors": {"label": "Sectors", "region": "us",
                    "items": [{"ticker": "LEAD", "name": "Leader"}, {"ticker": "LAG", "name": "Laggard"}]},
        "themes": {"label": "Themes", "region": "global",
                   "items": [{"ticker": "THEME1", "name": "Theme one"}, {"ticker": "THEME2", "name": "Theme two"}]},
    },
    "stock_groups": {"us": {"label": "US", "tickers": ["S1", "S2", "S3", "S4", "S5", "S6"]},
                     "europe": {"label": "Europe", "tickers": ["E1", "E2", "E3"]}},
    "macro": {"yahoo": {"VIX": "^VIX", "VIX3M": "^VIX3M", "Copper": "HG=F", "Gold": "GC=F", "Oil (WTI)": "CL=F"},
              "fred": {"BAMLH0A0HYM2": "US high-yield spread", "T10Y2Y": "US 10Y-2Y curve", "DGS10": "US 10Y yield",
                       "DTWEXBGS": "USD broad index"}},
    "external": {"cot": {}, "oecd_cli": {"G20": "G20"}},
}


def closes() -> dict[str, np.ndarray]:
    c = {t: 100 * (1 + g) ** T for t, g in G.items()}
    acwi = c["ACWI"]
    # LEAD started beating ACWI three months ago; LAG started trailing it
    c["LEAD"] = acwi * np.r_[np.ones(N - 60), 1.003 ** np.arange(60)]
    c["LAG"] = acwi * np.r_[np.ones(N - 60), 0.997 ** np.arange(60)]
    c["^VIX"], c["^VIX3M"], c["USDDKK=X"] = np.full(N, 14.0), np.full(N, 16.0), np.full(N, 6.5)
    return c


def bars(ticker: str, values) -> pd.DataFrame:
    v = np.asarray(values, dtype=float)
    return pd.DataFrame({"date": IDX[-len(v):], "ticker": ticker, "high": v * 1.01, "low": v * 0.99, "close": v,
                         "raw_close": v, "volume": 1000.0})


def prices() -> pd.DataFrame:
    return pd.concat([bars(t, v) for t, v in closes().items()], ignore_index=True)


def fred() -> pd.DataFrame:
    return pd.DataFrame({"BAMLH0A0HYM2": np.linspace(4.0, 3.0, N), "T10Y2Y": 0.5, "DGS10": 4.0,
                         "DTWEXBGS": 120.0}, index=IDX)


QUALITY = {"S1": 8, "S2": 7, "S3": 6, "S4": 5, "S5": 4, "E1": 3, "E2": 2, "E3": 1, "S6": 0}   # S6 is a bank
BANK = "S6"


def statements() -> pd.DataFrame:
    """Yahoo-style statements for the world's stocks: four fiscal years (December) and the last four quarters,
    better businesses (QUALITY) with higher, steadier margins, more cash flow and less debt."""
    last_q = (END - pd.Timedelta(days=60)).to_period("Q").end_time.normalize()
    quarters = [(last_q.to_period("Q") - k).end_time.normalize() for k in (3, 2, 1, 0)]
    last_fy = pd.Timestamp(f"{(last_q - pd.Timedelta(days=1)).year - (0 if last_q.month == 12 else 1)}-12-31")
    years = [pd.Timestamp(f"{last_fy.year - k}-12-31") for k in (3, 2, 1, 0)]
    rows = []

    def add(t, item, end, fp, v):
        rows.append({"ticker": t, "source": "yahoo", "item": item, "start": None, "end": end, "value": float(v),
                     "currency": None if item == "shares" else "USD", "form": {"FY": "yearly", "Q": "quarterly"}[fp],
                     "fp": fp, "filed": None, "known": end + pd.Timedelta(days=40), "fetched": END, "tag": item,
                     "accn": None, "assumed": False})
    for t, k in QUALITY.items():
        growth, margin = 1.03 + 0.01 * k, 0.10 + 0.02 * k
        for fp, ends, scale in (("FY", years, 1.0), ("Q", quarters, 0.25 * growth ** 4)):
            for i, end in enumerate(ends):
                rev = 1000 * scale * growth ** i * (1 + (0.02 if (i % 2) and k < 4 else 0))
                wobble = 0.03 * (i % 2) * (8 - k) / 8
                flows = {"revenue": rev, "gross_profit": rev * (0.35 + 0.03 * k - wobble),
                         "operating_income": rev * (margin - wobble), "pretax": rev * (margin - wobble - 0.01),
                         "income_tax": rev * margin * 0.2, "net_income": rev * margin * 0.75,
                         "interest": rev * 0.02, "dna": rev * 0.04, "cfo": rev * (0.12 + 0.02 * k),
                         "capex": rev * 0.05, "dividends_paid": rev * 0.02, "buybacks": rev * 0.01 * k,
                         "diluted_shares": 100.0}
                for item, v in flows.items():
                    add(t, item, end, fp, v)
                yr = 1000 * growth ** 3
                balance = {"total_assets": 2.0 * yr, "cash": 0.2 * yr, "current_liabilities": 0.3 * yr,
                           "debt_current": 0.05 * yr, "debt_noncurrent": (0.6 - 0.06 * k) * yr,
                           "equity": (0.5 + 0.05 * k) * yr, "shares": 100.0}
                if t == BANK:
                    balance |= {"total_assets": 12.0 * yr, "equity": 1.0 * yr}
                for item, v in balance.items():
                    add(t, item, end, fp, v)
    from radar.fundamentals import store

    return store.normalize(pd.DataFrame(rows))


def install(tmp_data, monkeypatch) -> dict[str, pd.DataFrame]:
    """Patch config, caches and Yahoo lookups to the synthetic world. Returns the dict of extra price
    frames that a faked download adds to (key = ticker)."""
    extra: dict[str, pd.DataFrame] = {}
    for mod in (dashboard, tracked, profile):
        monkeypatch.setattr(mod, "universe_config", lambda: UNIVERSE)
    monkeypatch.setattr(dashboard, "load_prices", prices)
    monkeypatch.setattr(dashboard, "load_fred", fred)
    monkeypatch.setattr(ingest, "load_prices", lambda: pd.concat([prices(), *extra.values()], ignore_index=True))
    for fn in ("load_cot", "load_oecd_cli", "load_factset", "load_analyst"):
        monkeypatch.setattr(external, fn, pd.DataFrame)
    monkeypatch.setattr(universe, "names", lambda ts: {t: f"{t} name" for t in ts})
    monkeypatch.setattr(fxrates, "currencies", lambda ts: {t: "USD" for t in ts})
    monkeypatch.setattr(universe, "sectors", lambda ts: pd.DataFrame(
        {"sector": "Technology", "industry": "Software"}, index=pd.Index(ts, name="ticker")))
    monkeypatch.setattr(external, "detail", lambda *a, **k: (None, "missing"))
    # what the score context reads from the cache: sectors (S6 a bank), quote currencies, stored statements
    stocks = list(QUALITY)
    pd.DataFrame({"ticker": stocks, "sector": ["Financial Services" if t == BANK else "Technology" for t in stocks],
                  "industry": ["Banks - Regional" if t == BANK else "Software" for t in stocks]}).to_csv(
        tmp_data / "sectors.csv", index=False)
    pd.DataFrame({"ticker": stocks, "currency": "USD"}).to_csv(tmp_data / "currencies.csv", index=False)
    from radar.fundamentals import store

    store.save(statements(), store.YAHOO_FILE)

    buy_px = 100 * 1.0012 ** BUY_AT
    (tmp_data / "holdings.csv").write_text(
        "symbol,status,quantity,avg_price,first_trade,last_sell_date,last_sell_price\n"
        f"S1,holding,10,{buy_px},{IDX[BUY_AT].date()},,\nE2,watch,,,,,\n", encoding="utf-8")
    (tmp_data / "transactions.csv").write_text(
        f"symbol,date,type,quantity,price\nS1,{IDX[BUY_AT].date()},BUY,10,{buy_px}\n", encoding="utf-8")
    return extra

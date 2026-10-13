"""A small synthetic market whose answers are known in advance, shared by the report, profile and API tests.

Prices grow geometrically at G per bar, so any n-bar return is (1+g)^n - 1. S1 is held (bought at bar
BUY_AT) and E2 is on the watchlist.
"""
from datetime import date

import numpy as np
import pandas as pd

from radar import dashboard, external, ingest, profile, report, snapshot, universe

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


def install(tmp_data, monkeypatch) -> dict[str, pd.DataFrame]:
    """Patch config, caches and Yahoo lookups to the synthetic world. Returns the dict of extra price
    frames that a faked download adds to (key = ticker)."""
    extra: dict[str, pd.DataFrame] = {}
    monkeypatch.setattr(report, "REPORTS", tmp_data / "reports")
    monkeypatch.setattr(dashboard, "REPORTS", tmp_data / "reports")
    monkeypatch.setattr(snapshot, "SNAPSHOTS", tmp_data / "snapshots")
    monkeypatch.setattr(profile, "PRICES_FILE", tmp_data / "prices.parquet")
    for mod in (dashboard, universe, profile):
        monkeypatch.setattr(mod, "universe_config", lambda: UNIVERSE)
    monkeypatch.setattr(dashboard, "load_prices", prices)
    monkeypatch.setattr(dashboard, "load_fred", fred)
    monkeypatch.setattr(ingest, "load_prices", lambda: pd.concat([prices(), *extra.values()], ignore_index=True))
    for fn in ("load_cot", "load_oecd_cli", "load_factset", "load_analyst"):
        monkeypatch.setattr(external, fn, pd.DataFrame)
    monkeypatch.setattr(universe, "names", lambda ts: {t: f"{t} name" for t in ts})
    monkeypatch.setattr(universe, "currencies", lambda ts: {t: "USD" for t in ts})
    monkeypatch.setattr(universe, "sectors", lambda ts: pd.DataFrame(
        {"sector": "Technology", "industry": "Software"}, index=pd.Index(ts, name="ticker")))
    monkeypatch.setattr(external, "detail", lambda *a, **k: (None, "missing"))

    buy_px = 100 * 1.0012 ** BUY_AT
    (tmp_data / "holdings.csv").write_text(
        "symbol,status,quantity,avg_price,first_trade,last_sell_date,last_sell_price\n"
        f"S1,holding,10,{buy_px},{IDX[BUY_AT].date()},,\nE2,watch,,,,,\n", encoding="utf-8")
    (tmp_data / "transactions.csv").write_text(
        f"symbol,date,type,quantity,price\nS1,{IDX[BUY_AT].date()},BUY,10,{buy_px}\n", encoding="utf-8")
    return extra

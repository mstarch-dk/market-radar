"""Everything the radar tracks: ETFs, stock lists, macro tickers, holdings."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from . import constituents, money, net, trades
from .config import settings, universe_config, write_csv
from .paths import CACHE


@dataclass(frozen=True)
class Instrument:
    ticker: str
    name: str
    group: str
    region: str
    ucits: str | None = None
    isin: str | None = None
    ucits_name: str | None = None


def benchmark() -> str:
    return universe_config()["benchmark"]["ticker"]


def etfs() -> list[Instrument]:
    out = []
    for key, g in universe_config()["etf_groups"].items():
        for it in g["items"]:
            out.append(Instrument(it["ticker"], it["name"], key, g["region"], it.get("ucits"), it.get("isin"),
                                  it.get("ucits_name")))
    return out


def group_benchmarks() -> dict[str, dict]:
    """ETF groups with a home-market benchmark (key -> {ticker, name}), used for an extra RRG."""
    return {k: g["benchmark"] for k, g in universe_config()["etf_groups"].items() if g.get("benchmark")}


# ---------- MSCI ACWI's own weights (iShares MSCI ACWI UCITS holdings) ----------


def names(tickers: list[str]) -> dict[str, str]:
    """Display names: config ETFs, SPY holdings file, then a cached Yahoo lookup for the rest."""
    out = {e.ticker: e.name for e in etfs()}
    us_file = CACHE / "constituents_us.csv"
    if us_file.exists():
        us = pd.read_csv(us_file)
        if "name" in us:
            out |= {t: str(n).title() for t, n in zip(us["ticker"], us["name"])}
    cache_file = CACHE / "names.csv"
    cached = dict(pd.read_csv(cache_file).values) if cache_file.exists() else {}
    missing = [t for t in tickers if t not in out and t not in cached]
    if missing:
        yf = net.yf()

        def lookup(t):
            try:
                info = yf.Ticker(t).info or {}
                return t, info.get("longName") or info.get("shortName")
            except Exception:
                return t, None
        with net.pool(8) as ex:
            found = {t: n for t, n in ex.map(lookup, missing) if n}   # a failed lookup is shown as the ticker,
        if found:                                                     # not remembered: it's asked again next time
            cached |= found
            write_csv(pd.DataFrame(list(cached.items()), columns=["ticker", "name"]), cache_file, index=False)
    return {t: out.get(t) or cached.get(t, t) for t in tickers}


def sectors(tickers: list[str]) -> pd.DataFrame:
    """Yahoo sector and industry per stock (cached in data/sectors.csv; ETFs and unknowns stay blank)."""
    cache_file = CACHE / "sectors.csv"
    cached = (pd.read_csv(cache_file, keep_default_na=False) if cache_file.exists()
              else pd.DataFrame(columns=["ticker", "sector", "industry"]))
    missing = sorted(set(tickers) - set(cached["ticker"]))
    if missing:
        yf = net.yf()

        def lookup(t):
            try:
                info = yf.Ticker(t).info or {}
            except Exception:
                return None  # not cached, so it is retried next run
            if not info.get("quoteType"):
                return None  # an empty answer (throttled, or Yahoo trouble) isn't "no sector": ask again next run
            return {"ticker": t, "sector": info.get("sector") or "", "industry": info.get("industry") or ""}
        with net.pool(8) as ex:
            found = [r for r in ex.map(lookup, missing) if r]
        cached = pd.concat([cached, pd.DataFrame(found)], ignore_index=True)
        CACHE.mkdir(parents=True, exist_ok=True)
        write_csv(cached, cache_file, index=False)
    return cached.set_index("ticker").reindex(tickers).fillna("")


# CAD: for the P/E of US listings that report in it (valuation.price_in); Yahoo has no CNY/DKK quote
FX_DKK = {"DKK": None, "USD": "USDDKK=X", "EUR": "EURDKK=X", "GBP": "GBPDKK=X", money.PENCE: "GBPDKK=X",
          "SEK": "SEKDKK=X", "NOK": "NOKDKK=X", "CHF": "CHFDKK=X", "PLN": "PLNDKK=X",
          "JPY": "JPYDKK=X", "HKD": "HKDDKK=X", "CAD": "CADDKK=X"}
# Yahoo has no KRW/DKK or TWD/DKK quote either: those go through USD (DKK per unit = USDDKK=X / USDxxx=X)
FX_VIA_USD = {"KRW": "USDKRW=X", "TWD": "USDTWD=X"}
FX_TICKERS = sorted({t for t in FX_DKK.values() if t} | set(FX_VIA_USD.values()))


def dkk_rates(last: dict[str, float]) -> dict[str, float]:
    """Latest DKK per unit of each currency from the latest close per FX ticker; a currency whose
    pair(s) are missing is left out. GBp is left out too (callers use GBP and divide by 100)."""
    out = {"DKK": 1.0} | {c: last[t] for c, t in FX_DKK.items() if t and not money.is_pence(c) and t in last}
    usd = last.get(FX_DKK["USD"])
    out |= {c: usd / last[t] for c, t in FX_VIA_USD.items() if usd and last.get(t)}
    return out


def fx_to_dkk(closes: pd.DataFrame, ccy: str | None) -> pd.Series | None:
    """DKK per unit of quoted price (pence-quoted GBp includes the /100)."""
    if ccy in FX_VIA_USD:
        usd, per_usd = FX_DKK["USD"], FX_VIA_USD[ccy]
        if usd not in closes or per_usd not in closes:
            return None
        return closes[usd].ffill() / closes[per_usd].ffill()
    if ccy not in FX_DKK:
        return None
    fx = FX_DKK[ccy]
    if fx is None:
        return pd.Series(1.0, index=closes.index)
    if fx not in closes:
        return None
    return closes[fx].ffill() * (0.01 if money.is_pence(ccy) else 1.0)


def currencies(tickers: list[str]) -> dict[str, str | None]:
    """Quote currency per ticker (cached Yahoo lookup). GBp = pence."""
    cache_file = CACHE / "currencies.csv"
    cached = dict(pd.read_csv(cache_file).values) if cache_file.exists() else {}
    missing = [t for t in tickers if t not in cached]
    if missing:
        yf = net.yf()

        def lookup(t):
            try:
                return t, yf.Ticker(t).fast_info.get("currency")
            except Exception:
                return t, None
        with net.pool(8) as ex:
            cached |= {t: c for t, c in ex.map(lookup, missing) if c}
        CACHE.mkdir(parents=True, exist_ok=True)
        write_csv(pd.DataFrame(list(cached.items()), columns=["ticker", "currency"]), cache_file, index=False)
    return {t: cached.get(t) for t in tickers}


def stock_groups(refresh: bool = False, offline: bool = False) -> dict[str, list[str]]:
    groups = {}
    for key, g in universe_config()["stock_groups"].items():
        groups[key] = constituents.us_constituents(refresh, offline) if g.get("source") == "spy_holdings" else list(g["tickers"])
    return groups


def stock_group_labels() -> dict[str, str]:
    return {k: g["label"] for k, g in universe_config()["stock_groups"].items()}


def macro_yahoo() -> dict[str, str]:
    return universe_config()["macro"]["yahoo"]


def macro_fred() -> dict[str, str]:
    return universe_config()["macro"]["fred"]


def macro_fred_views() -> dict[str, str]:
    """FRED series only the market-views evidence check reads (kept out of the regime's freshness check)."""
    return universe_config()["macro"].get("fred_views") or {}


def macro_fred_study() -> dict[str, str]:
    """FRED series only `radar study longrun` reads (USD/DKK since 1971, US recessions)."""
    return universe_config()["macro"].get("fred_study") or {}


def history_start(today: date | None = None) -> date:
    """Where the stored price history starts: `history_years` back, or earlier when your first trade needs it
    (that day minus backtest.warmup_days, for the 200-day average and 12-month momentum on the day you bought),
    but never more than backtest.max_years back."""
    from datetime import timedelta

    from . import userstore

    today = today or date.today()
    cfg, bt = settings(), settings().get("backtest") or {}
    start = today - timedelta(days=int(365.25 * cfg["history_years"]))
    dates = [str(t["date"])[:10] for t in userstore.transactions()]
    if dates:
        start = min(start, date.fromisoformat(min(dates)) - timedelta(days=int(bt.get("warmup_days", 0))))
    return max(start, today - timedelta(days=int(365.25 * bt.get("max_years", 10))))


def all_price_tickers(refresh: bool = False, offline: bool = False) -> list[str]:
    """Every ticker the radar downloads prices for; `offline` uses the cached constituent list as is."""
    tickers = {benchmark()}
    tickers |= {e.ticker for e in etfs()}
    tickers |= {b["ticker"] for b in group_benchmarks().values()}
    for g in stock_groups(refresh, offline).values():
        tickers |= set(g)
    tickers |= set(macro_yahoo().values())
    tickers |= set(trades.holdings()["symbol"].dropna())
    tickers |= trades.portfolio_symbols()                  # virtual portfolios need prices too
    tickers |= set(FX_TICKERS)
    return sorted(tickers)


# Exchange suffix -> region, for stocks outside the stock groups (region_for)
REGION_SUFFIXES = {
    "nordic": (".CO", ".ST", ".OL", ".HE", ".IC"),
    "europe": (".DE", ".F", ".PA", ".AS", ".BR", ".L", ".MI", ".SW", ".MC", ".LS", ".VI", ".IR", ".WA"),
    "asia": (".T", ".HK", ".TW", ".TWO", ".KS", ".KQ", ".SS", ".SZ", ".SI", ".AX", ".NS", ".BO"),
}


def region_for(ticker: str) -> str:
    for region, tickers in stock_groups(offline=True).items():
        if ticker in tickers:
            return region
    for region, suffixes in REGION_SUFFIXES.items():
        if ticker.upper().endswith(suffixes):
            return region
    return "us"

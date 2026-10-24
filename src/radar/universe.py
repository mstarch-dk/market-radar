"""Everything the radar tracks: ETFs, stock lists, macro tickers, holdings."""
from __future__ import annotations

from datetime import date

import pandas as pd

from . import net
from .config import typed, write_csv
from .paths import CACHE
from .portfolios import trades
from .sources import fxrates
from .sources.tracked import benchmark, etfs, group_benchmarks, macro_yahoo, stock_groups

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


def history_gap(closes) -> tuple[date, date] | None:
    """(where the stored prices start, where your trades need them from) when the prices start later; else None."""
    need = history_start()
    have = closes[benchmark()].dropna().index[0].date()
    return (have, need) if have > need else None


def history_start(today: date | None = None) -> date:
    """Where the stored price history starts: `history_years` back, or earlier when your first trade needs it
    (that day minus backtest.warmup_days, for the 200-day average and 12-month momentum on the day you bought),
    but never more than backtest.max_years back."""
    from datetime import timedelta

    from . import userstore

    today = today or date.today()
    bt = typed().backtest
    start = today - timedelta(days=int(365.25 * typed().history_years))
    dates = [str(t["date"])[:10] for t in userstore.transactions()]
    if dates:
        start = min(start, date.fromisoformat(min(dates)) - timedelta(days=bt.warmup_days))
    return max(start, today - timedelta(days=int(365.25 * bt.max_years)))


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
    tickers |= set(fxrates.FX_TICKERS)
    return sorted(tickers)


def held_or_watched() -> list[str]:
    """The symbols you hold or watch, in any portfolio."""
    h = trades.holdings()
    return sorted(h.loc[h["status"].isin(["holding", "watch"]), "symbol"].dropna()) if not h.empty else []


def tracked_stocks() -> list[str]:
    """The stocks the valuation snapshot and the statements cover: the stock groups, plus what you hold or watch."""
    etfs_ = {i.ticker for i in etfs()} | {benchmark()}
    names = {t for g in stock_groups(offline=True).values() for t in g} | set(held_or_watched())
    return sorted(names - etfs_)


def etf_tickers() -> list[str]:
    """The funds the ETF valuation snapshot covers: the config's, the benchmarks, and held or watched funds
    (stocks among them are skipped by the lookup)."""
    out = {i.ticker for i in etfs()} | {benchmark()}
    out |= {b["ticker"] for b in group_benchmarks().values()}
    stocks = {t for g in stock_groups(offline=True).values() for t in g}
    return sorted(out | (set(held_or_watched()) - stocks))


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

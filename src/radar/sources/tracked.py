"""What universe.yaml says the radar tracks: the benchmark, the ETFs, the stock groups, the macro series.

Config reads only (the S&P 500 list comes from `constituents`), so the data sources can use them; the
domain-level `universe` adds holdings, names, sectors and regions on top.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import universe_config
from . import constituents


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


def stock_groups(refresh: bool = False, offline: bool = False) -> dict[str, list[str]]:
    groups = {}
    for key, g in universe_config()["stock_groups"].items():
        groups[key] = constituents.us_constituents(refresh, offline) if g.get("source") == "spy_holdings" else list(g["tickers"])
    return groups


def stock_group_labels() -> dict[str, str]:
    return {k: g["label"] for k, g in universe_config()["stock_groups"].items()}


def etf_group_labels() -> dict[str, str]:
    return {k: g["label"] for k, g in universe_config()["etf_groups"].items()}


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


def attribution_tickers() -> set[str]:
    """Every ticker attribution's benchmark segments read prices from (universe.yaml `attribution:`): the sector
    proxies, the sector ETFs they fall back to, and the country ETFs."""
    conf = universe_config()
    attr = conf.get("attribution") or {}
    sectors = attr.get("sectors") or {}
    fallback = (conf.get("sector_etfs") or {}).get(attr.get("sector_fallback") or "") or {}
    out = set(sectors.values()) | {t for k, t in fallback.items() if k in sectors and isinstance(t, str)}
    for countries in (attr.get("regions") or {}).values():
        out |= set((countries or {}).values())
    return out

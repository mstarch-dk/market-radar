"""Currencies: each ticker's quote currency (a cached Yahoo lookup) and the FX tickers that turn it into DKK."""
from __future__ import annotations

import pandas as pd

from . import money, net
from .config import write_csv
from .paths import CACHE

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

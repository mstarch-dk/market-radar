"""Prices in DKK for a proposal: traded and adjusted closes, the exchange rate on a day, weekly returns."""
from __future__ import annotations

import pandas as pd

from .. import fxrates, money
from ..values import num


class Prices:
    """DKK closes and weekly DKK returns, computed once per ticker."""

    def __init__(self, market) -> None:
        self.market = market
        self._ccy: dict[str, str | None] = {}
        self._dkk: dict[str, pd.Series | None] = {}

    def ccy(self, t: str) -> str | None:
        if t not in self._ccy:
            self._ccy |= fxrates.currencies([t])
        return self._ccy.get(t)

    def preload(self, tickers) -> None:
        need = [t for t in tickers if t not in self._ccy]
        if need:
            self._ccy |= fxrates.currencies(need)

    def fx(self, t: str) -> pd.Series | None:
        return fxrates.fx_to_dkk(self.market.closes, self.ccy(t))

    def rate(self, t: str, day=None) -> float | None:
        return money.rate_on(self.fx(t), day)

    def dkk(self, t: str) -> pd.Series | None:
        if t not in self._dkk:
            c = self.market.closes
            fx = self.fx(t)
            s = (c[t] * fx.reindex(c.index)).dropna() if t in c and fx is not None else None
            self._dkk[t] = s if s is not None and not s.empty else None
        return self._dkk[t]

    def last_px(self, t: str) -> float | None:
        """The last traded close in the quote currency (adjusted close when no traded close is stored)."""
        raw = self.market.raw_closes()
        s = raw[t].dropna() if raw is not None and t in raw else pd.Series(dtype=float)
        if s.empty and t in self.market.closes:
            s = self.market.closes[t].dropna()
        return num(s.iloc[-1]) if len(s) else None

    def weekly(self, tickers, weeks: int) -> pd.DataFrame:
        """Weekly (W-FRI) DKK returns of `tickers` over the last `weeks` (a column only where it has prices)."""
        from ..signals import risk as rk

        cols = {}
        for t in dict.fromkeys(tickers):
            s = self.dkk(t)
            if s is not None and len(s) > 10:
                cols[t] = rk.weekly(s)
        if not cols:
            return pd.DataFrame()
        return pd.concat(cols, axis=1, sort=True).iloc[-weeks:]

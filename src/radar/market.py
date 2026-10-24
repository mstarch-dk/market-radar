"""The price store as wide frames (a data reader): what the app, the studies and the imports share."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import universe
from .config import typed
from .paths import PRICES_FILE
from .signals import momentum
from .sources import ingest, positive_list, tracked


@dataclass
class Market:
    """The price store as wide frames, plus derived tables that are expensive to recompute per ticker."""
    prices: pd.DataFrame
    closes: pd.DataFrame
    highs: pd.DataFrame
    lows: pd.DataFrame
    volumes: pd.DataFrame
    mtime: float = 0.0
    _leaders: pd.DataFrame | None = field(default=None, repr=False)
    _isins: tuple | None = field(default=None, repr=False)
    _raw: pd.DataFrame | None = field(default=None, repr=False)
    _fred: pd.DataFrame | None = field(default=None, repr=False)

    @classmethod
    def load(cls) -> Market:
        prices = ingest.load_prices()
        if prices.empty:
            raise SystemExit("No price data yet – run `radar update` first.")
        prices["date"] = pd.to_datetime(prices["date"])
        return cls(prices, ingest.wide(prices), ingest.wide(prices, "high"), ingest.wide(prices, "low"),
                   ingest.wide(prices, "volume"), PRICES_FILE.stat().st_mtime if PRICES_FILE.exists() else 0.0)

    def bars(self, ticker: str) -> pd.DataFrame:
        """The ticker's own sessions, as Yahoo delivered them. The wide frames forward-fill gaps (right for
        return windows); anything shown as a session (last price, day change, recent bars, chart) uses these."""
        return self.prices[self.prices["ticker"] == ticker].set_index("date").sort_index()

    def stale(self) -> bool:
        return PRICES_FILE.exists() and PRICES_FILE.stat().st_mtime != self.mtime

    def leaders(self) -> pd.DataFrame:
        """Momentum metrics and scores for every tracked stock (as on the dashboard), with sectors."""
        if self._leaders is None:
            lead = momentum.leaders(self.closes, self.volumes, tracked.stock_groups(offline=True),
                                    typed().momentum.min_history_days)
            sec = universe.sectors(list(lead["ticker"]))
            self._leaders = lead.assign(sector=lead["ticker"].map(sec["sector"]),
                                        industry=lead["ticker"].map(sec["industry"]))
        return self._leaders

    def fred(self) -> pd.DataFrame:
        if self._fred is None:
            self._fred = ingest.load_fred()
        return self._fred

    def raw_closes(self) -> pd.DataFrame | None:
        """Traded (unadjusted) closes, for the dividend factor in holding returns."""
        if self._raw is None and "raw_close" in self.prices:
            self._raw = ingest.wide(self.prices, "raw_close")
        return self._raw

    def positive_list(self) -> set[str] | None:
        if self._isins is None:
            try:
                self._isins = (positive_list.isins(),)
            except Exception:
                self._isins = (None,)
        return self._isins[0]

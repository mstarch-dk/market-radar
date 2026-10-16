"""The kvalitetsscore and værdiscore as they would have been on a past day: US stocks from SEC EDGAR only, whose
facts carry the day they became public (`known` = filing date + `backtest.fundamentals_lag_days`). On a day D the
scores are built by the live code (fundamentals/context.py, `pit=True`) from the facts known by D and the prices up
to D, so the study tests what the app shows, not a re-implementation.

What isn't as of D: sectors and industries (and so the bank/insurer set) are today's; the universe is today's US
group (survivorship); peers are the US names only, where the app pools every region; Yahoo's market-value check
is skipped (Yahoo's figure is today's). Non-US stocks have no dated statements and are left out."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import universe
from ..fundamentals import context as fcontext
from ..fundamentals import store
from ..signals import fundamentals as sf

GROUP = "us"
RANKED = ("roic", "fcf_margin", "fcf_yield", "ebit_ev", "shareholder_yield", "ey_vs_history", "gm_stability",
          "nd_ebitda", "div_years")


class FundPIT:
    """Scores per formation date, each computed once (a day's table is cached)."""

    def __init__(self, market, edgar: pd.DataFrame | None = None, tickers: list[str] | None = None):
        e = store.load_edgar() if edgar is None else edgar
        us = set(universe.stock_groups(offline=True).get(GROUP, []))
        names = sorted(set(tickers if tickers is not None else us) & set(e["ticker"].unique())) if not e.empty else []
        self.names = [t for t in names if t in market.closes.columns]
        self.edgar = e[e["ticker"].isin(self.names)]
        self.closes = market.closes
        self.raw = market.raw_closes()
        self.first_known = pd.Timestamp(self.edgar["known"].min()) if len(self.edgar) else None
        self._days: dict[pd.Timestamp, pd.DataFrame] = {}

    def context(self, day) -> fcontext.Context:
        day = pd.Timestamp(day)
        e = self.edgar[self.edgar["known"] <= day]
        raw = self.raw.loc[:day] if self.raw is not None else None
        return fcontext.Context(self.closes.loc[:day], raw, asof=day, edgar=e,
                                yahoo=pd.DataFrame(columns=store.COLS), tickers=self.names, pit=True)

    def table(self, day) -> pd.DataFrame:
        """One row per scored name on `day`: quality, value, qv, the pillars, the metrics oriented so that higher is
        better (rank_*) and gross profitability. Empty before the first filing."""
        day = pd.Timestamp(day)
        if day in self._days:
            return self._days[day]
        if self.first_known is None or day < self.first_known:
            out = pd.DataFrame()
        else:
            ctx = self.context(day)
            rows = {}
            for t, i in ctx.info.items():
                r = {f"rank_{k}": v for k, v in i["metrics"]["rank"].items()}
                r["gross_prof"] = _gross_profitability(i["facts"], day, ctx.cfg) if i["set"] == "standard" else None
                rows[t] = r
            ranks = pd.DataFrame.from_dict(rows, orient="index")
            cols = ["quality", "value", "qv", *(f"q_{p}" for p in sf.PILLARS)]
            out = ctx.scores.reindex(columns=cols).join(ranks, how="outer") if not ctx.scores.empty else ranks
        self._days[day] = out
        return out

    def col(self, day, key: str) -> pd.Series:
        t = self.table(day)
        return t[key].astype(float) if key in t else pd.Series(np.nan, index=t.index, dtype=float)


def _gross_profitability(v, day, cfg) -> float | None:
    """Novy-Marx: gross profit over the last twelve months divided by total assets (None when either is missing
    or stale)."""
    gp = store.ttm(v, "gross_profit")
    if gp is None:
        rev, cogs = store.ttm(v, "revenue"), store.ttm(v, "cost_of_revenue")
        if rev is None or cogs is None or rev.end != cogs.end:
            return None
        gp = store.Value(rev.value - cogs.value, rev.end, rev.basis)
    a = store.instant(v, "total_assets")
    age = cfg["ttm_max_age_days"]
    if a is None or a.value <= 0 or (day - gp.end).days > age or (day - a.end).days > age:
        return None
    return float(gp.value / a.value)

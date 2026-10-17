"""The kvalitetsscore and værdiscore of every tracked stock, from stored statements and prices (no network).

Per stock: its facts from one source (EDGAR when it has the core items, else Yahoo), the share price in the
reporting currency (the traded close converted with the radar's own FX closes; GBp is pence), the market value
from the latest share count (checked against diluted shares and Yahoo's market value), and the dividend record
from adjusted and traded closes. signals/fundamentals.py turns that into metrics and scores; the peers are the
stocks in the radar's stock groups.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from .. import fxrates, money, tracked, valuation
from ..config import settings
from ..paths import CACHE, HISTORY
from ..signals import fundamentals as sf
from ..signals import gauges as gz
from . import CORE, store

SCORES_FILE = HISTORY / "fundamentals" / "scores.parquet"     # weekly, like the valuation snapshot
LABELS = {"fcf_margin": "FCF margin", "roic": "ROIC", "gm_stability": "Gross-margin spread (pp)",
          "rev_stability": "Revenue steadiness", "nd_ebitda": "Net debt / EBITDA", "interest_cover": "Interest cover",
          "div_years": "Dividend years", "fcf_yield": "FCF yield", "ebit_ev": "EBIT / EV",
          "shareholder_yield": "Shareholder yield", "ey_vs_history": "EBIT/EV vs own history",
          "roe": "ROE", "roe_stability": "ROE spread (pp)", "equity_assets": "Equity / assets", "bp": "Book / price",
          "ep": "Earnings / price", "ep_vs_history": "E/P vs own history"}
SCORE_COLS = ["ticker", "set", "source", "quality", "value", "qv", "q_n", "v_n", "period_end", "fcf_yield", "roic",
              "ev_ebit", "note"]


def _cfg() -> dict:
    return settings()["fundamentals"]


def _csv(name: str, cols: list[str]) -> pd.DataFrame:
    p = CACHE / name
    return pd.read_csv(p, keep_default_na=False) if p.exists() else pd.DataFrame(columns=cols)


def _fin_currency(facts: pd.DataFrame, fallback: str | None) -> str | None:
    money = facts[~facts["item"].isin(["shares", "diluted_shares", "dps"])]["currency"].dropna()
    money = money[money.astype(str).str.len() == 3]
    return money.mode().iloc[0] if not money.empty else fallback


class Context:
    """Scores for every tracked stock, built once per report or request. `pit=True` (backtest/fund.py) scores as
    of `asof` from the facts and prices given only: Yahoo's latest snapshot (quote currency, market value check) is
    today's, so it is left out."""

    def __init__(self, closes: pd.DataFrame, raw: pd.DataFrame | None, asof=None, edgar: pd.DataFrame | None = None,
                 yahoo: pd.DataFrame | None = None, tickers: list[str] | None = None, pit: bool = False):
        cfg = self.cfg = _cfg()
        self.asof = pd.Timestamp(asof) if asof is not None else pd.Timestamp(closes.dropna(how="all").index[-1])
        e = store.as_known(store.load_edgar() if edgar is None else edgar)     # resolved once for every ticker
        y = store.as_known(store.load_yahoo() if yahoo is None else yahoo)
        by_e = {t: g for t, g in e.groupby("ticker")} if not e.empty else {}
        by_y = {t: g for t, g in y.groupby("ticker")} if not y.empty else {}
        self.groups = {t: g for g, ts in tracked.stock_groups(offline=True).items() for t in ts}
        names = tickers if tickers is not None else sorted(set(self.groups) | set(valuation.tracked_stocks()))
        snap = valuation.latest(valuation.load_stocks()) if not pit else pd.DataFrame()
        sec = _csv("sectors.csv", ["ticker", "sector", "industry"]).set_index("ticker")
        cur = dict(_csv("currencies.csv", ["ticker", "currency"]).values)
        fin_ind = cfg["financial_industries"]
        self.info: dict[str, dict] = {}
        rows = []
        for t in names:
            core_e = by_e.get(t)
            facts = core_e if core_e is not None and set(CORE) <= set(core_e["item"]) else by_y.get(t)
            if facts is None or facts.empty:
                continue
            s = snap.loc[t] if t in snap.index else None
            quote = (s["currency"] if s is not None and isinstance(s["currency"], str) else None) or cur.get(t) or None
            fin = _fin_currency(facts, s["financial_currency"] if s is not None and isinstance(
                s.get("financial_currency"), str) else quote)
            sector = sec.at[t, "sector"] if t in sec.index else ""
            industry = sec.at[t, "industry"] if t in sec.index else ""
            financial = sf.is_financial(industry, fin_ind)
            notes: list[str] = []
            v = store.View(facts, resolved=True)
            px = self._price_fin(t, closes, raw, quote, fin, notes)
            mcap = self._mcap(v, px, s, closes, quote, fin, notes)
            dps = sf.dps_by_year(closes[t], raw[t]) if raw is not None and t in raw and t in closes else None

            def price_on(day, px=px):
                if px is None:
                    return None
                s_ = px[px.index <= pd.Timestamp(day)].dropna()
                return float(s_.iloc[-1]) if len(s_) and (pd.Timestamp(day) - s_.index[-1]).days <= 10 else None

            m = sf.metrics(v, self.asof, cfg, financial, mcap, price_on, dps)
            src = facts["source"].iloc[0]
            self.info[t] = {"facts": v, "metrics": m, "notes": notes + m["notes"], "set": "financial" if financial
                            else "standard", "source": src, "currency": fin, "sector": sector, "industry": industry,
                            "mcap": mcap, "filed": None if src != "edgar" or facts["filed"].isna().all() else
                            pd.Timestamp(facts["filed"].max()).date().isoformat()}
            rows.append({"ticker": t, "set": self.info[t]["set"], "sector": sector, "member": t in self.groups,
                         **{f"rank_{k}": v for k, v in m["rank"].items()}})
        table = pd.DataFrame(rows)
        self.scores = sf.score(table, cfg) if not table.empty else pd.DataFrame()

    # ---- inputs

    @staticmethod
    def _price_fin(t, closes, raw, quote, fin, notes) -> pd.Series | None:
        """The traded close in the reporting currency (None without a price or rate)."""
        if raw is None or t not in raw or not quote or not fin:
            return None
        px = raw[t].dropna()
        if quote == fin:
            return px
        a, b = fxrates.fx_to_dkk(closes, quote), fxrates.fx_to_dkk(closes, fin)
        if a is None or b is None:
            notes.append(f"no {quote}→{fin} rate: value metrics left out")
            return None
        return (px * a.reindex(px.index).ffill() / b.reindex(px.index).ffill()).dropna()

    def _mcap(self, facts, px, snap_row, closes, quote, fin, notes) -> float | None:
        if px is None or px.empty:
            return None
        sh = store.instant(facts, "shares")
        dil = store.ttm(facts, "diluted_shares")
        shares = sh.value if sh is not None else None
        lo, hi = self.cfg["shares_low"], self.cfg["shares_high"]
        if dil is not None and dil.value > 0 and (shares is None or not lo <= shares / dil.value <= hi):
            if shares is not None:
                notes.append(f"reported shares {shares / dil.value:.2f}× diluted shares (several share classes?): "
                             "diluted shares used")
            shares = dil.value
        if not shares:
            return None
        mcap = shares * float(px.iloc[-1])
        yahoo = snap_row.get("market_cap") if snap_row is not None and "market_cap" in snap_row else None
        if yahoo is not None and pd.notna(yahoo) and quote and not money.is_pence(quote):
            a, b = fxrates.fx_to_dkk(closes, quote), fxrates.fx_to_dkk(closes, fin)
            if quote == fin:
                ym = float(yahoo)
            elif a is not None and b is not None and len(a.dropna()) and len(b.dropna()):
                ym = float(yahoo) * float(a.dropna().iloc[-1]) / float(b.dropna().iloc[-1])
            else:
                ym = None
            if ym and abs(mcap / ym - 1) > self.cfg["mcap_check"]:
                notes.append(f"market value from statement shares is {mcap / ym:.2f}× Yahoo's: Yahoo's used")
                mcap = ym
        return mcap

    # ---- outputs

    def _score(self, t: str, key: str):
        if self.scores.empty or t not in self.scores.index:
            return None
        v = self.scores.at[t, key]
        return None if pd.isna(v) else (int(v) if key in ("q_n", "v_n") else float(v))

    def stock(self, t: str) -> dict:
        """The fields a table row gets (StockFundamentals); all None for a stock without statements."""
        i = self.info.get(t)
        vals = i["metrics"]["values"] if i else {}
        out = {"quality": self._score(t, "quality"), "value": self._score(t, "value"), "qv": self._score(t, "qv"),
               "q_n": self._score(t, "q_n"), "v_n": self._score(t, "v_n"),
               "fund_set": i["set"] if i else None, "fund_source": i["source"] if i else None,
               "fund_period_end": i["metrics"]["period_end"] if i else None,
               "fcf_yield": vals.get("fcf_yield"), "ev_ebit": vals.get("ev_ebit"), "roic": vals.get("roic")}
        g = {"quality": gz.gauge("quality_score", out["quality"]), "value": gz.gauge("value_score", out["value"])}
        return out | {"fund_gauges": {k: v for k, v in g.items() if v}}

    def row(self, t: str) -> dict:
        """A row of the Quality & value page (QualityRow without ticker identity and ranks)."""
        i = self.info[t]
        v = i["metrics"]["values"]
        keep = ("fcf_margin", "gm_stability", "rev_stability", "rev_cagr", "nd_ebitda", "interest_cover", "div_years",
                "shareholder_yield", "ey_vs_history", "roe", "pb")
        return self.stock(t) | {k: v.get(k) for k in keep} | {f"q_{p}": self._score(t, f"q_{p}") for p in sf.PILLARS} \
            | {"sector": i["sector"] or None, "industry": i["industry"] or None, "notes": i["notes"]}

    def card(self, t: str) -> dict | None:
        """The ticker page's section: scores, every metric with its percentile and peers, the fiscal years."""
        i = self.info.get(t)
        if i is None:
            return None
        v = i["metrics"]["values"]
        kind = i["set"]
        pillar_of = {m: p for p, ms in sf.QUALITY[kind].items() for m in ms}
        rows = []
        for m in [m for ms in sf.QUALITY[kind].values() for m in ms] + list(sf.VALUE[kind]):
            pct = self._score(t, f"pct_{m}")
            basis = self.scores.at[t, f"basis_{m}"] if f"basis_{m}" in self.scores and t in self.scores.index else None
            peers = self._score(t, f"peers_{m}")
            rows.append({"key": m, "label": LABELS.get(m, m), "value": v.get(m), "pct": pct,
                         "basis": basis if isinstance(basis, str) else None, "peers": int(peers) if peers else None,
                         "pillar": pillar_of.get(m, "value")})
        facts = i["facts"]
        hist = []
        rev = store.annual(facts, "revenue")
        gp = store.annual(facts, "gross_profit")
        cfo, capex = store.annual(facts, "cfo"), store.annual(facts, "capex")
        for end, r in rev.tail(self.cfg["stability_years"]).items():
            hist.append({"year": end.date().isoformat(), "revenue": float(r),
                         "gross_margin": float(gp[end] / r) if end in gp and r else None,
                         "fcf_margin": float((cfo[end] - capex[end]) / r) if end in cfo and end in capex and r else None})
        return {"quality": self._score(t, "quality"), "value": self._score(t, "value"), "qv": self._score(t, "qv"),
                "q_n": self._score(t, "q_n"), "v_n": self._score(t, "v_n"), "fund_set": kind,
                "fund_source": i["source"], "period_end": i["metrics"]["period_end"], "filed": i["filed"],
                "currency": i["currency"], "ttm_basis": i["metrics"]["basis"],
                "ev_ebit": v.get("ev_ebit"), "market_cap": i["mcap"],
                "pillars": {p: self._score(t, f"q_{p}") for p in sf.PILLARS},
                "metrics": rows, "history": hist, "notes": i["notes"],
                "gauges": self.stock(t)["fund_gauges"]}

    def table(self) -> pd.DataFrame:
        """Every scored stock: ticker, region, the scores and the headline metrics (snapshots, the A/B test)."""
        rows = []
        for t in self.info:
            s = self.stock(t)
            rows.append({"ticker": t, "region": self.groups.get(t), **s})
        return pd.DataFrame(rows)


def save_week(ctx: Context, today: date | None = None) -> int:
    """This week's scores into the history tier (one per ISO week; see valuation.store_snapshot)."""
    t = ctx.table()
    if t.empty:
        return 0
    t = t.assign(set=t["fund_set"], source=t["fund_source"], period_end=t["fund_period_end"],
                 note=[("; ".join(ctx.info[x]["notes"]) or None) for x in t["ticker"]]).reindex(columns=SCORE_COLS)
    old = pd.read_parquet(SCORES_FILE) if SCORES_FILE.exists() else pd.DataFrame(columns=["date"] + SCORE_COLS)
    return valuation.store_snapshot(SCORES_FILE, old, t, today)


_ctx: tuple[tuple, Context] | None = None


def reset() -> None:
    """Forget the cached scores (context() builds them again)."""
    global _ctx
    _ctx = None


def context(closes: pd.DataFrame, raw: pd.DataFrame | None, stamp: float = 0.0) -> Context:
    """A Context for the API, rebuilt when the fact stores, the valuation snapshot or the prices (`stamp`) change."""
    global _ctx
    key = tuple(p.stat().st_mtime if p.exists() else 0.0 for p in (store.EDGAR_FILE, store.YAHOO_FILE,
                                                                     valuation.STOCKS_FILE)) + (stamp,)
    if _ctx is None or _ctx[0] != key:
        _ctx = (key, Context(closes, raw))
    return _ctx[1]

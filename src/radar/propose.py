"""Proposals: a fee-aware basket of new stocks for one of your portfolios, tested against the alternatives
(`radar propose`, the /propose-portfolio skill). Analysis, not advice.

- **Context**: the portfolio, its fee schedule (fees.SimFees), its holdings valued in DKK today, and your whole real
  book (every real portfolio) for overlap and the position limit. ACWI's own sector, region and currency weights
  come from the iShares MSCI ACWI UCITS holdings file (universe.acwi_holdings); without it the active weights are
  unknown and said so.
- **Gates**: a name is left out, and listed with why, when it has no score the tilt needs, no DKK rate, a stale
  price, a short history, thin trading, a share price above the ticket, or (tilts led by momentum) no uptrend.
- **Score** (`score`): the proposal score is a weighted mean of percentiles in the gated pool (the momentum score
  and K+V, by the tilt's pre-registered weights in settings.yaml `propose.tilts`) less penalties for volatility,
  a one-month spike and correlation with the portfolio. The weights are part of the rule the rule study tests
  (backtest/propose_study.py); changing them makes the study stale.
- **Selection** (`select`): greedy by score under caps on the portfolio *after* the addition: active weight vs
  ACWI by sector, region and currency (a bucket's first name is always allowed: one ticket is not a pile-up),
  new names per sector, a correlation cap against the picks and the holdings, and a position limit against your
  whole real book.
- **Sizing** (`size`): at least `min_ticket_dkk` per name, equal or inverse-volatility weights, whole shares, the
  portfolio's broker schedule with its FX surcharge, and an estimated half-spread by liquidity. Leftover cash
  goes to the ETF filler (ACWI UCITS; on an aktiesparekonto only if it is on the positive list) or stays cash.
- **Evaluation** (`evaluate`): exposures before → after, risk from a shrunk covariance of weekly DKK returns,
  the drawdown three ways (the rule study's realised drawdowns, a vol-scaled block bootstrap, historical stress
  windows), the expected excess over ACWI from the rule study only, the alternatives A0-A6 on the same metrics,
  and the pre-committed decision rule.
- **Follow-up**: `shadow` (virtual copies: the proposal, ACWI and the rule-only basket), `review` (how past
  proposals did against their model) and `check` (each pick's exit criteria today).

Missing is missing: a number that can't be computed is None with a note, never 0."""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import fees, universe, userstore
from .config import settings, universe_config, write_text
from .jsonsafe import clean as _clean
from .model import artifacts, inputs
from .model import paths as mpaths
from .model import prior as mprior
from .model.stats import mean as _mean
from .paths import HOME
from .values import num

PROPOSALS = HOME / "exports" / "proposals"
MEMOS = HOME / "research" / "proposals"
TILTS = ("momentum", "value", "mix")
MODES = ("conviction", "fill-gaps")
WEIGHTINGS = ("equal", "inverse-vol")
# settings that make up the rule: a change in any of them makes the rule study stale
RULE_KEYS = ("min_ticket_dkk", "max_names", "tilts", "require_trend_from", "penalties", "max_per_sector", "caps",
             "max_corr", "gates", "exit", "study_cost_bps", "study_ns", "horizons")
WEEKS_PER_MONTH = 52 / 12


def cfg() -> dict:
    return settings()["propose"]


def rule_hash(c: dict | None = None) -> str:
    c = c or cfg()
    blob = json.dumps({k: c.get(k) for k in RULE_KEYS}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:24] or "portfolio"


# ---------------- prices in DKK ----------------

class Prices:
    """DKK closes and weekly DKK returns, computed once per ticker."""

    def __init__(self, market):
        self.market = market
        self._ccy: dict[str, str | None] = {}
        self._dkk: dict[str, pd.Series | None] = {}

    def ccy(self, t: str) -> str | None:
        if t not in self._ccy:
            self._ccy |= universe.currencies([t])
        return self._ccy.get(t)

    def preload(self, tickers) -> None:
        need = [t for t in tickers if t not in self._ccy]
        if need:
            self._ccy |= universe.currencies(need)

    def fx(self, t: str) -> pd.Series | None:
        return universe.fx_to_dkk(self.market.closes, self.ccy(t))

    def rate(self, t: str, day=None) -> float | None:
        fx = self.fx(t)
        if fx is None or not len(fx.dropna()):
            return None
        v = fx.dropna().asof(pd.Timestamp(day)) if day is not None else fx.dropna().iloc[-1]
        return num(v) if v is not None and pd.notna(v) and v > 0 else None

    def dkk(self, t: str) -> pd.Series | None:
        if t not in self._dkk:
            c = self.market.closes
            fx = self.fx(t)
            self._dkk[t] = (c[t] * fx.reindex(c.index)).dropna() if t in c and fx is not None else None
            if self._dkk[t] is not None and self._dkk[t].empty:
                self._dkk[t] = None
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
        from .signals import risk as rk

        cols = {}
        for t in dict.fromkeys(tickers):
            s = self.dkk(t)
            if s is not None and len(s) > 10:
                cols[t] = rk.weekly(s)
        if not cols:
            return pd.DataFrame()
        return pd.concat(cols, axis=1, sort=True).iloc[-weeks:]


# ---------------- what you hold ----------------

def book(market, prices: Prices, portfolio_ids: list[int]) -> pd.DataFrame:
    """Holdings of these portfolios valued at the last close in DKK: symbol, quantity, price, rate, value_dkk
    (None when the price or rate is unknown)."""
    tx = universe.transactions(portfolio_ids)
    pos, _ = universe.positions(tx)
    pos = pos[pos["status"] == "holding"] if not pos.empty else pos
    rows = []
    for _, r in pos.iterrows():
        sym, qty = r["symbol"], float(r["quantity"])
        px, rate = prices.last_px(sym), prices.rate(sym)
        rows.append({"symbol": sym, "quantity": qty, "price": px, "rate": rate,
                     "value_dkk": qty * px * rate if px is not None and rate is not None else None})
    return pd.DataFrame(rows, columns=["symbol", "quantity", "price", "rate", "value_dkk"])


def _sector_etf_map() -> dict[str, str]:
    """Sector ETF ticker -> its sector (universe.yaml sector_etfs), for look-through of held sector funds."""
    out = {}
    for region in (universe_config().get("sector_etfs") or {}).values():
        for sec, t in region.items():
            if isinstance(t, str):
                out[t] = sec
    return out


def look_through() -> set[str]:
    """Tickers counted with ACWI's own weights: ACWI, its UCITS share classes, the filler and broad world funds
    (settings propose.look_through)."""
    f = cfg().get("etf_filler") or {}
    return ({universe.benchmark(), (universe_config().get("benchmark") or {}).get("ucits"), f.get("ticker"),
             f.get("model")} | set(cfg().get("look_through") or [])) - {None}


def info(tickers, prices: Prices) -> pd.DataFrame:
    """sector, region and currency per ticker (funds: a sector fund's sector, else '(fund)')."""
    from .universe import region_for

    tickers = list(dict.fromkeys(tickers))
    if not tickers:
        return pd.DataFrame(columns=["sector", "region", "currency"])
    prices.preload(tickers)
    sec = universe.sectors(tickers)
    etf_sec = _sector_etf_map()
    funds = {e.ticker for e in universe.etfs()} | look_through()
    rows = {}
    for t in tickers:
        s = sec["sector"].get(t) if t in sec.index else None
        s = s if isinstance(s, str) and s else None
        if t in funds or s is None:
            s = etf_sec.get(t, s or "(fund)")
        rows[t] = {"sector": s, "region": region_for(t), "currency": prices.ccy(t) or "?"}
    out = pd.DataFrame.from_dict(rows, orient="index")
    out.loc[out["currency"] == "GBp", "currency"] = "GBP"
    return out


DIMS = ("sector", "region", "currency")


def annotate(df: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """`df` with its sector, region and currency columns taken from `meta` (info())."""
    return df.drop(columns=[x for x in DIMS if x in df]).join(meta[list(DIMS)])


def exposures(values: dict[str, float], meta: pd.DataFrame, acwi: dict | None) -> dict:
    """Weights by sector, region and currency of DKK `values` (ACWI look-through), and active weights vs ACWI."""
    lt = look_through()
    total = sum(v for v in values.values() if v)
    out = {"total_dkk": total, "weights": {d: {} for d in DIMS}, "active": None,
           "note": None if acwi else "ACWI's own weights are unknown (no holdings file): active weights not shown"}
    if total <= 0:
        return out
    for t, v in values.items():
        if not v:
            continue
        if t in lt:
            for d in DIMS:
                if acwi:
                    for k, w in acwi[d].items():
                        out["weights"][d][k] = out["weights"][d].get(k, 0.0) + v * w / total
                else:
                    out["weights"][d]["ACWI (look-through unknown)"] = out["weights"][d].get(
                        "ACWI (look-through unknown)", 0.0) + v / total
            continue
        m = meta.loc[t] if t in meta.index else None
        for d in DIMS:
            k = (m[d] if m is not None else None) or "?"
            out["weights"][d][k] = out["weights"][d].get(k, 0.0) + v / total
    if acwi:
        out["active"] = {d: {k: out["weights"][d].get(k, 0.0) - acwi[d].get(k, 0.0)
                             for k in set(out["weights"][d]) | set(acwi[d])} for d in DIMS}
    return out


# ---------------- the pool, gates and score ----------------

def pool(market, prices: Prices, p=None, day=None, fund_table: pd.DataFrame | None = None, live: bool = True) -> pd.DataFrame:
    """The stock universe ranked on `day` (default: the latest session) with what the proposal needs."""
    from .model import panels as mp

    p = p or mp.panels(market)
    day = pd.Timestamp(day) if day is not None else p.sessions[-1]
    df = mp.ranked(p, day).set_index("ticker")
    tick = list(df.index)
    df["history"] = p.m["history"].loc[day].reindex(tick)
    dk = p.dkk.loc[:day].iloc[-20:]
    if p.volumes is not None:
        df["adv_dkk"] = (p.volumes.reindex(columns=p.dkk.columns).loc[:day].iloc[-20:] * dk).mean().reindex(tick)
    else:
        df["adv_dkk"] = np.nan
    if live:
        last = market.prices.groupby("ticker")["date"].max()
        df["last_bar"] = last.reindex(tick)
        prices.preload(tick)
        df["currency"] = [prices.ccy(t) for t in tick]
        df["price"] = [prices.last_px(t) for t in tick]
        df["rate"] = [prices.rate(t) for t in tick]
        df["price_dkk"] = df["price"] * df["rate"]
    else:
        df["last_bar"] = day
        df["price_dkk"] = p.dkk.loc[day].reindex(tick)
    if fund_table is None and live:
        from .fundamentals import context as fcontext

        t = fcontext.context(market.closes, market.raw_closes(), market.mtime).table()
        fund_table = t.set_index("ticker") if not t.empty else pd.DataFrame()
    for k in ("qv", "quality", "value"):
        df[k] = fund_table[k].reindex(tick).astype(float) if fund_table is not None and k in fund_table else np.nan
    df.attrs["day"] = day
    return df


def gates(df: pd.DataFrame, tilt: str, ticket: float, c: dict | None = None, day=None) -> tuple[pd.DataFrame, dict]:
    """The names a proposal may consider, and the rest by reason (each name under its first failing gate)."""
    c = c or cfg()
    g, w = c["gates"], c["tilts"][tilt]
    day = pd.Timestamp(day if day is not None else df.attrs.get("day", pd.Timestamp.today()))
    tests = []
    if w.get("momentum", 0) > 0:
        tests.append(("no momentum score", df["score"].isna()))
    if w.get("qv", 0) > 0:
        tests.append(("no K+V (kvalitet + værdi)", df["qv"].isna()))
    tests += [("no DKK rate", ~df["dkk"].eq(True)),
              ("stale price", (day - pd.to_datetime(df["last_bar"])).dt.days > g["max_stale_days"]),
              ("short history", df["history"].fillna(0) < g["min_history_weeks"] * 5),
              ("no volume data", df["adv_dkk"].isna()),
              ("thin trading", df["adv_dkk"] < g["min_adv_dkk"]),
              ("no price", df["price_dkk"].isna()),
              ("share price above the ticket", df["price_dkk"] > ticket)]
    if w.get("momentum", 0) >= c["require_trend_from"]:
        tests.append(("not in an uptrend", ~df["trend_ok"].eq(True)))
    left = pd.Series(True, index=df.index)
    out: dict[str, list[str]] = {}
    for reason, bad in tests:
        hit = left & bad.reindex(df.index).fillna(False).astype(bool)
        if hit.any():
            out[reason] = sorted(df.index[hit])
        left &= ~hit
    return df[left].copy(), out


def _pctl(s: pd.Series) -> pd.Series:
    return s.rank(pct=True) * 100


def score(df: pd.DataFrame, tilt: str, c: dict | None = None, corr: pd.Series | None = None) -> pd.DataFrame:
    """The proposal score on the gated pool, best first, with its parts."""
    c = c or cfg()
    w, pen = c["tilts"][tilt], c["penalties"]
    df = df.copy()
    parts, tot = [], 0.0
    for key, col in (("momentum", "score"), ("qv", "qv")):
        if w.get(key, 0) > 0:
            df[f"c_{key}"] = _pctl(df[col])
            parts.append(w[key] * df[f"c_{key}"])
            tot += w[key]
    base = sum(parts) / tot if tot else pd.Series(np.nan, index=df.index)
    df["pen_vol"] = (pen["vol"] * df["vol"].rank(pct=True)).fillna(pen["vol"])     # unknown volatility: the most
    hi = df["r1m"].quantile(0.9) if df["r1m"].notna().any() else np.inf
    df["pen_stretch"] = np.where(df["r1m"] >= hi, pen["stretch"], 0.0)
    df["corr_book"] = corr.reindex(df.index) if corr is not None else np.nan
    df["pen_corr"] = (pen["corr"] * df["corr_book"].clip(lower=0)).fillna(0.0)
    df["composite"] = base - df["pen_vol"] - df["pen_stretch"] - df["pen_corr"]
    df = df[df["composite"].notna()]
    return df.assign(_t=df.index).sort_values(["composite", "_t"], ascending=[False, True]).drop(columns="_t")


def corr_to(R: pd.DataFrame, series: pd.Series | None, min_weeks: int) -> pd.Series:
    """Each column's correlation with `series` (weekly returns), None below `min_weeks` shared weeks."""
    if series is None or R.empty:
        return pd.Series(np.nan, index=R.columns)
    s = series.reindex(R.index)
    ok = R.notna() & s.notna().to_numpy()[:, None]
    n = ok.sum()
    out = R.corrwith(s)
    return out.where(n >= min_weeks)


# ---------------- selection ----------------

@dataclass
class Base:
    """What the caps are measured against: the portfolio's DKK values by ticker and their meta, ACWI's weights,
    the whole real book's values (position limit), and weekly returns for the correlation cap."""
    values: dict[str, float]
    meta: pd.DataFrame
    acwi: dict | None
    whole: dict[str, float] = field(default_factory=dict)
    R: pd.DataFrame = field(default_factory=pd.DataFrame)

    def dim_values(self) -> dict[str, dict[str, float]]:
        ex = exposures(self.values, self.meta, self.acwi)
        return {d: {k: w * ex["total_dkk"] for k, w in ex["weights"][d].items()} for d in DIMS}


def select(scored: pd.DataFrame, n: int, amount: float, base: Base, c: dict | None = None, mode: str = "conviction",
           max_position: float | None = None, min_weeks: int = 26) -> tuple[list[dict], dict]:
    """Greedy by proposal score under the caps; returns the picks and, for names passed over, why."""
    c = c or cfg()
    if mode not in MODES:
        raise ValueError(f"mode is one of {', '.join(MODES)}")
    df = scored.copy()
    if df.empty or n <= 0:
        return [], {}
    held = base.dim_values()
    book_total = sum(v for v in base.values.values() if v)
    total_after = book_total + amount
    ticket = amount / n
    if mode == "fill-gaps" and base.acwi:
        sw = {k: v / book_total for k, v in held["sector"].items()} if book_total > 0 else {}
        deficit = df["sector"].map(lambda s: max(0.0, base.acwi["sector"].get(s, 0.0) - sw.get(s, 0.0)))
        df["bonus"] = (deficit / 0.10).clip(upper=1.0) * c["fill_gaps_bonus"]
        df["composite"] = df["composite"] + df["bonus"]
        df = df.assign(_t=df.index).sort_values(["composite", "_t"], ascending=[False, True]).drop(columns="_t")
    whole_total = sum(v for v in base.whole.values() if v) + amount
    book_names = [t for t, v in base.values.items() if v and book_total > 0 and v / book_total >= 0.02]
    R = base.R
    corr = R.corr(min_periods=min_weeks) if not R.empty else pd.DataFrame()
    picked: list[dict] = []
    added = {d: {} for d in DIMS}
    per_sector: dict[str, int] = {}
    passed: dict[str, str] = {}
    for t, r in df.iterrows():
        if len(picked) >= n:
            break
        why = None
        if per_sector.get(r["sector"], 0) >= c["max_per_sector"]:
            why = f"already {c['max_per_sector']} new names in {r['sector']}"
        if why is None and base.acwi:
            for d in DIMS:
                k = r[d]
                before = held[d].get(k, 0.0) + added[d].get(k, 0.0)
                if before <= 0:
                    continue                       # a bucket's first name: one ticket isn't a pile-up
                act = (before + ticket) / total_after - base.acwi[d].get(k, 0.0)
                if act > c["caps"][d]:
                    why = f"{d} {k} would be {act:+.0%} vs ACWI (cap {c['caps'][d]:+.0%})"
                    break
        if why is None and t in corr.index:
            for o in [x["ticker"] for x in picked] + book_names:
                v = corr.at[t, o] if o in corr.columns else np.nan
                if pd.notna(v) and o != t and v > c["max_corr"]:
                    why = f"correlation {v:.2f} with {o} (cap {c['max_corr']})"
                    break
        if why is None and max_position:
            share = (base.whole.get(t, 0.0) + ticket) / whole_total
            if share > max_position:
                why = f"{share:.1%} of your whole book (limit {max_position:.1%})"
        if why:
            passed[t] = why
            continue
        picked.append({"ticker": t, "composite": num(r["composite"]), "sector": r["sector"], "region": r["region"],
                       "currency": r["currency"]})
        per_sector[r["sector"]] = per_sector.get(r["sector"], 0) + 1
        for d in DIMS:
            added[d][r[d]] = added[d].get(r[d], 0.0) + ticket
    return picked, passed


def n_for(amount: float, c: dict | None = None, n: int | None = None) -> int:
    c = c or cfg()
    most = max(1, int(amount // c["min_ticket_dkk"]))
    return max(1, min(n or most, most, c["max_names"]))


# ---------------- sizing ----------------

def half_spread(adv: float | None, c: dict | None = None) -> float:
    c = c or cfg()
    for b in sorted(c["spread_bps"], key=lambda x: -x["min_adv_dkk"]):
        if adv is not None and not pd.isna(adv) and adv >= b["min_adv_dkk"]:
            return b["bps"] / 1e4
    return max(b["bps"] for b in c["spread_bps"]) / 1e4


def terms_for(prices: Prices, sf: fees.SimFees, t: str) -> fees.Terms:
    ccy = prices.ccy(t)
    rate = prices.rate(t)
    if rate is None:
        return sf.terms(t, None, None, count=False)

    def convert(amount: float, k: str) -> float | None:
        if k == "DKK":
            return amount / rate
        fx = universe.fx_to_dkk(prices.market.closes, k)
        v = fx.dropna().iloc[-1] if fx is not None and len(fx.dropna()) else None
        return amount * float(v) / rate if v is not None and v > 0 else None
    return sf.terms(t, ccy, convert, count=False)


def budgets(amount: float, vols: list[float | None], weighting: str, ticket: float) -> list[float]:
    """DKK per name: equal, or inverse volatility floored at `ticket` (the rest shared by the others)."""
    n = len(vols)
    if weighting == "equal" or n == 1 or any(v is None or not v > 0 for v in vols):
        return [amount / n] * n
    inv = np.array([1 / v for v in vols])
    fixed = np.zeros(n, dtype=bool)
    b = amount * inv / inv.sum()
    for _ in range(n):
        low = (b < ticket) & ~fixed
        if not low.any():
            break
        fixed |= low
        rest = amount - ticket * fixed.sum()
        b = np.where(fixed, ticket, rest * inv / inv[~fixed].sum() if (~fixed).any() else 0)
    return [float(x) for x in b]


def size(amount: float, picks: list[dict], df: pd.DataFrame, prices: Prices, sf: fees.SimFees, weighting: str = "equal",
         c: dict | None = None) -> dict:
    """Whole shares per pick within its budget, every cost counted; leftover cash stated."""
    c = c or cfg()
    if weighting not in WEIGHTINGS:
        raise ValueError(f"weighting is one of {', '.join(WEIGHTINGS)}")
    ticket = c["min_ticket_dkk"]
    vols = [num(df.at[x["ticker"], "vol"]) if x["ticker"] in df.index else None for x in picks]
    bud = budgets(amount, vols, weighting, ticket) if picks else []
    rows, flags = [], []
    for x, b in zip(picks, bud):
        t = x["ticker"]
        px, rate = prices.last_px(t), prices.rate(t)
        adv = num(df.at[t, "adv_dkk"]) if t in df.index else None
        hs = half_spread(adv, c)
        row = {"ticker": t, "budget_dkk": b, "price": px, "currency": prices.ccy(t), "rate": rate,
               "half_spread": hs, "quantity": None, "value_dkk": None, "cash_dkk": None, "fee_dkk": None,
               "spread_dkk": None, "roundtrip_dkk": None}
        if px is None or rate is None:
            flags.append(f"{t}: no price or DKK rate: can't be sized")
            rows.append(row)
            continue
        tm = terms_for(prices, sf, t)
        ask = px * (1 + hs)
        qty = math.floor(tm.value_for_budget(b / rate) / ask)
        if qty <= 0:
            flags.append(f"{t}: one share costs more than its budget of {b:,.0f} DKK")
            rows.append(row)
            continue
        trade = qty * ask
        fee = tm.fee(trade)
        sell_fee = tm.fee(qty * px)
        row |= {"quantity": qty, "value_dkk": qty * px * rate, "cash_dkk": (trade + fee) * rate,
                "fee_dkk": fee * rate, "spread_dkk": qty * px * hs * rate,
                "roundtrip_dkk": (fee + sell_fee + 2 * qty * px * hs) * rate}
        rows.append(row)
    ok = [r for r in rows if r["quantity"]]
    invested = sum(r["value_dkk"] for r in ok)
    out = {"rows": rows, "flags": flags, "invested_dkk": invested, "cash_dkk": sum(r["cash_dkk"] for r in ok),
           "fees_dkk": sum(r["fee_dkk"] for r in ok), "spread_dkk": sum(r["spread_dkk"] for r in ok),
           "roundtrip_dkk": sum(r["roundtrip_dkk"] for r in ok), "fee_model": sf.describe()}
    out["roundtrip_pct"] = out["roundtrip_dkk"] / invested if invested > 0 else None
    out["leftover_dkk"] = amount - out["cash_dkk"]
    return out


def filler(leftover: float, kind: str, prices: Prices, sf: fees.SimFees, allowed: bool = True, c: dict | None = None) -> dict | None:
    """The ETF filler for leftover cash (ACWI UCITS), or None when it isn't wanted or the leftover is too small."""
    c = c or cfg()
    f = c.get("etf_filler") or {}
    if not allowed or not f or leftover < f.get("min_dkk", 0):
        return None
    flag = universe.positive_list_flag(f.get("isin"), prices.market.positive_list())
    out = {"ticker": f["ticker"], "name": f.get("name"), "isin": f.get("isin"), "model": f.get("model"),
           "positive_list": flag, "budget_dkk": leftover, "quantity": None, "value_dkk": None, "fee_dkk": None,
           "note": None}
    if kind == "ask" and flag == "no":
        return out | {"budget_dkk": 0.0, "note": "not on the positive list: an aktiesparekonto can't hold it, so the "
                                                 "leftover stays cash"}
    if kind == "ask" and flag == "?":
        out["note"] = "positive list unknown (no imports/positivliste.xlsx): check before buying on an aktiesparekonto"
    px, rate = prices.last_px(f["ticker"]), prices.rate(f["ticker"])
    if px is None or rate is None:
        tm = sf.terms(f["ticker"], None, None, count=False)
        v = tm.value_for_budget(leftover)
        return out | {"value_dkk": v, "fee_dkk": leftover - v,
                      "note": (out["note"] + "; " if out["note"] else "") + f"its price isn't tracked: sized by value "
                              f"at the flat fee, modelled with {f.get('model')}"}
    tm = terms_for(prices, sf, f["ticker"])
    qty = math.floor(tm.value_for_budget(leftover / rate) / px)
    if qty <= 0:
        return out | {"budget_dkk": 0.0, "note": "one unit costs more than the leftover"}
    return out | {"quantity": qty, "value_dkk": qty * px * rate, "fee_dkk": tm.fee(qty * px) * rate}


# ---------------- risk ----------------

def shrunk_cov(R: pd.DataFrame, shrink: float, min_weeks: int) -> pd.DataFrame:
    """Pairwise weekly covariance pulled `shrink` of the way to a constant-correlation matrix, made positive
    semi-definite; columns with fewer than `min_weeks` returns are dropped."""
    R = R.loc[:, R.notna().sum() >= min_weeks]
    if R.shape[1] == 0:
        return pd.DataFrame()
    S = R.cov(min_periods=min_weeks)
    sd = np.sqrt(np.diag(S.to_numpy()))
    C = R.corr(min_periods=min_weeks).to_numpy()
    off = C[~np.eye(len(C), dtype=bool)]
    rbar = float(np.nanmean(off)) if off.size and np.isfinite(off).any() else 0.0
    F = rbar * np.outer(sd, sd)
    np.fill_diagonal(F, sd ** 2)
    Sn = S.to_numpy()
    Sn = np.where(np.isnan(Sn), F, Sn)
    M = shrink * F + (1 - shrink) * Sn
    vals, vecs = np.linalg.eigh((M + M.T) / 2)
    M = vecs @ np.diag(np.clip(vals, 0, None)) @ vecs.T
    return pd.DataFrame(M, index=S.index, columns=S.columns)


def risk(values: dict[str, float], cov: pd.DataFrame, bench: str) -> dict:
    """Ex-ante risk of DKK `values` from a weekly covariance (that includes `bench`)."""
    lt = look_through()
    agg: dict[str, float] = {}
    for t, x in values.items():                    # a world fund without its own prices is modelled with ACWI
        if x:
            k = bench if t in lt and t not in cov.index else t
            agg[k] = agg.get(k, 0.0) + x
    total = sum(agg.values())
    out = {"vol_ann": None, "beta": None, "te_ann": None, "div_ratio": None, "coverage": None,
           "missing": sorted(t for t in agg if t not in cov.index), "contributions": {}}
    covered = {t: x for t, x in agg.items() if t in cov.index}
    if total <= 0 or not covered or bench not in cov.index:
        return out
    out["coverage"] = sum(covered.values()) / total
    names = list(covered)
    w = np.array([covered[t] for t in names]) / sum(covered.values())
    S = cov.loc[names, names].to_numpy()
    sb = cov.loc[names, bench].to_numpy()
    vb = float(cov.at[bench, bench])
    var = float(w @ S @ w)
    if var <= 0:
        return out
    sd = np.sqrt(np.diag(S))
    out |= {"vol_ann": math.sqrt(var * 52), "beta": float(w @ sb) / vb if vb > 0 else None,
            "te_ann": math.sqrt(max(var - 2 * float(w @ sb) + vb, 0.0) * 52),
            "div_ratio": float(w @ sd) / math.sqrt(var),
            "contributions": {t: float(w[i] * (S @ w)[i] / var) for i, t in enumerate(names)}}
    return out


def series(values: dict[str, float], R: pd.DataFrame, bench: str) -> pd.Series | None:
    """Weekly return of fixed DKK weights (rebalanced weekly; names without a return that week are left out and
    the rest re-weighted)."""
    lt = look_through()
    agg: dict[str, float] = {}
    for t, x in values.items():
        if x:
            k = bench if t in lt and t not in R.columns else t
            agg[k] = agg.get(k, 0.0) + x
    cols = [t for t in agg if t in R.columns]
    if not cols:
        return None
    w = pd.Series({t: agg[t] for t in cols})
    sub = R[cols]
    ok = sub.notna()
    ww = ok.mul(w, axis=1)
    out = (sub.fillna(0).mul(w, axis=1).sum(axis=1) / ww.sum(axis=1)).where(ww.sum(axis=1) > 0.5 * w.sum())
    return out.dropna()


def bootstrap(rp: pd.Series, rb: pd.Series, weeks: int, excess: float | None, c: dict | None = None) -> dict:
    """Block bootstrap of the basket's and ACWI's weekly returns together: demeaned, scaled to today's (EWMA)
    volatility, re-centred on ACWI's assumed drift plus the modelled excess (none: on ACWI's drift alone)."""
    c = c or cfg()
    bc = c["bootstrap"]
    d = pd.concat([rp, rb], axis=1, keys=["p", "b"]).dropna()
    if len(d) < c["min_weeks"]:
        return {"weeks_used": len(d), "note": f"fewer than {c['min_weeks']} weeks of joint returns: no bootstrap"}
    lam = bc["ewma_lambda"]
    scale = {}
    for k in ("p", "b"):
        x = d[k] - d[k].mean()
        ew = float((x ** 2).ewm(alpha=1 - lam).mean().iloc[-1])
        full = float((x ** 2).mean())
        scale[k] = float(np.clip(math.sqrt(ew / full), 0.5, 2.0)) if full > 0 else 1.0
    mu_b = (1 + c["acwi_drift_annual"]) ** (1 / 52) - 1
    mu_p = mu_b + (excess / weeks if excess is not None else 0.0)
    X = np.column_stack([(d["p"] - d["p"].mean()) * scale["p"] + mu_p, (d["b"] - d["b"].mean()) * scale["b"] + mu_b])
    T, blk = len(X), max(1, int(bc["block_weeks"]))
    rng = np.random.default_rng(int(bc["seed"]))
    nb = math.ceil(weeks / blk)
    starts = rng.integers(0, T - blk + 1, size=(int(bc["draws"]), nb))
    idx = (starts[:, :, None] + np.arange(blk)).reshape(int(bc["draws"]), -1)[:, :weeks]
    paths = {}
    for j, k in enumerate(("p", "b")):
        cum = np.cumprod(1 + X[idx, j], axis=1)
        peak = np.maximum.accumulate(np.concatenate([np.ones((len(cum), 1)), cum], axis=1), axis=1)[:, 1:]
        paths[k] = {"ret": cum[:, -1] - 1, "dd": np.minimum((cum / peak - 1).min(axis=1), 0.0)}
    ex = paths["p"]["ret"] - paths["b"]["ret"]

    def q(a, p):
        return float(np.percentile(a, p))
    return {"draws": int(bc["draws"]), "weeks": weeks, "weeks_used": T, "block_weeks": blk, "vol_scale": scale,
            "drift_used": excess is not None, "acwi_drift_annual": c["acwi_drift_annual"],
            "ret": {"median": q(paths["p"]["ret"], 50), "p10": q(paths["p"]["ret"], 10), "p90": q(paths["p"]["ret"], 90)},
            "acwi_ret": {"median": q(paths["b"]["ret"], 50), "p10": q(paths["b"]["ret"], 10), "p90": q(paths["b"]["ret"], 90)},
            "excess": {"median": q(ex, 50), "p10": q(ex, 10), "p90": q(ex, 90)},
            "p_beat": float((ex > 0).mean()),
            "max_dd": {"median": q(paths["p"]["dd"], 50), "p10": q(paths["p"]["dd"], 10)},
            "acwi_max_dd": {"median": q(paths["b"]["dd"], 50), "p10": q(paths["b"]["dd"], 10)},
            "note": "weekly steps: a fall inside a week isn't seen, so drawdowns read a little shallow"}


def stress(values: dict[str, float], prices: Prices, bench: str, c: dict | None = None) -> list[dict]:
    """Today's DKK weights through each stress window (daily DKK closes), where the price history covers it."""
    c = c or cfg()
    lt = look_through()
    out = []
    for e in c.get("stress") or []:
        s, t1 = pd.Timestamp(e["start"]), pd.Timestamp(e["end"])
        rec = {"key": e["key"], "label": e["label"], "start": s.date().isoformat(), "end": t1.date().isoformat(),
               "coverage": None, "ret": None, "max_dd": None, "acwi_ret": None, "acwi_max_dd": None, "missing": []}
        total = sum(x for x in values.values() if x)
        legs, cov = [], 0.0
        for t, x in values.items():
            if not x:
                continue
            ser = prices.dkk(t)
            if ser is None and t in lt:
                ser = prices.dkk(bench)
            win = ser.loc[s:t1] if ser is not None else None
            if win is None or len(win) < 2 or (win.index[0] - s).days > 5 or (t1 - win.index[-1]).days > 5:
                rec["missing"].append(t)
                continue
            legs.append(win / win.iloc[0] * x)
            cov += x
        b = prices.dkk(bench)
        bw = b.loc[s:t1] if b is not None else None
        if bw is not None and len(bw) >= 2 and (bw.index[0] - s).days <= 5:
            bi = bw / bw.iloc[0]
            rec["acwi_ret"], rec["acwi_max_dd"] = float(bi.iloc[-1] - 1), float((bi / bi.cummax() - 1).min())
        rec["coverage"] = cov / total if total > 0 else None
        if legs and total > 0 and cov / total >= 0.5:
            v = pd.concat(legs, axis=1).ffill().sum(axis=1) / cov
            rec["ret"], rec["max_dd"] = float(v.iloc[-1] - 1), float((v / v.cummax() - 1).min())
        elif legs or rec["missing"]:
            rec["note"] = "less than half of the value has prices in this window: not replayed"
        out.append(rec)
    return out


def realised_dd(rp: pd.Series | None, weeks: int) -> float | None:
    from .signals import risk as rk

    if rp is None or len(rp.dropna()) < 10:
        return None
    return rk.drawdown(rp.dropna().iloc[-weeks:])[0]


# ---------------- the rule study's numbers ----------------

def load_study() -> artifacts.Loaded:
    """The rule study (model/artifacts.py), stale when it tested other settings than today's rule."""
    return artifacts.load("propose-study", rule_hash=rule_hash())


def haircut(c: dict | None = None, longrun: artifacts.Loaded | None = None) -> dict:
    """The survivorship haircut used: `survivorship_haircut`, or the long-run study's gauge when it implies more
    (`haircut_from_gauge`; never less than configured). Without a readable long-run study the configured one, with
    the reason."""
    c = c or cfg()
    conf = float(c["survivorship_haircut"])
    lr = longrun.report if longrun is not None else None
    g = ((lr.survivorship.implied_haircut if lr is not None and lr.survivorship else None)
         if c.get("haircut_from_gauge") else None)
    if g is not None and 0 < g < 1 and g > conf:
        return {"used": float(g), "configured": conf, "gauge": float(g),
                "basis": "the long-run study's survivorship gauge (larger than configured)"}
    out = {"used": conf, "configured": conf, "gauge": g, "basis": "configured"}
    if c.get("haircut_from_gauge") and longrun is not None and longrun.report is None:
        out["gauge_note"] = longrun.reason
    return out


_PRIORS: dict = {}


def long_prior(tilt: str, horizon: int, trend: str | None, c: dict | None = None) -> dict | None:
    """The tilt's long-run prior at this horizon (model/prior.tilt_prior in `prior.region`): in today's trend
    when that split has `prior.min_trend_eff_n` independent periods, else over all dates. Cached per factors file."""
    from . import factors

    c = c or cfg()
    pc = c.get("prior") or {}
    tw = (c.get("tilts") or {}).get(tilt)
    if not pc or not tw:
        return None
    f = factors.FACTORS_FILE
    stamp = f.stat().st_mtime if f.exists() else None
    key = (tilt, horizon, trend, stamp, json.dumps(pc, sort_keys=True, default=str), json.dumps(tw, sort_keys=True))
    if key not in _PRIORS:
        data = factors.load()
        w = mprior.prior_weights(tw, pc.get("components") or {}, pc.get("qv") or {})
        regions = [pc.get("region", "developed"), *(pc.get("report_regions") or [])]
        res = {r: mprior.tilt_prior(w, horizon, r, data, pc.get("since"), int(pc.get("trend_months", 10)))
               for r in regions}
        main = res[regions[0]]
        if main is None:
            _PRIORS[key] = None
        else:
            st = (main.get("by_trend") or {}).get(trend) if trend else None
            use = st if st and (st.get("eff_n") or 0) >= float(pc.get("min_trend_eff_n", 20)) else main
            _PRIORS[key] = {
                "mean": use["mean"], "se": use["se"], "t": use["t"], "eff_n": use["eff_n"],
                "basis": f"{regions[0]}, {trend}trend ({use['eff_n']:g} periods)" if use is st
                         else f"{regions[0]}, all dates since {pc.get('since')} ({use['eff_n']:g} periods)",
                "region": regions[0], "trend": trend if use is st else None, "weights": w,
                "components": main.get("components"),
                "regions": {r: None if v is None else {"mean": v["mean"], "t": v["t"], "eff_n": v["eff_n"]}
                            for r, v in res.items()}}
    return _PRIORS[key]


def shrink(short: float | None, se_short: float | None, prior: dict | None, horizon: int, c: dict) -> dict:
    """Precision-weighted mean of the rule study's excess and the long-run prior (a normal-normal Bayesian update):
    w = (1/se_s²) / (1/se_s² + 1/(se_p² + tau²)), tau = `prior.tau_annual` × √(H/12). Without a standard error for
    the study (too few dates, t of 0) the prior alone; without a prior, the study alone."""
    if short is None:
        return {"drift": None, "w_short": None}
    if prior is None or prior.get("mean") is None:
        return {"drift": short, "w_short": 1.0, "note": "no long-run prior (run `radar update` for the JKP portfolios)"}
    tau = float((c.get("prior") or {}).get("tau_annual", 0)) * math.sqrt(horizon / 12)
    var_p = (prior.get("se") or 0) ** 2 + tau ** 2
    if not se_short:
        return {"drift": prior["mean"], "w_short": 0.0, "tau": tau, "note": "the study's excess has no standard error"}
    if var_p <= 0:
        return {"drift": prior["mean"], "w_short": 0.0, "tau": tau}
    w = (1 / se_short ** 2) / (1 / se_short ** 2 + 1 / var_p)
    return {"drift": w * short + (1 - w) * prior["mean"], "w_short": w, "tau": tau}


def study_view(study: artifacts.Loaded | None, tilt: str, n: int, horizon: int, regime: str | None,
               c: dict | None = None, trend: str | None = None) -> dict:
    """The rule study's figures for this tilt, the nearest basket size and the horizon, with the drift the model
    uses. The study's mean (the regime's own when it has enough dates, else all dates) is cut by the survivorship
    haircut when positive (`haircut`), then shrunk toward the tilt's long-run prior (`long_prior`, `shrink`): the
    study has few independent periods and today's universe, the prior decades of every listed stock. Gross of
    costs (the proposal's own costs are taken off in `evaluate`)."""
    c = c or cfg()
    out = {"available": False, "stale": None, "drift_gross": None, "drift_gross_raw": None, "drift_short": None,
           "basis": None, "n_used": None, "us_only": None, "prior": None, "w_short": None, "haircut": None}
    rep = study.report if study is not None else None
    if rep is None:
        out["note"] = (study.reason if study is not None else None) or "no rule study yet: run `radar study propose`"
        return out
    out["stale"] = study.status == "stale"
    res = rep.results.get(tilt) or {}
    if not res:
        out["note"] = f"the rule study has no {tilt} results"
        return out
    ns = sorted(int(k) for k in res)
    nu = min(ns, key=lambda k: (abs(k - n), k))
    cell = res[str(nu)].get(str(horizon))
    kept = cell.kept if cell is not None and cell.kept is not None else artifacts.Split()
    exits = cell.exits if cell is not None else None
    out |= {"available": kept.all is not None, "n_used": nu, "horizon": horizon,
            "kept": kept.model_dump(exclude_unset=True),
            "exits": exits.model_dump(exclude_unset=True) if exits is not None else None,
            "us_only": rep.us_only.get(tilt), "asof": rep.asof, "first": rep.universe.first}
    if out["stale"]:
        out["note"] = "the rule study was run with other settings: its numbers don't describe today's rule"
        return out
    allr = kept.all or artifacts.Summary()
    reg = kept.by_regime.get(str(regime)) if regime else None
    use = reg if reg is not None and (reg.dates or 0) >= c["min_regime_dates"] else allr
    out["basis"] = f"regime {regime} ({use.dates} dates)" if use is reg and reg else f"all dates ({allr.dates})"
    g = use.gross_mean
    hc = haircut(c, artifacts.load("longrun-study"))
    out["drift_gross_raw"] = g
    out["haircut"] = hc
    short = None if g is None else (g * (1 - hc["used"]) if g > 0 else g)
    out["drift_short"] = short
    t, mean = use.t, use.mean
    se_short = abs(mean / t) if t and mean is not None else None
    prior = long_prior(tilt, horizon, trend, c)
    sh = shrink(short, se_short, prior, horizon, c)
    out |= {"drift_gross": sh["drift"], "w_short": sh["w_short"], "se_short": se_short, "prior": prior,
            "tau": sh.get("tau")}
    if sh.get("note"):
        out["prior_note"] = sh["note"]
    return out


# ---------------- context, candidates ----------------

@dataclass
class Ctx:
    market: object
    prices: Prices
    portfolio: dict
    holdings: pd.DataFrame
    whole: pd.DataFrame
    sf: fees.SimFees
    acwi: dict | None
    regime: str | None
    notes: list[str]
    trend: str | None = None       # ACWI above ("up") or below ("down") its prior.trend_months-month average


def context(market, name: str, offline: bool = False) -> Ctx:
    p = userstore.portfolio_by_name(name)
    if not p:
        known = ", ".join(x["name"] for x in userstore.portfolios(include_archived=False))
        raise ValueError(f"no portfolio called {name} (yours: {known or 'none'})")
    prices = Prices(market)
    notes = []
    held = book(market, prices, [p["id"]])
    whole = book(market, prices, userstore.portfolio_ids())
    for df, what in ((held, name), (whole, "your real portfolios")):
        miss = df[df["value_dkk"].isna()]["symbol"].tolist()
        if miss:
            notes.append(f"{what}: no price or DKK rate for {', '.join(miss)}: left out of the weights")
    acwi = universe.acwi_weights(offline=offline)
    if acwi is None:
        notes.append("ACWI's own weights are unknown (no iShares holdings file): active-weight caps are off")
    sf = fees.SimFees.for_portfolio(p, float((settings().get("backtest") or {}).get("fee_bps", 0)))
    if not sf.schedule:
        notes.append(f"{name} has no fee schedule: fees are the flat backtest.fee_bps")
    return Ctx(market, prices, p, held, whole, sf, acwi, inputs.current_regime()["label"], notes, _trend(market))


def _trend(market, months: int | None = None) -> str | None:
    """"up" when ACWI's last month-end close is at or above the mean of its last `months` month-ends, else
    "down" (the split the long-run prior uses); None without enough history."""
    months = months or int((cfg().get("prior") or {}).get("trend_months", 10))
    try:
        s = market.closes[universe.benchmark()].dropna()
    except (KeyError, AttributeError):
        return None
    me = s.groupby(s.index.to_period("M")).last()
    if len(me) < months:
        return None
    return "up" if me.iloc[-1] >= me.iloc[-months:].mean() else "down"


def _values(df: pd.DataFrame) -> dict[str, float]:
    return {r["symbol"]: float(r["value_dkk"]) for _, r in df.iterrows() if r["value_dkk"] is not None and pd.notna(r["value_dkk"])}


def _base(ctx: Ctx, extra=(), weeks: int = 52) -> Base:
    vals = _values(ctx.holdings)
    meta = info(list(vals) + list(extra), ctx.prices)
    R = ctx.prices.weekly(list(vals) + list(extra), weeks)
    return Base(vals, meta, ctx.acwi, _values(ctx.whole), R)


def ranked_pool(ctx: Ctx, tilt: str, ticket: float, p=None, raw: pd.DataFrame | None = None
                ) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Gated and scored pool for this portfolio (correlation with its weekly returns), the exclusions and the
    ungated pool."""
    c = cfg()
    df = raw if raw is not None else pool(ctx.market, ctx.prices, p)
    kept, excluded = gates(df, tilt, ticket, c)
    vals = _values(ctx.holdings)
    R = ctx.prices.weekly(list(kept.index) + list(vals) + [universe.benchmark()], 52)
    book_r = series(vals, R, universe.benchmark()) if vals else None
    corr = corr_to(R.reindex(columns=list(kept.index)), book_r, c["min_weeks"]) if book_r is not None else None
    kept = annotate(kept, info(list(kept.index), ctx.prices))
    return score(kept, tilt, c, corr), excluded, df


def rule_basket(ctx: Ctx, scored: pd.DataFrame, amount: float, n: int, mode: str, max_position: float | None,
                weighting: str) -> tuple[list[dict], dict, dict]:
    base = _base(ctx, list(scored.index[: max(4 * n, 40)]))
    chosen, passed = select(scored, n, amount, base, cfg(), mode, max_position)
    return chosen, passed, size(amount, chosen, scored, ctx.prices, ctx.sf, weighting)


def default_exit(tilt: str, fill: str, horizon: int, c: dict | None = None) -> dict:
    """The standard exit criteria every pick gets (thesis checks are added by the skill)."""
    c = c or cfg()
    st = settings()["stops"]
    w = c["tilts"][tilt]
    sig = ({"metric": "score", "below": c["exit"]["min_score"]} if w.get("momentum", 0) >= w.get("qv", 0)
           else {"metric": "qv", "below": c["exit"]["min_qv"]})
    review = (pd.Timestamp(fill) + pd.DateOffset(months=horizon)).date().isoformat()
    return {"review_level": {"rule": f"close below the {st['trend_sma']}-day average", "sma": st["trend_sma"],
                             "mode": st["mode"], "action": st["action"]},
            "signal": sig, "time_stop": review, "thesis": []}


def candidates(market, name: str, amount: float, tilt: str = "mix", mode: str = "conviction", n: int | None = None,
               weighting: str = "equal", max_position: float | None = None, etf: bool = True, horizon: int = 6,
               top: int = 40, offline: bool = False) -> dict:
    """The context, the gates, a scored shortlist and the rule-only basket as a draft picks file."""
    c = cfg()
    if tilt not in TILTS:
        raise ValueError(f"tilt is one of {', '.join(TILTS)}")
    if amount < c["min_ticket_dkk"]:
        raise ValueError(f"{amount:,.0f} DKK is less than one ticket ({c['min_ticket_dkk']:,} DKK): consider the "
                         "ACWI ETF instead")
    ctx = context(market, name, offline)
    n = n_for(amount, c, n)
    ticket = amount / n
    scored, excluded, _ = ranked_pool(ctx, tilt, ticket)
    chosen, passed, sz = rule_basket(ctx, scored, amount, n, mode, max_position, weighting)
    fill_ = filler(sz["leftover_dkk"], ctx.portfolio["kind"], ctx.prices, ctx.sf, etf, c)
    today = pd.Timestamp(market.closes.index[-1]).date().isoformat()
    vals = _values(ctx.holdings)
    meta = info(list(vals), ctx.prices)
    rows = []
    names = universe.names(list(scored.index[:top]))
    for t, r in scored.head(top).iterrows():
        rows.append({"ticker": t, "name": names.get(t), "composite": r["composite"],
                     "c_momentum": r.get("c_momentum"), "c_qv": r.get("c_qv"), "pen_vol": r["pen_vol"],
                     "pen_stretch": r["pen_stretch"], "pen_corr": r["pen_corr"], "corr_book": r["corr_book"],
                     "momentum_score": r["score"], "qv": r["qv"], "quality": r["quality"], "value": r["value"],
                     "r1m": r["r1m"], "r3m": r["r3m"], "r6m": r["r6m"], "r12_1": r["r12_1"], "from_high": r["from_high"],
                     "trend_ok": r["trend_ok"], "vol": r["vol"], "sector": r["sector"], "region": r["region"],
                     "currency": r["currency"], "adv_dkk": r["adv_dkk"], "price_dkk": r["price_dkk"],
                     "half_spread": half_spread(r["adv_dkk"], c), "in_rule_basket": t in {x["ticker"] for x in chosen},
                     "passed_over": passed.get(t), "ask_flag": ask_flag(t) if ctx.portfolio["kind"] == "ask" else None})
    ex = default_exit(tilt, today, horizon, c)
    draft = {"type": "propose-picks", "meta": {"portfolio": name, "portfolio_id": ctx.portfolio["id"], "amount": amount,
                                                "tilt": tilt, "mode": mode, "n": n, "horizon": horizon,
                                                "weighting": weighting, "max_position": max_position, "etf": etf,
                                                "date": today, "settings_hash": rule_hash(c), "stops": settings()["stops"],
                                                "rule_basket": [x["ticker"] for x in chosen], "frozen_at": None},
             "picks": [{"ticker": x["ticker"], "why": None, "swapped_from": None, "swap_reason": None, "exit": ex}
                       for x in chosen],
             "filler": fill_}
    return _clean({
        "portfolio": {"id": ctx.portfolio["id"], "name": name, "mode": ctx.portfolio["mode"], "kind": ctx.portfolio["kind"],
                      "value_dkk": sum(vals.values()), "holdings": len(vals)},
        "asof": today, "amount": amount, "tilt": tilt, "mode": mode, "n": n, "ticket_dkk": ticket,
        "regime": ctx.regime, "trend": ctx.trend, "fee_model": ctx.sf.describe(), "notes": ctx.notes,
        "exposure_now": exposures(vals, meta, ctx.acwi), "acwi_weights": ctx.acwi is not None,
        "gates": {"pool": int(len(scored)) + sum(len(v) for v in excluded.values()), "kept": int(len(scored)),
                  "excluded": {k: {"count": len(v), "tickers": v} for k, v in excluded.items()}},
        "shortlist": rows,
        "rule_basket": {"picks": chosen, "passed_over": passed, "size": sz, "filler": fill_},
        "study": study_view(load_study(), tilt, n, horizon, ctx.regime, trend=ctx.trend),
        "ask": ask_account(ctx, amount) if ctx.portfolio["kind"] == "ask" else None,
        "draft_picks": draft,
        "columns": {"composite": "the proposal score: tilt-weighted percentiles less penalties (0-100 scale)",
                    "c_momentum": "momentum score percentile in the gated pool", "c_qv": "K+V percentile in the pool",
                    "corr_book": "weekly DKK correlation with the portfolio over a year",
                    "half_spread": "estimated half-spread (an estimate by liquidity bucket)"},
    })


# ---------------- the account ----------------

def ask_flag(t: str) -> str | None:
    """A note for an aktiesparekonto: listings the radar can't place on a known exchange need checking."""
    m = fees.market_of(t)
    return None if m != "OTHER" else "listing outside the known exchanges: check that an aktiesparekonto may hold it"


def ask_account(ctx: Ctx, amount: float) -> dict:
    c = cfg()
    cap, year = c.get("ask_deposit_cap"), c.get("ask_cap_year")
    rows = universe.ledger([ctx.portfolio["id"]])
    dep = None
    if not rows.empty and "amount" in rows:
        d = rows[rows["type"].isin(["DEPOSIT", "WITHDRAW"])]
        if len(d):
            dep = float(np.where(d["type"] == "DEPOSIT", d["amount"].astype(float), -d["amount"].astype(float)).sum())
    out = {"deposit_cap": cap, "cap_year": year, "net_deposits_dkk": dep,
           "note": "17 % lager on the account's yearly gain: frequent momentum trades cost no extra tax here; "
                   "funds must be on the positive list"}
    if cap is None:
        out["cap_check"] = "not checked: set propose.ask_deposit_cap (and ask_cap_year) from skat.dk"
    elif dep is None:
        out["cap_check"] = "not checked: the account has no deposit rows"
    else:
        out["cap_check"] = "within the cap" if dep + amount <= cap else f"over the {year} cap by {dep + amount - cap:,.0f} DKK"
    return out


# ---------------- evaluation ----------------

def _picks_doc(doc: dict) -> dict:
    if doc.get("type") != "propose-picks" or not doc.get("picks"):
        raise ValueError("not a picks file (type propose-picks with picks)")
    seen = set()
    for x in doc["picks"]:
        t = x.get("ticker")
        if not t:
            raise ValueError("a pick without a ticker")
        if t in seen:
            raise ValueError(f"{t} is picked twice")
        seen.add(t)
    return doc


def picks_sha(doc: dict) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, default=str).encode()).hexdigest()[:16]


def metrics(values: dict[str, float], ctx: Ctx, cov: pd.DataFrame, R: pd.DataFrame, horizon: int, drift: float | None,
            cost_pct: float | None, c: dict, before: dict[str, float] | None = None, draws: int | None = None) -> dict:
    """One alternative on the common metrics: risk alone and in the portfolio, the bootstrap, costs, the drift."""
    bench = universe.benchmark()
    cc = dict(c, bootstrap=dict(c["bootstrap"], draws=draws or c["bootstrap"]["draws"]))
    rp = series(values, R, bench)
    boot = bootstrap(rp, R[bench], round(horizon * WEEKS_PER_MONTH), None if drift is None else drift - (cost_pct or 0.0), cc) \
        if rp is not None and bench in R else {"note": "no weekly returns"}
    after = dict(before or {})
    for t, v in values.items():
        after[t] = after.get(t, 0.0) + v
    return {"risk": risk(values, cov, bench), "after": risk(after, cov, bench) if before is not None else None,
            "bootstrap": boot, "cost_pct": cost_pct, "drift_gross": drift,
            "drift_net": None if drift is None else drift - (cost_pct or 0.0),
            "realised_dd_1y": realised_dd(rp, 52), "realised_dd_3y": realised_dd(rp, 156)}


def adv_dkk(prices: Prices, t: str) -> float | None:
    """Mean daily traded value over the last 20 sessions in DKK (None without volumes)."""
    v = getattr(prices.market, "volumes", None)
    s = prices.dkk(t)
    if v is None or t not in v or s is None:
        return None
    x = (v[t].reindex(s.index) * s).dropna().iloc[-20:]
    return num(x.mean()) if len(x) else None


def _cost_one(prices: Prices, sf: fees.SimFees, t: str, amount: float, adv=None) -> float | None:
    """Round-trip cost share of putting `amount` DKK into `t` (fees both ways, FX surcharge, half-spread)."""
    adv = adv if adv is not None else adv_dkk(prices, t)
    if adv is None and t in look_through():
        adv = adv_dkk(prices, universe.benchmark())      # a world fund modelled with ACWI trades like it
    rate = prices.rate(t)
    if rate is None:
        tm = sf.terms(t, None, None, count=False)
        v = tm.value_for_budget(amount)
        return (2 * tm.fee(v)) / v if v > 0 else None
    tm = terms_for(prices, sf, t)
    v = tm.value_for_budget(amount / rate)
    hs = half_spread(adv)
    return (2 * tm.fee(v) + 2 * v * hs) / v if v > 0 else None


def evaluate(market, doc: dict, max_position: float | None = None, tolerance: float | None = None,
             offline: bool = False, light: bool = False) -> dict:
    """Everything the memo needs for a frozen picks file: sizing, constraints, exposures, risk, the drawdown three
    ways, the modelled return, the alternatives A0-A6 and the decision rule."""
    c = cfg()
    doc = _picks_doc(doc)
    m = doc.get("meta") or {}
    name, amount = m.get("portfolio"), float(m.get("amount") or 0)
    tilt, mode, horizon = m.get("tilt", "mix"), m.get("mode", "conviction"), int(m.get("horizon", 6))
    weighting = m.get("weighting", "equal")
    max_position = max_position if max_position is not None else m.get("max_position")
    if not name or amount <= 0:
        raise ValueError("the picks file needs meta.portfolio and meta.amount")
    ctx = context(market, name, offline)
    bench = universe.benchmark()
    tickers = [x["ticker"] for x in doc["picks"]]
    n = len(tickers)
    ticket = amount / n
    scored, excluded, raw = ranked_pool(ctx, tilt, ticket)
    for t in tickers:
        if t not in market.closes.columns:
            raise ValueError(f"{t}: no prices in the radar (not a tracked ticker)")
    frame = scored.reindex(tickers).combine_first(raw.reindex(tickers))
    frame = annotate(frame, info(tickers, ctx.prices))
    picks_list = [{"ticker": t} for t in tickers]
    sz = size(amount, picks_list, frame, ctx.prices, ctx.sf, weighting, c)
    fl_doc = doc.get("filler")
    fl = filler(sz["leftover_dkk"], ctx.portfolio["kind"], ctx.prices, ctx.sf, bool(fl_doc) or bool(m.get("etf", True)), c)
    vals = _values(ctx.holdings)
    new = {r["ticker"]: r["value_dkk"] for r in sz["rows"] if r["value_dkk"]}
    if fl and fl.get("value_dkk"):
        new[fl["ticker"]] = new.get(fl["ticker"], 0.0) + fl["value_dkk"]
    after = dict(vals)
    for t, v in new.items():
        after[t] = after.get(t, 0.0) + v
    every = list(dict.fromkeys([*after, *tickers, bench, *(scored.index[:60])]))
    meta = info(every, ctx.prices)
    weeks = c["history_weeks"]
    R = ctx.prices.weekly(every + [f for f in settings()["risk"]["factors"] if f in market.closes], weeks)
    cov = shrunk_cov(R.reindex(columns=[t for t in every if t in R]), c["shrink"], c["min_weeks"])

    # constraints
    base = _base(ctx, tickers)
    _, passed = select(frame.assign(composite=np.arange(n, 0, -1)), n, amount, base, c, "conviction", max_position)
    rule = m.get("rule_basket") or []
    swaps = [t for t in tickers if rule and t not in rule]
    cons = [{"check": "min ticket", "ok": all((r["budget_dkk"] or 0) >= c["min_ticket_dkk"] - 1 for r in sz["rows"]),
             "detail": f"{c['min_ticket_dkk']:,} DKK per name"},
            {"check": "sized", "ok": not sz["flags"], "detail": "; ".join(sz["flags"]) or "every pick has whole shares"},
            {"check": "caps (sector, region, currency, per sector, correlation, position)", "ok": not passed,
             "detail": "; ".join(f"{t}: {w}" for t, w in passed.items()) or "all within"},
            {"check": "swaps from the rule basket", "ok": len(swaps) <= c["max_swaps"],
             "detail": f"{len(swaps)} of at most {c['max_swaps']}" + (f" ({', '.join(swaps)})" if swaps else "")},
            {"check": "names in the gated pool", "ok": all(t in scored.index for t in tickers),
             "detail": "; ".join(f"{t}: {next((k for k, v in excluded.items() if t in v), 'not ranked')}"
                                 for t in tickers if t not in scored.index) or "all passed the gates"}]
    if ctx.portfolio["kind"] == "ask":
        fl_ask = [f"{t}: {ask_flag(t)}" for t in tickers if ask_flag(t)]
        cons.append({"check": "aktiesparekonto", "ok": not fl_ask and not (fl and fl.get("positive_list") == "no"),
                     "detail": "; ".join(fl_ask) or "no listing flags"})

    # the model
    sv = {h: study_view(load_study(), tilt, n, h, ctx.regime, c, ctx.trend) for h in c["horizons"]}
    cost_pct = sz["roundtrip_pct"]
    hv = sv.get(horizon) or study_view(load_study(), tilt, n, horizon, ctx.regime, c, ctx.trend)
    draws = 1000 if light else None
    prop = metrics(new, ctx, cov, R, horizon, hv["drift_gross"], cost_pct, c, vals, draws)
    st = stress(new, ctx.prices, bench, c)
    kept = (hv.get("kept") or {}).get("all") or {}
    lenses = {"study": {"median": kept.get("dd_median"), "p10": kept.get("dd_p10"), "dates": kept.get("dates")},
              "bootstrap": (prop["bootstrap"] or {}).get("max_dd"),
              "stress_worst": min((s["max_dd"] for s in st if s["max_dd"] is not None), default=None)}
    meds = [x for x in (lenses["study"]["median"], (lenses["bootstrap"] or {}).get("median")) if x is not None]
    bads = [x for x in (lenses["study"]["p10"], (lenses["bootstrap"] or {}).get("p10"), lenses["stress_worst"]) if x is not None]
    dd = {"expected": float(np.median(meds)) if meds else None, "bad_case": min(bads) if bads else None,
          "lenses": lenses, "note": "expected = the median of the study's and the bootstrap's median drawdown; bad case "
                                    "= the worst of their 10th percentiles and the worst stress window"}

    # alternatives
    alts = alternatives(ctx, scored, raw, tickers, amount, n, tilt, mode, weighting, max_position, horizon, cov, R,
                        vals, meta, c) if not light else {}
    decision = decide(prop, hv, dd, tolerance, c)
    pmeta = info(list(new), ctx.prices)
    # the rule study tests K+V on US stocks only (SEC EDGAR); outside the US only the factor-level prior speaks
    untested = sorted(t for t in tickers if (c["tilts"].get(tilt) or {}).get("qv", 0) > 0
                      and pmeta["region"].get(t, "us") != "us")
    if untested:
        ex = (((hv.get("prior") or {}).get("regions") or {}).get("world_ex_us") or {})
        ctx.notes.append(f"{', '.join(untested)}: outside the US, where the rule study never tested K+V; the only "
                         "evidence is JKP's factor-level prior ex US"
                         + (f" ({ex['mean']:+.1%} over {horizon} months, t {ex['t']:.1f})"
                            if ex.get("mean") is not None and ex.get("t") is not None else ""))
    return _clean({
        "portfolio": {"id": ctx.portfolio["id"], "name": name, "kind": ctx.portfolio["kind"], "mode": ctx.portfolio["mode"]},
        "asof": pd.Timestamp(market.closes.index[-1]).date().isoformat(), "picks_sha": picks_sha(doc),
        "meta": m, "regime": ctx.regime, "trend": ctx.trend, "notes": ctx.notes, "untested_kv": untested,
        "picks": [{**x, **{k: v for k, v in (next(r for r in sz["rows"] if r["ticker"] == x["ticker"])).items()},
                   "sector": pmeta["sector"].get(x["ticker"]), "region": pmeta["region"].get(x["ticker"]),
                   "momentum_score": num(frame.at[x["ticker"], "score"]) if "score" in frame else None,
                   "qv": num(frame.at[x["ticker"], "qv"]) if "qv" in frame else None,
                   "vol": num(frame.at[x["ticker"], "vol"]),
                   "contribution": prop["risk"]["contributions"].get(x["ticker"])} for x in doc["picks"]],
        "size": sz, "filler": fl, "constraints": cons,
        "exposure": {"before": exposures(vals, meta, ctx.acwi), "after": exposures(after, meta, ctx.acwi),
                     "basket": exposures(new, meta, ctx.acwi)},
        "factors": factors(new, R, market),
        "risk": {"basket": prop["risk"], "before": risk(vals, cov, bench) if vals else None, "after": prop["after"]},
        "model": {"horizon": horizon, "study": sv, "drift_gross": hv["drift_gross"], "cost_pct": cost_pct,
                  "drift_net": prop["drift_net"], "bootstrap": prop["bootstrap"],
                  "realised_dd_1y": prop["realised_dd_1y"], "realised_dd_3y": prop["realised_dd_3y"]},
        "drawdown": dd, "stress": st, "alternatives": alts, "decision": decision,
        "ask": ask_account(ctx, amount) if ctx.portfolio["kind"] == "ask" else None,
        "caveats": [
            "The expected excess comes from the rule study (the same rule on past month-ends), cut by a "
            "survivorship haircut and shrunk toward the long-run prior (JKP's survivorship-free tercile portfolios "
            "since prior.since); the picks' own past returns are not used: they were chosen for being high.",
            "The bootstrap and the stress windows describe risk, not a forecast; ACWI's drift is an assumption "
            f"({c['acwi_drift_annual']:.0%} a year).",
            "Returns are before tax. Spreads are estimates by liquidity bucket.",
        ],
    })


def factors(values: dict[str, float], R: pd.DataFrame, market) -> dict | None:
    from .signals import risk as rk

    bench = universe.benchmark()
    rp = series(values, R, bench)
    if rp is None or bench not in R:
        return None
    tilts = {f: R[f] for f in settings()["risk"]["factors"] if f in R}
    try:
        rf = market.fred().get("DGS3MO")
    except Exception:  # noqa: BLE001 - no FRED cache: raw returns
        rf = None
    return rk.factor_loadings(rp, R[bench], tilts, rf, cfg()["history_weeks"], cfg()["min_weeks"])


def decide(prop: dict, hv: dict, dd: dict, tolerance: float | None, c: dict) -> dict:
    """The pre-committed rule: stocks only if the modelled excess after costs beats ACWI by `min_edge`, the
    holdout agrees in sign, and the bad-case drawdown is within your tolerance."""
    net = prop["drift_net"]
    hold = ((hv.get("kept") or {}).get("holdout") or {})
    checks = {"edge": None if net is None else net > c["min_edge"],
              "holdout_sign": None if hold.get("gross_mean") is None else hold["gross_mean"] > 0,
              "drawdown": None if tolerance is None or dd["bad_case"] is None else dd["bad_case"] >= -abs(tolerance)}
    if net is None:
        verdict, why = "A0", "no evidence for an edge (the rule study is missing or stale): ACWI is the default"
    elif all(v is not False for v in checks.values()) and checks["edge"]:
        verdict, why = "stocks", "the modelled edge after costs clears the bar and nothing contradicts it"
    else:
        failed = [k for k, v in checks.items() if v is False]
        verdict, why = "A0", "fails: " + ", ".join(failed) + " (ACWI, or topping up / ETFs, is the disciplined choice)"
    return {"verdict": verdict, "why": why, "checks": checks, "min_edge": c["min_edge"], "tolerance": tolerance,
            "unchecked": [k for k, v in checks.items() if v is None]}


def alternatives(ctx: Ctx, scored: pd.DataFrame, raw: pd.DataFrame, tickers: list[str], amount: float, n: int,
                 tilt: str, mode: str,
                 weighting: str, max_position, horizon: int, cov: pd.DataFrame, R: pd.DataFrame,
                 vals: dict[str, float], meta: pd.DataFrame, c: dict) -> dict:
    """A0-A6 on the same metrics."""
    bench = universe.benchmark()
    study = load_study()
    out = {}

    def rec(label: str, values: dict, drift, cost, tests: str, extra: dict | None = None, draws: int = 2000):
        missing = [t for t in values if t not in cov.index and t not in look_through()]
        if missing:
            more = ctx.prices.weekly(missing, c["history_weeks"])
            R2 = pd.concat([R, more], axis=1)
            cv = shrunk_cov(R2.reindex(columns=[x for x in dict.fromkeys([*cov.index, *missing]) if x in R2]),
                            c["shrink"], c["min_weeks"])
        else:
            R2, cv = R, cov
        mt = metrics(values, ctx, cv, R2, horizon, drift, cost, c, vals, draws)
        return {"label": label, "tests": tests, "values": values, **mt, **(extra or {})}

    a0_cost = _cost_one(ctx.prices, ctx.sf, (c.get("etf_filler") or {}).get("ticker") or bench, amount)
    out["A0"] = rec("ACWI UCITS for the whole amount", {bench: amount}, 0.0, a0_cost,
                    "the null: every proposal must beat it")
    chosen, _, sz = rule_basket(ctx, scored, amount, n, mode, max_position, weighting)
    rv = study_view(study, tilt, n, horizon, ctx.regime, c, ctx.trend)
    out["A1"] = rec("The rule-only basket (no judgment)", {r["ticker"]: r["value_dkk"] for r in sz["rows"] if r["value_dkk"]},
                    rv["drift_gross"], sz["roundtrip_pct"], "whether the judgment's swaps add anything",
                    {"tickers": [x["ticker"] for x in chosen]})
    for other in [t for t in TILTS if t != tilt]:
        sc, _, _ = ranked_pool(ctx, other, amount / n, raw=raw)
        ch, _, szo = rule_basket(ctx, sc, amount, n, mode, max_position, weighting)
        ov = study_view(study, other, n, horizon, ctx.regime, c, ctx.trend)
        out[f"A2-{other}"] = rec(f"The rule basket with the {other} tilt", {r["ticker"]: r["value_dkk"] for r in szo["rows"]
                                                                          if r["value_dkk"]},
                                 ov["drift_gross"], szo["roundtrip_pct"], "whether the tilt matters today",
                                 {"tickers": [x["ticker"] for x in ch]})
    frontier = []
    for k in range(1, n_for(amount, c) + 1):
        ch, _, szk = rule_basket(ctx, scored, amount, k, mode, max_position, weighting)
        v = {r["ticker"]: r["value_dkk"] for r in szk["rows"] if r["value_dkk"]}
        rk_ = risk(v, cov if all(t in cov.index for t in v) else shrunk_cov(
            pd.concat([R, ctx.prices.weekly([t for t in v if t not in R], c["history_weeks"])], axis=1),
            c["shrink"], c["min_weeks"]), bench)
        kv = study_view(study, tilt, k, horizon, ctx.regime, c, ctx.trend)
        frontier.append({"n": k, "tickers": [x["ticker"] for x in ch], "cost_pct": szk["roundtrip_pct"],
                         "vol_ann": rk_["vol_ann"], "te_ann": rk_["te_ann"], "drift_gross": kv["drift_gross"],
                         "study_n": kv["n_used"]})
    knee = next((f["n"] for f, g in zip(frontier, frontier[1:]) if f["vol_ann"] is not None and g["vol_ann"] is not None
                 and f["vol_ann"] - g["vol_ann"] < c["frontier_knee"]), frontier[-1]["n"] if frontier else None)
    out["A3"] = {"label": "Basket size: fewer or more names for the same amount", "tests": "diversification vs fee drag",
                 "frontier": frontier, "knee": knee}
    stocks = {t: v for t, v in vals.items() if t not in look_through()}
    tot = sum(stocks.values())
    if tot > 0:
        top = {t: amount * v / tot for t, v in stocks.items()}
        costs = [(_cost_one(ctx.prices, ctx.sf, t, a) or 0) * a for t, a in top.items()]
        out["A4"] = rec("Top up current holdings pro rata", top, None, sum(costs) / amount,
                        "no new names, no new research (no study drift: n/a)",
                        {"tickets_below_min": sum(a < c["min_ticket_dkk"] for a in top.values())})
    else:
        out["A4"] = {"label": "Top up current holdings pro rata", "tests": "no new names", "note": "nothing held to top up"}
    etf_of = {}
    for t in tickers:
        reg = "europe" if meta["region"].get(t) in ("europe", "nordic") else "us"
        se = ((universe_config().get("sector_etfs") or {}).get(reg) or {}).get(meta["sector"].get(t))
        etf_of[t] = se if isinstance(se, str) else bench
    a5: dict[str, float] = {}
    for t in tickers:
        a5[etf_of[t]] = a5.get(etf_of[t], 0.0) + amount / len(tickers)
    out["A5"] = rec("Sector ETFs with the basket's sector mix", a5, None,
                    float(np.mean([_cost_one(ctx.prices, ctx.sf, t, v) or 0 for t, v in a5.items()])),
                    "whether picking stocks adds anything beyond the exposure (US/EU sector ETFs as proxies: buy "
                    "UCITS equivalents)", {"map": etf_of})
    out["A6"] = randoms(scored, tickers, amount, n, ctx, cov, R, vals, c)
    return out


def randoms(scored: pd.DataFrame, tickers: list[str], amount: float, n: int, ctx: Ctx, cov: pd.DataFrame,
            R: pd.DataFrame, vals: dict[str, float], c: dict, draws: int = 300) -> dict:
    """Random baskets of the same size from the gated pool under the same caps: where the proposal's ex-ante
    volatility, tracking error and diversification ratio sit among them."""
    bench = universe.benchmark()
    pool_ = [t for t in scored.index if t in cov.index]
    if len(pool_) < n * 2:
        return {"label": "Random baskets", "note": "too few names with a return history in the pool"}
    rng = np.random.default_rng(int(c["bootstrap"]["seed"]))
    base = _base(ctx, pool_)
    stats = {"vol_ann": [], "te_ann": [], "div_ratio": []}
    for _ in range(draws):
        order = scored.loc[pool_].iloc[rng.permutation(len(pool_))].assign(composite=np.arange(len(pool_), 0, -1))
        ch, _ = select(order, n, amount, base, c)
        if len(ch) < n:
            continue
        r = risk({x["ticker"]: amount / n for x in ch}, cov, bench)
        for k in stats:
            if r[k] is not None:
                stats[k].append(r[k])
    me = risk({t: amount / n for t in tickers}, cov, bench)
    out = {"label": "Random baskets of the same size and caps", "tests": "where the proposal sits among chance",
           "draws": len(stats["vol_ann"]), "seed": int(c["bootstrap"]["seed"])}
    for k, v in stats.items():
        if v and me[k] is not None:
            a = np.array(v)
            out[k] = {"proposal": me[k], "median": float(np.median(a)), "percentile": float((a < me[k]).mean() * 100)}
    return out


# ---------------- frozen proposals: shadow, review, check ----------------

def save_picks(doc: dict) -> str:
    """Write a picks file into exports/proposals/ (frozen: stamped once)."""
    doc = _picks_doc(doc)
    m = doc["meta"]
    if not m.get("portfolio") or not m.get("date"):
        raise ValueError("the picks file needs meta.portfolio and meta.date")
    if not m.get("frozen_at"):
        m["frozen_at"] = pd.Timestamp.now().isoformat(timespec="seconds")
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    stem = f"{m['date']}_{slug(m['portfolio'])}"
    f, k = PROPOSALS / f"{stem}.json", 1
    while f.exists():                              # a frozen proposal is never overwritten
        k += 1
        f = PROPOSALS / f"{stem}-{k}.json"
    write_text(f, json.dumps(doc, indent=1, ensure_ascii=False, default=str))
    return str(f)


def evaluation_file(fname: str):
    return PROPOSALS / fname.replace(".json", "-evaluation.json")


def save_evaluation(fname: str, ev: dict) -> str:
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    f = evaluation_file(fname)
    write_text(f, json.dumps(ev, indent=1, ensure_ascii=False, default=str))
    return str(f)


def _band(fname: str) -> list[float] | None:
    """The modelled drawdown band [bad case, expected] from a proposal's saved evaluation."""
    f = evaluation_file(fname)
    try:
        dd = json.loads(f.read_text(encoding="utf-8")).get("drawdown") or {}
    except (FileNotFoundError, ValueError):
        return None
    return [dd["bad_case"], dd["expected"]] if dd.get("bad_case") is not None else None


def proposals() -> list[tuple[str, dict]]:
    """Every frozen picks file, oldest first."""
    if not PROPOSALS.exists():
        return []
    out = []
    for f in sorted(PROPOSALS.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if d.get("type") == "propose-picks" and (d.get("meta") or {}).get("frozen_at"):
            out.append((f.name, d))
    return out


def shadow(market, doc: dict, name: str) -> dict:
    """Virtual copies of the portfolio at the latest close plus the amount: the proposal, ACWI (A0) and the rule
    basket (A1), tagged proposal and proposal-<date>. Never touches a real portfolio."""
    from . import simulate

    doc = _picks_doc(doc)
    m = doc["meta"]
    src = userstore.portfolio_by_name(m["portfolio"])
    if not src:
        raise ValueError(f"no portfolio called {m['portfolio']}")
    names = {"proposal": name, "acwi": f"{name} · ACWI", "rule": f"{name} · rule"}
    for v in names.values():
        if userstore.portfolio_by_name(v):
            raise ValueError(f"there is already a portfolio called {v}: shadows are new, virtual portfolios")
    prices = Prices(market)
    sf = fees.SimFees.for_portfolio(src, float((settings().get("backtest") or {}).get("fee_bps", 0)))
    day = pd.Timestamp(market.closes.index[-1])
    tags = ["proposal", f"proposal-{m['date']}"]
    amount = float(m["amount"])
    rule = m.get("rule_basket") or []
    arms = {"proposal": [x["ticker"] for x in doc["picks"]], "acwi": [universe.benchmark()], "rule": rule}
    ids = {}
    for arm, ticks in arms.items():
        if not ticks:
            continue
        pid = simulate.fork(src["id"], names[arm], day, market, amount, tags)
        for t in ticks:
            px, rate = prices.last_px(t), prices.rate(t)
            if px is None or rate is None:
                continue
            tm = terms_for(prices, sf, t)
            qty = tm.value_for_budget(amount / len(ticks) / rate) / px
            if arm != "acwi":
                qty = math.floor(qty)
            if qty <= 0:
                continue
            userstore.add_tx({"symbol": t, "date": day.date().isoformat(), "type": "BUY", "quantity": qty, "price": px,
                              "fee": tm.fee(qty * px), "fx_rate": rate, "portfolio_id": pid,
                              "note": f"proposal {m['date']} ({arm})"}, source="fork")
        p = userstore.get_portfolio(pid)
        userstore.save_portfolio({"params": (p.get("params") or {}) | {"proposal": {
            "date": m["date"], "arm": arm, "tickers": ticks, "amount": amount, "picks_sha": picks_sha(doc)}}}, pid)
        ids[arm] = pid
    return {"ids": ids, "names": {k: names[k] for k in ids}, "tags": tags,
            "returns_link": f"/returns?pf={','.join(str(v) for v in ids.values())}&from={day.date().isoformat()}"}


def _basket_path(prices: Prices, tickers: list[str], start: pd.Timestamp, sma: int | None = None) -> dict:
    """Equal DKK weights bought at the close of `start`: kept, and with the trend exit (model.paths: a close below
    the average after the buy day, sold at the next close, parked in ACWI)."""
    bench = universe.benchmark()
    b = prices.dkk(bench)
    legs, legs_x, events = [], [], []
    for t in tickers:
        s = prices.dkk(t)
        if s is None or s.loc[start:].empty:
            continue
        w = s.loc[start:]
        leg = w / w.iloc[0]
        legs.append(leg)
        if sma and t in prices.market.closes:
            below = mpaths.below_trend(prices.market.closes[t], sma).reindex(w.index, fill_value=False)
            k = mpaths.exit_session(w.index, below)
            if k is not None:
                kd = w.index[k]
                legs_x.append(mpaths.park(leg, kd, b.reindex(w.index).ffill()))
                events.append({"ticker": t, "date": kd.date().isoformat()})
                continue
        legs_x.append(leg)
    if not legs:
        return {}
    v = pd.concat(legs, axis=1).ffill().mean(axis=1)
    vx = pd.concat(legs_x, axis=1).ffill().mean(axis=1)
    bi = b.loc[start:] / b.loc[start:].iloc[0] if b is not None else None
    return {"ret": float(v.iloc[-1] - 1), "max_dd": float((v / v.cummax() - 1).min()),
            "exits_ret": float(vx.iloc[-1] - 1), "exits": events,
            "acwi": float(bi.iloc[-1] - 1) if bi is not None and len(bi) else None, "days": int(len(v) - 1)}


def review(market) -> dict:
    """How each frozen proposal did since its day, against ACWI, its rule basket and its own modelled range."""
    c = cfg()
    prices = Prices(market)
    st = settings()["stops"]
    rows = []
    for fname, d in proposals():
        m = d["meta"]
        start = pd.Timestamp(m["date"])
        if start >= market.closes.index[-1]:
            rows.append({"file": fname, "date": m["date"], "portfolio": m["portfolio"], "note": "no prices since yet"})
            continue
        ticks = [x["ticker"] for x in d["picks"]]
        mine = _basket_path(prices, ticks, start, st["trend_sma"])
        rule = _basket_path(prices, m.get("rule_basket") or [], start) if m.get("rule_basket") else {}
        band = _band(fname)
        rows.append({"file": fname, "date": m["date"], "portfolio": m["portfolio"], "tilt": m.get("tilt"),
                     "tickers": ticks, "days": mine.get("days"), "ret": mine.get("ret"), "acwi": mine.get("acwi"),
                     "excess": None if mine.get("ret") is None or mine.get("acwi") is None else mine["ret"] - mine["acwi"],
                     "rule_ret": rule.get("ret"), "judgment_vs_rule": None if not rule or mine.get("ret") is None
                     else mine["ret"] - rule["ret"], "max_dd": mine.get("max_dd"), "modelled_dd": band,
                     "dd_inside_band": None if not band or mine.get("max_dd") is None else mine["max_dd"] >= band[0],
                     "exits_ret": mine.get("exits_ret"), "exits_vs_kept": None if mine.get("exits_ret") is None
                     else mine["exits_ret"] - mine["ret"], "exit_events": mine.get("exits")})
    judged = [r for r in rows if r.get("excess") is not None]
    return _clean({"proposals": rows, "count": len(judged), "enough": len(judged) >= c["review_min"],
                   "summary": {"mean_excess": float(np.mean([r["excess"] for r in judged])) if judged else None,
                               "beat_acwi": float(np.mean([r["excess"] > 0 for r in judged])) if judged else None,
                               "mean_judgment_vs_rule": _mean([r.get("judgment_vs_rule") for r in judged]),
                               "dd_inside_band": _mean([r.get("dd_inside_band") for r in judged]),
                               "mean_exits_vs_kept": _mean([r.get("exits_vs_kept") for r in judged])},
                   "note": None if len(judged) >= c["review_min"] else
                   f"{len(judged)} proposal(s) with a result: fewer than {c['review_min']} say nothing about the method yet"})




def check(market, portfolio: str | None = None) -> dict:
    """Each open proposal's exit criteria today: Intact, Weakening or Triggered, with the evidence."""
    from .model import panels as mp

    c = cfg()
    prices = Prices(market)
    st = settings()["stops"]
    p = mp.panels(market)
    pl = pool(market, prices, p)
    exit_run = max((r.report.created for r in (artifacts.load("exit-study"), artifacts.load("redeploy-study"))
                    if r.report is not None), default=None)
    today = pd.Timestamp(market.closes.index[-1])
    out = []
    for fname, d in proposals():
        m = d["meta"]
        if portfolio and m.get("portfolio") != portfolio:
            continue
        held = None
        pf = userstore.portfolio_by_name(m["portfolio"])
        if pf:
            pos, _ = universe.positions(universe.transactions([pf["id"]]))
            held = set(pos[pos["status"] == "holding"]["symbol"]) if not pos.empty else set()
        older = []
        if m.get("settings_hash") and m["settings_hash"] != rule_hash():
            older.append("the proposal rule's settings have changed since")
        if m.get("stops") and m["stops"] != st:
            older.append("settings.stops have changed since")
        if exit_run and pd.Timestamp(exit_run) > pd.Timestamp(m.get("frozen_at") or m["date"]):
            older.append("the exit study was re-run since")
        names = []
        for x in d["picks"]:
            t = x["ticker"]
            ex = x.get("exit") or default_exit(m.get("tilt", "mix"), m["date"], int(m.get("horizon", 6)))
            items = []
            cl = market.closes[t].dropna() if t in market.closes else pd.Series(dtype=float)
            sma = int((ex.get("review_level") or {}).get("sma") or st["trend_sma"])
            if len(cl) >= sma:
                lvl = float(mpaths.trend_level(cl, sma).iloc[-1])
                gap = float(cl.iloc[-1] / lvl - 1)
                items.append({"criterion": f"close vs {sma}-day average", "value": gap,
                              "status": "triggered" if gap < 0 else "weakening" if gap < c["exit"]["weakening"] else "intact"})
            else:
                items.append({"criterion": f"close vs {sma}-day average", "value": None, "status": "unknown"})
            sig = ex.get("signal") or {}
            if sig.get("metric"):
                col = "score" if sig["metric"] == "score" else sig["metric"]
                v = num(pl.at[t, col]) if t in pl.index and col in pl else None
                lim = float(sig["below"])
                items.append({"criterion": f"{sig['metric']} below {lim:g}", "value": v,
                              "status": "unknown" if v is None else "triggered" if v < lim else
                              "weakening" if v < lim + 5 else "intact"})
            for th in ex.get("thesis") or []:
                if th.get("metric") and th.get("op") in ("<", ">") and th.get("value") is not None:
                    col = th["metric"]
                    v = num(pl.at[t, col]) if t in pl.index and col in pl else None
                    bad = None if v is None else (v < th["value"] if th["op"] == "<" else v > th["value"])
                    items.append({"criterion": th.get("text") or f"{col} {th['op']} {th['value']}", "value": v,
                                  "status": "unknown" if bad is None else "triggered" if bad else "intact"})
                else:
                    items.append({"criterion": th.get("text"), "value": None, "status": "manual"})
            ts = ex.get("time_stop")
            days = (pd.Timestamp(ts) - today).days if ts else None
            if ts:
                items.append({"criterion": f"time stop {ts}", "value": days,
                              "status": "triggered" if days is not None and days <= 0 else "intact"})
            stt = [i["status"] for i in items]
            status = "Triggered" if "triggered" in stt else "Weakening" if "weakening" in stt else "Intact"
            names.append({"ticker": t, "held": None if held is None else t in held, "status": status, "items": items,
                          "days_to_time_stop": days})
        start = pd.Timestamp(m["date"])
        path = _basket_path(prices, [x["ticker"] for x in d["picks"]], start) if start < today else {}
        band = _band(fname)
        basket = {"max_dd": path.get("max_dd"), "bad_case": band[0] if band else None,
                  "status": None if not band or path.get("max_dd") is None else
                  "Triggered" if path["max_dd"] < band[0] else "Intact"}
        out.append({"file": fname, "date": m["date"], "portfolio": m["portfolio"], "older_rule": older,
                    "names": names, "basket": basket})
    return _clean({"asof": today.date().isoformat(), "proposals": out})

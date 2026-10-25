"""The portfolio X-ray: what a selection of portfolios is exposed to and where its risk sits, against ACWI, in DKK.

It assembles the shared engine (portfolios/exposure.py, portfolios/riskmodel.py, the same code proposals use) for
the holdings of one or more portfolios: the book and its cash, each name's class, exposures with coverage, the
ex-ante risk of today's weights with each position's share of total and active risk, the realised figures of
what was actually held, concentration, the stress windows and the factor tilts. No math of its own. Computed live
(the X-ray follows your edits), nothing written. Analysis, not advice."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import pandas as pd

from . import userstore
from .config import typed
from .portfolios import exposure, performance, riskmodel
from .portfolios.prices import Prices
from .sources import constituents, external, tracked
from .values import num

if TYPE_CHECKING:
    from .market import Market

REALISED_DAYS = 365
_cache: dict[tuple, dict] = {}


def _book(market: Market, prices: Prices, ids: list[int]) -> tuple[dict[str, float], list[dict]]:
    """DKK value per held symbol (summed over the portfolios), and the positions without a DKK value."""
    book = exposure.holdings_book(market, prices, ids)
    values: dict[str, float] = {}
    unvalued = []
    for _, r in book.iterrows():
        if r["value_dkk"] is None or pd.isna(r["value_dkk"]):
            unvalued.append({"symbol": r["symbol"], "quantity": float(r["quantity"]),
                             "reason": "no price" if r["price"] is None or pd.isna(r["price"]) else "no DKK rate"})
        else:
            values[r["symbol"]] = values.get(r["symbol"], 0.0) + float(r["value_dkk"])
    return values, unvalued


def _cash(market: Market, ports: list[dict], notes: list[str]) -> float | None:
    """The cash of the portfolios that keep a ledger, summed; None when none does. The others are named."""
    total, ledger, implicit = 0.0, False, []
    for p in ports:
        rows = userstore.transactions(portfolios=[p["id"]])
        if not rows:
            continue
        if not performance.has_ledger(rows):
            implicit.append(p["name"])
            continue
        s, problems = performance.cash_balance(rows, market, p["dividends"])
        ledger = True
        if problems:
            notes.append(f"{p['name']}: {len(problems)} cash row(s) without a DKK rate are left out of its cash")
        if len(s):
            total += float(s.iloc[-1])
    if implicit:
        notes.append(f"No cash ledger for {', '.join(implicit)}: its cash is unknown and not shown")
    return total if ledger else None


def _exposure(ex: dict, acwi: dict | None) -> dict:
    """Per dimension: rows of key, weight, ACWI's weight and the active weight (real keys only), sorted by the
    size of the active weight, then the weight; and the coverage."""
    out = {}
    for d in exposure.DIMS:
        w = ex["weights"][d]
        active = (ex["active"] or {}).get(d) or {}
        keys = set(w) | (set(active) if acwi else set())
        rows = [{"key": k, "weight": w.get(k, 0.0), "acwi": (acwi[d].get(k, 0.0) if acwi and k in active else None),
                 "active": active.get(k)} for k in keys]
        rows.sort(key=lambda r: (-abs(r["active"]) if r["active"] is not None else 1, -r["weight"], r["key"]))
        cov = ex["coverage"][d]
        out[d] = {"rows": rows, "coverage": cov,
                  "note": None if cov is None or cov >= 1 - 1e-9 else
                  f"{1 - cov:.0%} of the value can't be placed by {d} (funds not looked through, or unknown)"}
    return out


def _realised(market: Market, ports: list[dict]) -> tuple[float | None, float | None]:
    """Volatility and the deepest drawdown of the time-weighted index of what was actually held, last year."""
    b = performance.pool([performance.portfolio_book(p, market) for p in ports])
    if b is None:
        return None, None
    start = market.closes.index[-1] - pd.Timedelta(days=REALISED_DAYS)
    stats = performance.analyze(b, market, start)["stats"] or {}
    return stats.get("vol_ann"), stats.get("max_drawdown")


def _risk(values: dict[str, float], cov: pd.DataFrame, bench: str, realised: tuple, notes: list[str]) -> dict | None:
    """Ex-ante risk of today's weights with the per-position shares, under the coverage rules."""
    xc = typed().risk.xray
    cv = typed().risk.covariance
    r = riskmodel.ex_ante_risk(values, cov, bench)
    coverage = r["coverage"]
    total = sum(values.values())
    excluded = [{"symbol": t, "weight": values.get(t, 0.0) / total if total > 0 else None,
                 "reason": f"fewer than {cv.min_weeks} weeks of prices"} for t in r["missing"]]
    if coverage is None or coverage < xc.min_coverage or r["vol_ann"] is None:
        share = "none" if coverage is None else f"{coverage:.0%}"
        notes.append(f"Risk figures not shown: {share} of the invested value is in the risk model "
                     f"(at least {xc.min_coverage:.0%} is needed)")
        return None
    w, _, _ = riskmodel.model_weights(values, cov, bench)
    mctr = riskmodel.mctr(w, cov)
    active = riskmodel.active_contributions(w, cov, bench)
    positions = [{"symbol": t, "weight": float(w[t]), "share_total": r["contributions"].get(t),
                  "share_active": active.get(t) if t != bench else None, "mctr_ann": num(mctr.get(t))}
                 for t in w.index]
    positions.sort(key=lambda p: -(p["share_total"] or 0))
    warn = coverage < xc.warn_coverage
    if warn:
        notes.append(f"Only {coverage:.0%} of the invested value is in the risk model: the risk figures describe that "
                     "part")
    return {"vol_ann": r["vol_ann"], "beta": r["beta"], "te_ann": r["te_ann"], "div_ratio": r["div_ratio"],
            "coverage": coverage, "warn": warn, "realised_vol_1y": realised[0], "realised_max_dd_1y": realised[1],
            "positions": positions, "acwi_leg_share_active": active.get(bench), "excluded": excluded,
            "window_weeks": cv.history_weeks, "shrink": cv.shrink}


def cached(market: Market, ids: list[int] | None = None, scope: str | None = None) -> dict:
    """`build`, kept until a trade or portfolio edit, a price update or a newly cached fund detail changes it."""
    ids = userstore.portfolio_ids() if ids is None else ids
    d = external.PROFILE_DIR
    key = (tuple(ids), scope, market.mtime, userstore.transactions_version(), d.stat().st_mtime if d.exists() else 0)
    if key not in _cache:
        if len(_cache) > 32:
            _cache.clear()
        _cache[key] = build(market, ids, scope)
    return _cache[key]


def build(market: Market, ids: list[int] | None = None, scope: str | None = None) -> dict:
    """The X-ray of these portfolios (None: your real ones)."""
    ids = userstore.portfolio_ids() if ids is None else ids
    ports = [p for p in (userstore.get_portfolio(i) for i in ids) if p]
    notes: list[str] = []
    prices = Prices(market)
    bench = tracked.benchmark()
    values, unvalued = _book(market, prices, [p["id"] for p in ports])
    if unvalued:
        notes.append(f"No DKK value for {', '.join(u['symbol'] for u in unvalued)}: left out of every weight")
    cash = _cash(market, ports, notes)
    invested = sum(values.values())
    acwi = constituents.acwi_weights(offline=True)
    meta = exposure.ticker_meta(list(values), prices)
    ex = exposure.exposures(values, meta, acwi)
    if ex["note"]:
        notes.append(ex["note"])
    classes = [{"symbol": t, "class": meta.at[t, "class"], "value_dkk": v, "weight": v / invested,
                "detail_asof": meta.at[t, "detail_asof"]} for t, v in sorted(values.items(), key=lambda kv: -kv[1])]
    unknown = [c["symbol"] for c in classes if c["class"] == "unknown"]
    if unknown:
        notes.append(f"{', '.join(unknown)}: neither a known fund nor a stock with a sector. Opening its profile "
                     "caches Yahoo's fund data, so a fund can be looked through next time")

    rc = typed().risk
    risk: dict[str, Any] | None = None
    conc: dict[str, Any] = riskmodel.concentration(values)
    pairs: list[dict] = []
    stress: list[dict] = []
    factors = None
    if values:
        factor_cols = [f for f in rc.factors if f in market.closes]
        R = prices.weekly(list(dict.fromkeys([*values, bench, *factor_cols])), rc.covariance.history_weeks)
        cov = riskmodel.book_cov(values, R, bench)
        risk = _risk(values, cov, bench, _realised(market, ports), notes)
        conc = riskmodel.concentration(values, {p["symbol"]: p["share_total"] for p in risk["positions"]
                                                if p["share_total"] is not None} if risk else None)
        pairs = riskmodel.correlated_pairs(values, R)
        stress = riskmodel.stress(values, prices, bench)
        factors = riskmodel.factor_tilts(values, R, market)
        if factors is not None:
            notes.append("Factor tilts are a regression on US factor ETFs (as spreads over ACWI): descriptive, "
                         "not a forecast")
        if conc["world_fund_weight"]:
            notes.append("A world fund counts as one position in the concentration figures, which understates how "
                         "spread out it is")
    else:
        notes.append("No valued holdings in this selection")
    if cash is not None and cash < 0:
        notes.append("The cash ledger is negative: more was bought than paid in")
    asof = market.closes[bench].dropna().index[-1].date().isoformat() if bench in market.closes else None
    return {
        "asof": asof, "generated": datetime.now().isoformat(timespec="seconds"),
        "selection": {"ids": [p["id"] for p in ports], "names": [p["name"] for p in ports], "scope": scope},
        "totals": {"invested_dkk": invested, "cash_dkk": cash, "unvalued": unvalued},
        "exposure": _exposure(ex, acwi), "classes": classes, "risk": risk,
        "concentration": conc | {"pairs": pairs}, "stress": stress, "factors": factors, "notes": notes,
    }

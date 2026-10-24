"""Kvalitetsscore and værdiscore: a business's quality and its price, from its financial statements (pure functions).

`metrics` gives one stock's quality metrics (four pillars) and value metrics from one source's facts
(fundamentals/store.py) and its market value, with their own sets for banks and insurers (`QUALITY`, `VALUE`);
`score` turns them into percentiles among peers and the scores. The method: guide/laerebog/kvalitetsscore.md.
"""
from __future__ import annotations

import math
from datetime import timedelta

import numpy as np
import pandas as pd

from ..values import num
from . import periods

QUALITY: dict[str, dict[str, tuple[str, ...]]] = {
    "standard": {"profitability": ("fcf_margin", "roic"), "durability": ("gm_stability", "rev_stability"),
                 "balance": ("nd_ebitda", "interest_cover"), "record": ("div_years",)},
    "financial": {"profitability": ("roe",), "durability": ("roe_stability",), "balance": ("equity_assets",),
                  "record": ("div_years",)},
}
VALUE = {"standard": ("fcf_yield", "ebit_ev", "shareholder_yield", "ey_vs_history"),
         "financial": ("bp", "ep", "shareholder_yield", "ep_vs_history")}
LOWER_BETTER = {"gm_stability", "roe_stability", "nd_ebitda"}
PILLARS = ("profitability", "durability", "balance", "record")
ALL_METRICS = sorted({m for s in QUALITY.values() for ms in s.values() for m in ms} | {m for s in VALUE.values()
                                                                                    for m in s})


def _v(x) -> float | None:
    return None if x is None else num(x.value)


def is_financial(industry: str | None, financial_industries) -> bool:
    return bool(industry) and industry in set(financial_industries)


# ---------------- metrics per stock ----------------

def _fresh(v: periods.Value | None, asof: pd.Timestamp, days: int) -> periods.Value | None:
    return v if v is not None and (asof - v.end).days <= days else None


def _years(series: pd.Series, asof: pd.Timestamp, n: int, max_age: int) -> pd.Series:
    """The last `n` fiscal years, when the latest isn't older than `max_age` days."""
    if series.empty or (asof - series.index.max()).days > max_age:
        return pd.Series(dtype="float64")
    return series.sort_index().tail(n)


def _trend(rev: pd.Series) -> tuple[float | None, float | None]:
    """(sign of the trend × R² of log revenue on time, yearly growth first to last year)."""
    if len(rev) < 2 or (rev <= 0).any():
        return None, None
    t = np.array([(d - rev.index[0]).days / 365.25 for d in rev.index])
    y = np.log(rev.to_numpy(dtype=float))
    cagr = float(math.exp((y[-1] - y[0]) / t[-1]) - 1) if t[-1] > 0 else None
    if np.ptp(y) == 0:
        return 0.0, cagr
    slope, icpt = np.polyfit(t, y, 1)
    r2 = 1 - ((y - (slope * t + icpt)) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return float(np.sign(slope) * max(r2, 0.0)), cagr


def dividend_years(dps: dict[int, float] | None, last_year: int, cap: int = 10) -> int | None:
    """Years in a row up to `last_year` with a dividend at least 95% of the year before; 0 for a non-payer (or a
    cut in `last_year`); None without data. The first year of the record counts when paid (nothing to compare)."""
    if not dps or last_year not in dps:
        return None
    n, y = 0, last_year
    while y in dps and dps[y] > 0 and n < cap:
        if y - 1 in dps and dps[y] < 0.95 * dps[y - 1]:
            break                                   # a cut: this year ends the streak
        n += 1
        y -= 1
    return n


def dps_by_year(adj: pd.Series, raw: pd.Series, min_share: float = 0.0005) -> dict[int, float]:
    """Dividends per share per complete calendar year, read from adjusted and traded closes: on an ex-date the
    adjustment factor (adjusted / traded) steps, by the dividend over the close before. Steps under `min_share` of
    the price are rounding. Years at the edges of the history (incomplete) are left out."""
    df = pd.DataFrame({"adj": adj, "raw": raw}).dropna()
    df = df[(df["raw"] > 0) & (df["adj"] > 0)]
    if len(df) < 30:
        return {}
    f = df["adj"] / df["raw"]
    step = 1 - f.shift(1) / f
    d = (df["raw"].shift(1) * step).where(step > min_share, 0.0).fillna(0.0)
    years = d.groupby(d.index.year).sum()
    first, last = df.index.min(), df.index.max()
    full = [y for y in years.index if pd.Timestamp(f"{y}-01-07") >= first and pd.Timestamp(f"{y}-12-24") <= last]
    return {int(y): float(years[y]) for y in full}


def metrics(facts: pd.DataFrame, asof, cfg: dict, financial: bool, mcap: float | None,
            price_on=None, dps: dict[int, float] | None = None, known_by=None) -> dict:
    """One stock's metrics. `price_on(day)` gives the share price in the reporting currency on a day (for the
    value metrics' own history), `mcap` today's market value in the reporting currency. Returns {"values": what
    is shown, "rank": oriented so higher is better, "notes", "period_end", "basis"}."""
    asof = pd.Timestamp(asof)
    facts, known_by = periods.view(facts, known_by), None     # resolved once: every lookup below reads the view
    notes: list[str] = []
    rng = cfg.get("ranges") or {}
    ttm_age, fy_age = cfg["ttm_max_age_days"], cfg["annual_max_age_days"]

    def ttm(item: str) -> periods.Value | None:
        return _fresh(periods.ttm(facts, item, known_by), asof, ttm_age)

    def bal(item: str, on=None) -> periods.Value | None:
        v = periods.instant(facts, item, known_by, on)
        return v if on is not None else _fresh(v, asof, ttm_age)

    def annual(item):
        return _years(periods.annual(facts, item, known_by), asof, cfg["stability_years"], fy_age)

    rev, ebit, cfo, capex = ttm("revenue"), ttm("operating_income"), ttm("cfo"), ttm("capex")
    ni, pretax, tax, dna, interest = ttm("net_income"), ttm("pretax"), ttm("income_tax"), ttm("dna"), ttm("interest")
    assets, cl, cash = bal("total_assets"), bal("current_liabilities"), bal("cash")
    equity = bal("equity")
    latest = periods.latest_end(facts, known_by)
    if rev is None and latest is not None and (asof - latest).days > ttm_age:
        notes.append(f"latest report ends {latest:%d %b %Y}, more than {ttm_age} days ago: left out")
    debt_parts = [bal("debt_current"), bal("debt_noncurrent")]
    debt = _debt(facts, debt_parts) if assets is not None else None
    if assets is not None:
        if debt is None:
            notes.append("debt reported before but not on the latest balance sheet: net debt, interest cover and "
                         "EV left out")
        elif all(_v(x) is None for x in debt_parts):
            notes.append("no debt line in any report: counted as no debt")
    debt_c = _v(debt_parts[0]) or 0.0
    cash_v = _v(cash)
    other = sum(_v(bal(i)) or 0.0 for i in ("minority", "preferred"))

    vals: dict[str, float | None] = {m: None for m in ALL_METRICS}
    nd_rank: float | None = None   # what nd_ebitda ranks by: net cash ties as best, debt without EBITDA as worst
    vals |= {"rev_cagr": None, "ev_ebit": None, "pe": None, "pb": None, "fcf": None, "ebitda": None}

    def check(key, v):
        lo_hi = rng.get(key)
        if v is not None and lo_hi and not lo_hi[0] <= v <= lo_hi[1]:
            notes.append(f"{key} {v:.3g} outside {lo_hi[0]}–{lo_hi[1]}: left out")
            return None
        return v

    # --- quality (each value read once: a fact whose value doesn't parse counts as missing)
    r_, ebit_v, ni_v, cfo_v, capex_v = _v(rev), _v(ebit), _v(ni), _v(cfo), _v(capex)
    assets_v, equity_v, cl_v = _v(assets), _v(equity), _v(cl)
    fcf = cfo_v - capex_v if cfo_v is not None and capex_v is not None else None
    vals["fcf"] = fcf
    if financial:
        eq = equity_v
        eq_ago = bal("equity", on=asof - timedelta(days=300))
        eq_ago_v = _v(eq_ago)
        eq_avg = eq
        if eq is not None and equity is not None and eq_ago is not None and eq_ago_v is not None \
                and eq_ago.end < equity.end - timedelta(days=250):
            eq_avg = (eq + eq_ago_v) / 2
        vals["roe"] = check("roe", ni_v / eq_avg if ni_v is not None and eq_avg and eq_avg > 0 else None)
        ni_y, eq_y = annual("net_income"), annual("equity")
        roe_y = (ni_y / eq_y.reindex(ni_y.index)).dropna()
        roe_y = roe_y[eq_y.reindex(roe_y.index) > 0]
        if len(roe_y) >= cfg["min_fy_points"]:
            vals["roe_stability"] = float(roe_y.std(ddof=1) * 100)
        if equity_v is not None and assets_v is not None and assets_v > 0:
            vals["equity_assets"] = equity_v / assets_v
    else:
        if fcf is not None and r_ and r_ > 0:
            vals["fcf_margin"] = check("fcf_margin", fcf / r_)
        if ebit_v is not None and assets is not None and assets_v is not None and cash_v is not None and cl_v is not None:
            ic = assets_v - cash_v - (cl_v - debt_c)
            ago = assets.end - timedelta(days=300)
            a0 = bal("total_assets", on=ago)
            ic0: float | None = None
            if a0 is not None and (assets.end - a0.end).days <= 430:
                a0_v, c0, l0 = _v(a0), _v(bal("cash", on=ago)), _v(bal("current_liabilities", on=ago))
                if a0_v is not None and c0 is not None and l0 is not None:
                    ic0 = a0_v - c0 - (l0 - (_v(bal("debt_current", on=ago)) or 0.0))
            ic_avg = (ic + ic0) / 2 if ic0 is not None and ic0 > 0 else ic
            p, t = _v(pretax), _v(tax)
            rate = min(max(t / p, 0.0), 0.40) if p and p > 0 and t is not None else 0.25
            vals["roic"] = check("roic", ebit_v * (1 - rate) / ic_avg if ic_avg and ic_avg > 0 else None)
        rev_y, gp_y, cogs_y = annual("revenue"), annual("gross_profit"), annual("cost_of_revenue")
        margin = (gp_y / rev_y.reindex(gp_y.index)) if not gp_y.empty else \
            ((rev_y - cogs_y.reindex(rev_y.index)) / rev_y) if not cogs_y.empty else pd.Series(dtype="float64")
        margin = margin.dropna()
        basis = "gross"
        if len(margin) < cfg["min_fy_points"]:
            op_y = annual("operating_income")
            margin, basis = (op_y / rev_y.reindex(op_y.index)).dropna(), "operating"
        margin = margin[(margin >= -1) & (margin <= 1)]
        if len(margin) >= cfg["min_fy_points"]:
            vals["gm_stability"] = float(margin.std(ddof=1) * 100)
            if basis == "operating":
                notes.append("no cost of revenue reported: margin stability on the operating margin")
        rev_y = rev_y.dropna()
        if len(rev_y) >= cfg["min_fy_points"]:
            vals["rev_stability"], vals["rev_cagr"] = _trend(rev_y)
        ebitda = ebit_v + (_v(dna) or 0.0) if ebit_v is not None else None
        vals["ebitda"] = ebitda
        if debt is not None and cash_v is not None and ebitda is not None:
            nd = debt - cash_v
            vals["nd_ebitda"] = check("nd_ebitda", nd / ebitda) if ebitda > 0 else None
            if nd <= 0:
                nd_rank = -1.0                              # net cash: best, tied
            elif ebitda <= 0:
                nd_rank = 99.0                              # debt and no earnings to carry it: worst
                notes.append("net debt with negative EBITDA")
            else:
                nd_rank = vals["nd_ebitda"]
        if ebit_v is not None:
            cap = cfg["interest_cover_cap"]
            interest_v = _v(interest)
            i = abs(interest_v) if interest_v is not None else None   # Yahoo's sign varies by company
            if ebit_v <= 0:
                vals["interest_cover"] = 0.0
            elif i:
                vals["interest_cover"] = min(ebit_v / i, cap)
            elif debt is not None and assets_v is not None and debt <= 0.05 * assets_v:
                vals["interest_cover"] = float(cap)         # next to no debt, no interest line
    vals["div_years"] = dividend_years(dps, asof.year - 1)

    # --- value
    if mcap is None or mcap <= 0:
        if mcap is None:
            notes.append("no market value (price, shares or exchange rate missing): value metrics left out")
    else:
        vals["shareholder_yield"] = check("shareholder_yield", _shy(ttm, mcap))
        if financial:
            if equity_v is not None and equity_v > 0:
                vals["bp"] = equity_v / mcap
                vals["pb"] = mcap / equity_v
            if ni_v is not None:
                vals["ep"] = ni_v / mcap
                vals["pe"] = mcap / ni_v if ni_v > 0 else None
                vals["ep_vs_history"] = _own_history(facts, "net_income", None, vals["ep"], price_on, asof, cfg,
                                                     known_by)
        else:
            if fcf is not None:
                vals["fcf_yield"] = check("fcf_yield", fcf / mcap)
            if ebit_v is not None and debt is not None and cash_v is not None:
                ev = mcap + debt - cash_v + other
                if ev > 0:
                    vals["ebit_ev"] = check("ebit_ev", ebit_v / ev)
                    vals["ev_ebit"] = ev / ebit_v if ebit_v > 0 else None

                    if vals["ebit_ev"] is not None:
                        vals["ey_vs_history"] = _own_history(facts, "operating_income", True, vals["ebit_ev"],
                                                             price_on, asof, cfg, known_by)
                else:
                    notes.append("enterprise value ≤ 0 (more cash than market value and debt): EBIT/EV left out")

    rank = {}
    for m in ALL_METRICS:
        v = nd_rank if m == "nd_ebitda" else vals.get(m)
        rank[m] = None if v is None else (-v if m in LOWER_BETTER else v)
    ends = [x.end for x in (rev, ebit, cfo, ni) if x is not None]
    return {"values": vals, "rank": rank, "notes": notes,
            "period_end": max(ends).date().isoformat() if ends else None,
            "basis": next((x.basis for x in (rev, ni) if x is not None), None)}


DEBT = ("debt_current", "debt_noncurrent")


def _debt(facts, parts: list[periods.Value | None]) -> float | None:
    """Total debt from the balance lines found (`parts`). With none found it is 0 only when the company has never
    reported a debt line (a debt-free company files none); one that has, but not on this balance sheet (a renamed
    tag, a stale balance), has unknown debt: None, never 0."""
    known = [x for x in (_v(p) for p in parts) if x is not None]
    if known:
        return sum(known)
    return None if any(periods.instant(facts, i) is not None for i in DEBT) else 0.0


def _shy(ttm, mcap: float) -> float | None:
    d, b, i = ttm("dividends_paid"), ttm("buybacks"), ttm("issuance")
    if d is None and b is None and i is None:
        return None
    return ((_v(d) or 0.0) + (_v(b) or 0.0) - (_v(i) or 0.0)) / mcap


def _own_history(facts, item: str, ev_based: bool | None, now: float | None, price_on, asof, cfg,
                 known_by) -> float | None:
    """Today's yield (EBIT/EV, or E/P for financials) as a percentile of the company's own fiscal year-ends over
    `ey_history_years` (market value from that day's price and shares); None with fewer than
    `ey_history_min_points` points, today included."""
    if now is None or price_on is None:
        return None
    fy = periods.annual(facts, item, known_by)
    fy = fy[fy.index >= asof - pd.DateOffset(years=cfg["ey_history_years"])]
    hist = []
    for end, flow in fy.items():
        px = price_on(end)
        sh = periods.instant(facts, "shares", known_by, on=end + timedelta(days=60))
        if px is None or sh is None or abs((sh.end - end).days) > 100:
            continue
        mc = px * sh.value
        if ev_based:
            d = _debt(facts, [periods.instant(facts, i, known_by, on=end) for i in DEBT])
            c = _v(periods.instant(facts, "cash", known_by, on=end))
            if c is None or d is None:
                continue
            ev = mc + d - c
            if ev <= 0:
                continue
            hist.append(flow / ev)
        elif mc > 0:
            hist.append(flow / mc)
    if len(hist) + 1 < cfg["ey_history_min_points"]:
        return None
    return 100.0 * sum(h < now for h in hist) / len(hist)


# ---------------- percentiles and scores ----------------

def score(table: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Percentiles, pillars and scores for a table with columns ticker, set (standard | financial), sector, member
    (counts as a peer) and `rank_<metric>`. Returns one row per ticker: pct_/basis_/peers_<metric>,
    q_<pillar>, quality, value, qv, q_n, v_n."""
    min_peers = cfg["min_sector_peers"]
    out = pd.DataFrame(index=table["ticker"])
    t = table.set_index("ticker")
    members = t[t["member"]]
    is_member = t["member"].astype(bool)
    for m in ALL_METRICS:
        col = f"rank_{m}"
        if col not in t:
            continue
        vals = pd.to_numeric(t[col], errors="coerce")
        have = members.assign(_v=pd.to_numeric(members[col], errors="coerce")).dropna(subset=["_v"])
        by_set = {k: np.sort(g["_v"].to_numpy()) for k, g in have.groupby("set")}
        by_sector = {k: np.sort(g["_v"].to_numpy()) for k, g in have[have["sector"].astype(bool)]
                     .groupby(["set", "sector"])}
        pct, basis, peers = {}, {}, {}
        for tk, v in vals.dropna().items():
            kind, sector = t.at[tk, "set"], t.at[tk, "sector"]
            sect = by_sector.get((kind, sector)) if sector else None
            use, b = (sect, "sector") if sect is not None and len(sect) >= min_peers else (by_set.get(kind), "universe")
            n = 0 if use is None else len(use)
            below = 0 if use is None else int(np.searchsorted(use, v, side="left"))   # strictly below
            if not is_member[tk]:            # not a member: ranked against the members, itself included
                n += 1
            if n < 2:
                continue
            pct[tk], basis[tk], peers[tk] = 100.0 * below / n, b, n
        out[f"pct_{m}"] = pd.Series(pct, dtype="float64")
        out[f"basis_{m}"] = pd.Series(basis, dtype="object")
        out[f"peers_{m}"] = pd.Series(peers, dtype="float64")

    qcfg, wq = cfg["quality"], cfg["quality"]["weights"]
    rows = []
    for tk, row in t.iterrows():
        kind = row["set"]
        pillars = {}
        for p, ms in QUALITY[kind].items():
            vals = [out.at[tk, f"pct_{m}"] for m in ms if f"pct_{m}" in out and pd.notna(out.at[tk, f"pct_{m}"])]
            pillars[p] = float(np.mean(vals)) if vals else None
        have = {p: v for p, v in pillars.items() if v is not None}
        ok = len(have) >= qcfg["min_pillars"] and all(p in have for p in qcfg.get("required", []))
        quality = sum(have[p] * wq[p] for p in have) / sum(wq[p] for p in have) if ok else None
        vcfg = cfg["financial_value" if kind == "financial" else "value"]
        comps = {m: out.at[tk, f"pct_{m}"] for m in VALUE[kind] if f"pct_{m}" in out and pd.notna(out.at[tk, f"pct_{m}"])}
        ok_v = len(comps) >= vcfg["min_components"] and any(m in comps for m in vcfg.get("required_any", []))
        wv = vcfg["weights"]
        value = sum(comps[m] * wv[m] for m in comps) / sum(wv[m] for m in comps) if ok_v else None
        rows.append({"ticker": tk, **{f"q_{p}": pillars.get(p) for p in PILLARS},
                     "quality": None if quality is None else round(quality, 1),
                     "value": None if value is None else round(value, 1),
                     "qv": round((quality + value) / 2, 1) if quality is not None and value is not None else None,
                     "q_n": len(have), "v_n": len(comps)})
    return out.join(pd.DataFrame(rows).set_index("ticker"))

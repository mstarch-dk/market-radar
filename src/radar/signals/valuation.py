"""Valuation and sentiment readings from the stored snapshots (valuation.py, sentiment.py): P/E against sector
peers, EPS revisions between weekly snapshots and their breadth per region, ETF multiples against ACWI and their
own history, the market's CAPE and equity risk premium, and the AAII and put/call extremes. Pure functions:
everything missing stays missing (None), never 0.
"""
from __future__ import annotations

import pandas as pd

from ..values import num
from . import gauges as gz


def percentile(s: pd.Series, v: float) -> float | None:
    """% of the history below `v` (0–100), as in the CFTC table."""
    s = s.dropna()
    return None if s.empty or v is None else round(100 * float((s < v).mean()), 1)


# ---------------- stocks ----------------

def vs_sector(latest: pd.DataFrame, group: dict[str, str], sector: dict[str, str], min_peers: int = 5) -> pd.Series:
    """Each stock's forward P/E divided by the median of its sector within its group (a region of the radar or a
    Discover market). None without a P/E or with fewer than `min_peers` peers that have one."""
    df = pd.DataFrame({"pe": latest["pe_fy1"]})
    df["group"], df["sector"] = df.index.map(group), df.index.map(sector)
    df = df.dropna(subset=["group", "sector"])
    med = df.dropna(subset=["pe"]).groupby(["group", "sector"])["pe"].agg(["median", "count"])
    out = {}
    for t, r in df.iterrows():
        m = med.loc[(r["group"], r["sector"])] if (r["group"], r["sector"]) in med.index else None
        out[t] = (r["pe"] / m["median"] if m is not None and pd.notna(r["pe"]) and m["count"] >= min_peers else None)
    return pd.Series(out, dtype=object)


def _snap(hist: pd.DataFrame, day: pd.Timestamp) -> pd.DataFrame:
    d = pd.to_datetime(hist["date"])
    return hist[d == day].drop_duplicates("ticker", keep="last").set_index("ticker")


def eps_revision(new: dict, old: dict) -> float | None:
    """Change in the next-fiscal-year EPS estimate between two snapshots. When the fiscal year has rolled over
    (this year's estimate is now last time's "next year"), the comparison follows the same year."""
    n_fy1, o_fy1, n_cy, o_cy = (num(new.get("eps_fy1")), num(old.get("eps_fy1")), num(new.get("eps_cy")), num(old.get("eps_cy")))
    if o_fy1 is None or not o_fy1:
        return None
    rolled = (n_cy is not None and o_cy and abs(n_cy / o_cy - 1) > 0.15 and abs(n_cy / o_fy1 - 1) < abs(n_cy / o_cy - 1))
    cur = n_cy if rolled else n_fy1
    return None if cur is None else (cur - o_fy1) / abs(o_fy1)


def revisions(hist: pd.DataFrame, weeks: int, tolerance_days: int = 4) -> tuple[pd.Series, pd.Timestamp | None]:
    """EPS revision per ticker over `weeks` (latest snapshot vs the one closest to `weeks` earlier, within
    `tolerance_days`). Empty when the history is shorter: the reading needs time to build up."""
    if hist.empty:
        return pd.Series(dtype=float), None
    dates = sorted(pd.to_datetime(hist["date"]).unique())
    last = pd.Timestamp(dates[-1])
    target = last - pd.Timedelta(weeks=weeks)
    near = [pd.Timestamp(d) for d in dates[:-1] if abs((pd.Timestamp(d) - target).days) <= tolerance_days]
    if not near:
        return pd.Series(dtype=float), None
    base = min(near, key=lambda d: abs((d - target).days))
    a, b = _snap(hist, last), _snap(hist, base)
    if "cross_ccy" in a:   # Yahoo converts their next-year EPS at today's rate: an FX move would look like a revision
        a = a[~a["cross_ccy"].fillna(False).astype(bool)]
    common = a.index.intersection(b.index)
    out = {t: eps_revision(a.loc[t].to_dict(), b.loc[t].to_dict()) for t in common}
    return pd.Series({k: v for k, v in out.items() if v is not None}, dtype=float), base


def history_weeks(hist: pd.DataFrame) -> int:
    return len(pd.to_datetime(hist["date"]).unique()) if not hist.empty else 0


def breadth(rev: pd.Series, group: dict[str, str], band: float = 0.01, min_names: int = 10) -> list[dict]:
    """Per group: names with a revision, % revised up and down (beyond `band`), and net up − down."""
    df = pd.DataFrame({"rev": rev})
    df["group"] = df.index.map(group)
    out = []
    for g, x in df.dropna().groupby("group"):
        if len(x) < min_names:
            continue
        up, down = float((x["rev"] > band).mean()), float((x["rev"] < -band).mean())
        out.append({"group": g, "names": len(x), "up": up, "down": down, "net": up - down,
                    "median": float(x["rev"].median()), "gauge": gz.gauge("revision_breadth", up - down)})
    return out


# ---------------- ETFs ----------------

def etf_rows(hist: pd.DataFrame, bench: str, min_weeks: int = 26) -> dict[str, dict]:
    """Per ETF: P/E, P/B, P/E relative to the benchmark's, and the P/E percentile in its own stored history
    (None until `min_weeks` snapshots exist)."""
    if hist.empty:
        return {}
    d = pd.to_datetime(hist["date"])
    now = hist[d == d.max()].drop_duplicates("ticker", keep="last").set_index("ticker")
    bench_pe = num(now.loc[bench, "pe"]) if bench in now.index else None
    out = {}
    for t, r in now.iterrows():
        pe = num(r["pe"])
        past = hist[hist["ticker"] == t]["pe"].dropna()
        out[t] = {"pe": pe, "pb": num(r.get("pb")), "pe_vs_acwi": pe / bench_pe if pe and bench_pe else None,
                  "pe_pct": percentile(past, pe) if pe is not None and len(past) >= min_weeks else None,
                  "weeks": int(len(past))}
    return out


# ---------------- the market ----------------

def market(cape: pd.Series, erp: pd.Series, fwd_pe: float | None, real10y: pd.Series) -> dict:
    """The market's valuation: CAPE (percentiles since 1871 and 1990), Damodaran's implied ERP (percentile since
    2008) and the yield gap: S&P 500 forward earnings yield (FactSet P/E) minus the US 10Y real yield."""
    out: dict = {"cape": None, "erp": None, "yield_gap": None}
    c = cape.dropna()
    if len(c):
        v = float(c.iloc[-1])
        out["cape"] = {"value": v, "asof": c.index[-1].date().isoformat(), "pct_all": percentile(c.iloc[:-1], v),
                       "pct_1990": percentile(c[c.index >= "1990-01-01"].iloc[:-1], v), "median": float(c.median()),
                       "since": c.index[0].date().isoformat()}
        out["cape"]["gauge"] = gz.gauge("cape_pct", out["cape"]["pct_all"])
    e = erp.dropna()
    if len(e):
        v = float(e.iloc[-1])
        out["erp"] = {"value": v, "asof": e.index[-1].date().isoformat(), "pct": percentile(e.iloc[:-1], v),
                      "median": float(e.median()), "since": e.index[0].date().isoformat()}
        out["erp"]["gauge"] = gz.gauge("erp_pct", out["erp"]["pct"])
    r = real10y.dropna()
    if fwd_pe and len(r):
        ey = 100 / fwd_pe
        out["yield_gap"] = {"earnings_yield": ey, "real_yield": float(r.iloc[-1]), "value": ey - float(r.iloc[-1]),
                            "asof": r.index[-1].date().isoformat(), "fwd_pe": fwd_pe}
        out["yield_gap"]["gauge"] = gz.gauge("yield_gap", out["yield_gap"]["value"])
    return out


# ---------------- sentiment (contrarian) ----------------

def aaii(df: pd.DataFrame, extreme: float = 10) -> dict | None:
    """The latest AAII survey: bull − bear spread, its 8-week average and the spread's percentile since 1987."""
    if df.empty:
        return None
    s = (df.set_index(pd.to_datetime(df["date"]))["bullish"] - df.set_index(pd.to_datetime(df["date"]))["bearish"]).sort_index()
    v = float(s.iloc[-1])
    pct = percentile(s.iloc[:-1], v)
    last = df.sort_values("date").iloc[-1]
    flag = "extreme fear" if pct is not None and pct <= extreme else "euphoria" if pct is not None and pct >= 100 - extreme else None
    return {"asof": pd.Timestamp(last["date"]).date().isoformat(), "bullish": float(last["bullish"]),
            "neutral": float(last["neutral"]), "bearish": float(last["bearish"]), "spread": v,
            "spread_8w": float(s.iloc[-8:].mean()), "pct": pct, "flag": flag, "gauge": gz.gauge("aaii_pct", pct),
            "history": [{"date": d.date().isoformat(), "spread": float(x)} for d, x in s.iloc[-156:].items()]}


def putcall(df: pd.DataFrame, lookback: int = 756) -> dict | None:
    """The equity put/call ratio's 10-day average and its percentile over `lookback` trading days (high = fear)."""
    if df.empty or "equity" not in df:
        return None
    s = df.set_index(pd.to_datetime(df["date"]))["equity"].dropna().sort_index()
    if len(s) < 10:
        return None
    avg = s.rolling(10).mean().dropna()
    v = float(avg.iloc[-1])
    hist = avg.iloc[-lookback:-1]
    last = df.sort_values("date").iloc[-1]
    return {"asof": s.index[-1].date().isoformat(), "total": num(last.get("total")), "equity": num(last.get("equity")),
            "index": num(last.get("index")), "equity_10d": v, "pct": percentile(hist, v) if len(hist) >= 60 else None,
            "days": int(len(s)), "gauge": gz.gauge("putcall_pct", percentile(hist, v) if len(hist) >= 60 else None)}

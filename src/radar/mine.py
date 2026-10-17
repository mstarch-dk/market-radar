"""Your holdings, watchlist and sold positions: momentum, DKK return vs a shadow ACWI position, flags and
stop/take-profit levels. Used by `radar run` (summary.json) and live by the web API (`/api/me`)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import external, universe
from .model.inputs import level_etfs, level_universe  # noqa: F401 (re-exported)
from .model.score import score_vs
from .signals import gauges as gz
from .signals import levels, momentum, technicals

METRIC_KEYS = ("last", "r1m", "r3m", "r6m", "r12_1", "from_high", "sma50", "sma200", "vol_surge", "history",
               "above50", "above200", "trend_ok")
POSITION_KEYS = ("quantity", "avg_price", "first_trade", "last_sell_date", "last_sell_price")
RS_HIGH_DAYS = 5      # flag: the RS line against ACWI (both in DKK) made a new 52-week high within this many sessions
CROSS_DAYS = 20       # flag: the 50-day average crossed the 200-day within this many sessions


_fx_to_dkk = universe.fx_to_dkk


def _vs_shadow(tx: pd.DataFrame, px: pd.Series, fx: pd.Series, bench_dkk: pd.Series,
               raw: pd.Series | None = None) -> tuple[float, float] | None:
    """Total return of the open position vs. a shadow ACWI position with identical DKK cash flows.

    Buys put the same DKK amount into ACWI on the same day; sells remove the same fraction from both
    (average-cost method). Dividends count as reinvested on both sides: `px` is the adjusted close, and each
    lot's shares are scaled by adjusted/traded close on its trade date, so a lot bought before an ex-date
    gets the dividend. Without `raw` (traded closes) the position is price-only. Returns (position return,
    shadow return), both in DKK.
    """
    factor = (px / raw).dropna() if raw is not None else pd.Series(dtype=float)
    qty = units_px = cost = units = 0.0  # units_px: dividend-reinvested shares, in adjusted-price terms
    for _, t in tx.sort_values("date", kind="stable").iterrows():
        d, q = t["date"], t["quantity"]
        if t["type"] == "SELL":
            if qty <= 1e-9:
                continue
            keep = 1 - min(q, qty) / qty
            qty, units_px, cost, units = qty * keep, units_px * keep, cost * keep, units * keep
        else:
            if qty <= 1e-9:
                qty = units_px = cost = units = 0.0
            fee = t.get("fee", 0)
            amount = (q * t["price"] + (0.0 if pd.isna(fee) else fee)) * fx.asof(d)   # fees are part of the cost
            f = factor.asof(d) if not factor.empty else np.nan
            if not (np.isfinite(f) and f > 0):  # trade before the price history: price-only for that lot
                f = factor.iloc[-1] if not factor.empty else 1.0
            qty += q
            units_px += q / f
            cost += amount
            units += amount / bench_dkk.asof(d)
    if qty <= 1e-9 or not np.isfinite(cost) or not np.isfinite(units) or cost <= 0:
        return None
    value = units_px * px.iloc[-1] * fx.iloc[-1]
    return value / cost - 1, units * bench_dkk.iloc[-1] / cost - 1


def _me_table(closes, volumes, all_stocks: pd.DataFrame, bench: str, min_history: int,
              raw_closes: pd.DataFrame | None = None, portfolios: list[int] | None = None) -> pd.DataFrame:
    h = universe.holdings(portfolios)
    if h.empty:
        return pd.DataFrame()
    m = momentum.metrics(closes, volumes, list(h["symbol"]), min_history)
    df = h.merge(m, left_on="symbol", right_on="ticker", how="left")
    b = closes[bench].dropna()
    rel3 = b.iloc[-1] / b.iloc[-64] - 1
    df["rel_r3m"] = df["r3m"] - rel3
    df["score"] = [score_vs(all_stocks, r) if pd.notna(r["last"]) else None for _, r in df.iterrows()]

    ccy = universe.currencies([*df["symbol"], bench])
    bench_dkk = (b * _fx_to_dkk(closes, ccy[bench]).reindex(b.index).ffill()).dropna()
    tx = universe.transactions(portfolios)
    since, bench_since, since_sell, flags = [], [], [], []
    for _, r in df.iterrows():
        s_ret = b_ret = x_ret = None
        f = []
        if r["status"] == "sold" and pd.notna(r.get("last_sell_price")) and pd.notna(r["last"]):
            x_ret = r["last"] / r["last_sell_price"] - 1
            if not -0.95 < x_ret < 20:
                x_ret = None
        since_sell.append(x_ret)
        if r["status"] == "holding" and pd.notna(r["last"]):
            fx = _fx_to_dkk(closes, ccy.get(r["symbol"]))
            raw = raw_closes[r["symbol"]] if raw_closes is not None and r["symbol"] in raw_closes else None
            res = _vs_shadow(tx[tx["symbol"] == r["symbol"]], closes[r["symbol"]].dropna(), fx, bench_dkk, raw) \
                if fx is not None else None
            if res is None:
                f.append("can't compute return")
            elif not -0.95 < res[0] < 20:  # usually a GBp/GBP (pence vs pounds) mismatch in Yahoo
                f.append("check purchase price units")
            else:
                s_ret, b_ret = res
        since.append(s_ret)
        bench_since.append(b_ret)
        if pd.isna(r["last"]):
            f.append("no data")
        else:
            if pd.notna(r["trend_ok"]) and bool(r["trend_ok"]):
                f.append("trend intact")
            if r["status"] == "holding" and not r["above50"] and r["r1m"] < 0:
                f.append("losing momentum")
            if r["status"] == "holding" and r["above200"] == False:  # noqa: E712 (NaN-safe)
                f.append("below 200d")
            if r["status"] in ("watch", "sold") and r["above50"] and r["r1m"] > 0 and r["rel_r3m"] > 0:
                f.append("turning up")
            if r["from_high"] > -0.03:
                f.append("near 52w high")
            c = closes[r["symbol"]]
            fx_t = _fx_to_dkk(closes, ccy.get(r["symbol"]))
            if r["symbol"] != bench and fx_t is not None and technicals.rs_new_high(
                    c * fx_t.reindex(c.index).ffill(), bench_dkk, RS_HIGH_DAYS):
                f.append("RS line at 52w high")
            cross = technicals.sma_cross(c, CROSS_DAYS)
            if cross:
                f.append(f"{cross} cross")
        flags.append(f)
    df["since_buy"] = since
    df["bench_since_buy"] = bench_since
    df["since_sell"] = since_sell
    df["flags"] = flags
    # holdings & watchlist by momentum score, sold positions by most recent sale
    sold_date = pd.to_datetime(df["last_sell_date"], errors="coerce")
    df["_o"] = df["status"].map({"holding": 0, "watch": 1, "sold": 2})
    df["_k"] = (-df["score"].astype(float)).where(df["status"] != "sold", -sold_date.astype("int64").astype(float))
    return df.sort_values(["_o", "_k"]).drop(columns=["_o", "_k"])


def _add_levels(me: pd.DataFrame, closes, highs, lows, etfs: set[str], quadrant: dict[str, str],
                regime_label: str | None, cfg: dict) -> None:
    """Stop / take-profit levels for held stocks and sector/theme ETFs (broad index funds are left out).

    A stock is a ticker Yahoo gives a sector (funds have none, even when it labels them EQUITY) or one in
    a stock group. `etfs` are the sector/theme funds (and their UCITS twins) that get levels; `quadrant` maps
    those to their rotation quadrant.
    """
    ah = external.load_analyst()
    eligible = level_universe(etfs, ah)
    out = []
    for _, r in me.iterrows():
        lv = None
        if r["status"] == "holding" and r["symbol"] in eligible:
            row = r.to_dict() | {"quadrant": quadrant.get(r["symbol"]),
                                 "score": None if pd.isna(r["score"]) else r["score"]}
            lv = levels.for_ticker(r["symbol"], closes, highs, lows, row, r.get("first_trade"), regime_label, ah, cfg)
        out.append(lv)
    me["levels"] = out


def quadrants(rotation_rows) -> dict[str, str]:
    """ticker (and its UCITS twin) -> rotation quadrant, from rotation table rows."""
    out = {}
    for r in rotation_rows:
        out[r["ticker"]] = r["quadrant"]
        if isinstance(r.get("ucits"), str):
            out[r["ucits"]] = r["quadrant"]
    return out


def _v(v):
    if isinstance(v, (float, np.floating)) and not np.isfinite(v):
        return None
    if isinstance(v, np.generic):
        return v.item()
    if v is pd.NaT or v is pd.NA:
        return None
    if isinstance(v, pd.Timestamp):
        return v.date().isoformat()
    return v


def table(closes, highs, lows, volumes, raw_closes, leaders: pd.DataFrame, rotation_rows, regime_label: str | None,
          cfg: dict, sessions=None, portfolios: list[int] | None = None) -> list[dict]:
    """One row per holding / watchlist / sold symbol, holdings first, pooled over these portfolios (ids;
    default: your real ones). `leaders` is the momentum table of the whole stock universe (the score is a
    percentile against it); `cfg` is settings(). `sessions(symbol)` gives the symbol's own closes (no
    gap-filled holidays), so its RSI matches the ticker page."""
    bench = universe.benchmark()
    me = _me_table(closes, volumes, leaders, bench, cfg["momentum"]["min_history_days"], raw_closes, portfolios)
    if me.empty:
        return []
    names = universe.names(list(me["symbol"]))
    _add_levels(me, closes, highs, lows, level_etfs(cfg["stops"]), quadrants(rotation_rows), regime_label,
                cfg["stops"] | {"analyst_max_age_days": cfg["coverage"]["max_age"]["analyst"]})
    rows = []
    for _, r in me.iterrows():
        row = {"symbol": r["symbol"], "name": names.get(r["symbol"]), "status": r["status"]}
        row |= {k: _v(r.get(k)) for k in POSITION_KEYS}
        row |= {k: _v(r.get(k)) for k in METRIC_KEYS}
        if row["history"] is not None:
            row["history"] = int(row["history"])
        row |= {k: _v(r[k]) for k in ("rel_r3m", "score", "since_buy", "bench_since_buy", "since_sell")}
        row["flags"] = list(r["flags"])
        row["levels"] = _levels_row(r["levels"])
        c = (sessions(r["symbol"]) if sessions else closes[r["symbol"]]).dropna() if r["symbol"] in closes else None
        rsi = technicals.rsi(c).iloc[-1] if c is not None and len(c) > 15 else None
        lv = row["levels"] or {}
        excess = (row["since_buy"] - row["bench_since_buy"]
                  if row["since_buy"] is not None and row["bench_since_buy"] is not None else None)
        row["gauges"] = gz.gauges({"score": row["score"], "rsi14": rsi, "from_high": row["from_high"],
                                   "stop_dist": lv.get("stop_pct"), "tp_dist": lv.get("tp_pct"), "excess_vs_acwi": excess})
        row["watchouts"] = gz.watchouts(row["gauges"], skip=set() if row["status"] == "holding" else {"stop_dist", "tp_dist"})
        rows.append(row)
    return rows


def _levels_row(lv: dict | None) -> dict | None:
    if not lv:
        return None
    a = lv.get("analyst") or None
    return {k: _v(lv.get(k)) for k in ("stop", "stop_pct", "take_profit", "tp_pct", "tp_source", "k", "anchor", "atr",
                                       "anchor_basis", "mode", "action")} | {
        "reasons": [{"signal": x["signal"], "effect": float(x["effect"]), "detail": x["detail"]} for x in lv["reasons"]],
        "flags": list(lv["flags"]), "breaches": lv.get("breaches") or [],
        "analyst": {k: _v(a.get(k)) for k in ("fetched", "rec_key", "n_analysts", "target_low", "target_high",
                                               "target_mean", "upside", "stale")} if a else None}

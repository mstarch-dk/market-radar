"""Rule-based stop-loss / take-profit levels for a position, each with the signals that set it.

Stop = anchor (highest close since entry) - k x ATR. k starts at `k_base` and every signal that
argues for more or less room moves it by `k_step`; each move is recorded as a reason. Take-profit is
the lower of a reward/risk multiple of the stop width (k x ATR) and the analysts' mean target.
A mechanical rule for discipline and review, not a recommendation.
"""
from __future__ import annotations

import math

import pandas as pd


def atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    """Wilder's average true range."""
    prev = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1, skipna=False)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def anchor(close: pd.Series, since, days: int) -> tuple[float | None, str]:
    """Highest close since entry, or over the last `days` sessions when there is no entry date."""
    close = close.dropna()
    if close.empty:
        return None, ""
    since = pd.to_datetime(since, errors="coerce") if since is not None else pd.NaT
    if pd.notna(since) and not close[since:].empty:
        return float(close[since:].max()), f"highest close since entry ({since.date()})"
    return float(close.iloc[-days:].max()), f"highest close of the last {days} sessions"


def analyst_view(hist: pd.DataFrame, ticker: str, close: pd.Series, revision_days: int = 30,
                 max_age_days: int | None = None) -> dict | None:
    """Latest analyst consensus for `ticker`, with targets converted into the radar's price units.

    Consensus fetched more than `max_age_days` before the last close is returned without targets and
    marked `stale`, so it can't set a take-profit.

    Yahoo's targets are quoted against its own `current_price`, which can be in different units than the
    listing's adjusted close (GBp vs GBP, ADR ratios). Scaling by our close on the fetch date over Yahoo's
    price that day fixes the units without assuming anything about the currency.
    """
    if hist is None or hist.empty:
        return None
    h = hist[hist["ticker"] == ticker].sort_values("fetched")
    if h.empty:
        return None
    a = h.iloc[-1].to_dict()
    out = {"fetched": pd.Timestamp(a["fetched"]).date().isoformat(), "quote_type": a.get("quote_type"),
           "n_analysts": _num(a.get("n_analysts")), "rec_key": a.get("rec_key") or None,
           "rec_mean": _num(a.get("rec_mean"))}
    close = close.dropna()
    if max_age_days is not None and not close.empty and (close.index[-1] - pd.Timestamp(a["fetched"])).days > max_age_days:
        return out | {"stale": True, "max_age_days": max_age_days}
    cur, mean = _num(a.get("current_price")), _num(a.get("target_mean"))
    on_fetch = close[:pd.Timestamp(a["fetched"])]
    if not cur or mean is None or on_fetch.empty:
        return out
    unit = float(on_fetch.iloc[-1]) / cur
    for k in ("target_mean", "target_median", "target_high", "target_low"):
        v = _num(a.get(k))
        out[k] = None if v is None else v * unit
    out["upside"] = out["target_mean"] / float(close.iloc[-1]) - 1
    old = h[h["fetched"] <= pd.Timestamp(a["fetched"]) - pd.Timedelta(days=revision_days)]
    old_mean = _num(old.iloc[-1]["target_mean"]) if not old.empty else None
    out["target_change"] = mean / old_mean - 1 if old_mean else None
    return out


def levels(row: dict, atr_value: float, anchor_value: float, regime_label: str | None,
           analyst: dict | None, cfg: dict) -> dict:
    """Stop / take-profit for one position.

    `row` needs last, sma50, sma200, above50, above200, trend_ok, r1m and optionally score (0-100,
    momentum percentile) and quadrant (RRG, ETFs). Returns the levels, k, reasons and flags.
    """
    last = float(row["last"])
    step = cfg["k_step"]
    reasons: list[dict] = []
    k = cfg["k_base"]

    def adjust(signal: str, effect: float, detail: str):
        nonlocal k
        k += effect
        reasons.append({"signal": signal, "effect": effect, "detail": detail})

    def note(signal: str, detail: str):
        reasons.append({"signal": signal, "effect": 0, "detail": detail})

    score, trend_ok = row.get("score"), row.get("trend_ok")
    if _true(trend_ok) and score is not None and score >= cfg["strong_score"]:
        adjust("Strong momentum", step, f"score {score:.0f} with the 50d above a rising 200d: give the trend room")
    if row.get("above200") == False:  # noqa: E712 (NaN-safe, numpy bools)
        adjust("Trend broken", -step, f"price below its 200-day average ({row['sma200']:.2f})")
    if not _true(row.get("above50")) and (row.get("r1m") or 0) < 0:
        adjust("Losing momentum", -step, f"below the 50-day average and down {row['r1m']:.1%} over 1 month")
    sma50 = row.get("sma50")
    if sma50 and last / sma50 - 1 > cfg["extended_vs_sma50"]:
        adjust("Extended", -step, f"{last / sma50 - 1:.0%} above the 50-day average: pullbacks tend to be sharp")
    if regime_label == "Risk-off":
        adjust("Macro regime", -step, "radar regime is Risk-off")
    elif regime_label == "Mixed":
        adjust("Macro regime", -step / 2, "radar regime is Mixed")
    elif regime_label:
        note("Macro regime", f"radar regime is {regime_label}")

    flags: list[str] = []
    a = analyst if analyst and analyst.get("target_mean") and (analyst.get("n_analysts") or 0) >= cfg["min_analysts"] else None
    if a:
        cons = f"consensus {a['rec_key'] or '?'}, {a['n_analysts']:.0f} analysts"
        if a.get("target_high") and last > a["target_high"]:
            flags.append("above highest analyst target")
            adjust("Above all analyst targets", -step, f"highest target {a['target_high']:.2f} ({cons})")
        elif last > a["target_mean"]:
            adjust("Above analyst target", -step, f"mean target {a['target_mean']:.2f} is {a['upside']:.1%} away ({cons})")
        if a.get("target_change") is not None and a["target_change"] < -cfg["target_cut"]:
            adjust("Targets being cut", -step / 2, f"mean target {a['target_change']:+.1%} over the last 30 days")
        elif a.get("target_change") is not None and a["target_change"] > cfg["target_cut"]:
            note("Targets being raised", f"mean target {a['target_change']:+.1%} over the last 30 days")

    if row.get("quadrant") in ("Weakening", "Lagging"):
        note("Rotation", f"RRG quadrant vs ACWI: {row['quadrant']}")

    k = min(max(k, cfg["k_min"]), cfg["k_max"])
    stop = anchor_value - k * atr_value
    reasons.insert(0, {"signal": "Trailing ATR stop", "effect": 0,
                       "detail": f"{anchor_value:.2f} high − {k:.2f} × ATR {atr_value:.2f} ({atr_value / last:.1%} of price)"})
    sma200 = row.get("sma200")
    if sma200 and stop < sma200 < last:
        note("200-day average", f"{sma200:.2f} sits between price and stop: a break there is an earlier warning")

    tp, tp_source = None, None
    if "above highest analyst target" not in flags:
        cands = []
        # one risk unit is the full stop width (k x ATR), so the target doesn't shrink as price nears the stop
        cands.append((last + cfg["reward_risk"] * k * atr_value, f"{cfg['reward_risk']:g}:1 reward/risk"))
        if a and a["target_mean"] > last:
            cands.append((a["target_mean"], f"analyst mean target ({a['n_analysts']:.0f} analysts)"))
        if cands:
            tp, tp_source = min(cands)
            reasons.append({"signal": "Take-profit", "effect": 0,
                            "detail": " vs ".join(f"{s} {v:.2f}" for v, s in cands) + f" → lower: {tp_source}"})

    if last <= stop:
        flags.append("stop hit")
    elif last - stop <= cfg["near_atr"] * atr_value:
        flags.append("near stop")
    if tp is not None and tp - last <= cfg["near_atr"] * atr_value:
        flags.append("near target")

    return {"stop": stop, "stop_pct": stop / last - 1, "take_profit": tp, "tp_pct": None if tp is None else tp / last - 1,
            "tp_source": tp_source, "k": k, "anchor": anchor_value, "atr": atr_value,
            "reasons": reasons, "flags": flags}


def for_ticker(ticker: str, closes: pd.DataFrame, highs: pd.DataFrame, lows: pd.DataFrame, row: dict, since,
               regime_label: str | None, analyst_hist: pd.DataFrame | None, cfg: dict) -> dict | None:
    """`levels` for one ticker from the wide price frames; None without enough high/low history."""
    if ticker not in closes or ticker not in highs or ticker not in lows or pd.isna(row.get("last")):
        return None
    a = atr(highs[ticker], lows[ticker], closes[ticker], cfg["atr_days"]).dropna()
    if a.empty:
        return None
    anc, basis = anchor(closes[ticker], since, cfg["info_anchor_days"])
    view = analyst_view(analyst_hist, ticker, closes[ticker], max_age_days=cfg.get("analyst_max_age_days"))
    k = levels(row, float(a.iloc[-1]), anc, regime_label, view, cfg)["k"]   # k doesn't depend on the anchor
    close = closes[ticker].dropna()
    start = close.index[-cfg["info_anchor_days"]] if basis.startswith("highest close of") else pd.Timestamp(since)
    start, breaches = trail(close, a, start, k)
    if breaches:
        anc = float(close[start:].max())
        basis = f"highest close since the last stop breach ({breaches[-1]['date']})"
    out = levels(row, float(a.iloc[-1]), anc, regime_label, view, cfg)
    out["reasons"][0]["detail"] = f"{basis}: " + out["reasons"][0]["detail"]
    if breaches:
        b = breaches[-1]
        out["reasons"].insert(1, {"signal": "Stop breached", "effect": 0, "detail":
                                  f"closed at {b['close']:.2f} through the stop at {b['stop']:.2f} on {b['date']}"
                                  f" ({len(breaches)} breach{'es' if len(breaches) > 1 else ''} since entry, at today's k);"
                                  " the stop now trails from the high since then"})
        if pd.Timestamp(b["date"]) >= close.index[-21]:  # recent breaches only; older ones are in the reasons
            out["flags"].append(f"stop breached {b['date']}")
    if view and view.get("stale"):
        out["reasons"].append({"signal": "Analyst data", "effect": 0, "detail":
                               f"consensus from {view['fetched']} is older than {view['max_age_days']} days: not used"})
    return out | {"anchor_basis": basis, "analyst": view, "breaches": breaches}


def trail(close: pd.Series, atr_series: pd.Series, start, k: float) -> tuple[pd.Timestamp, list[dict]]:
    """Walk a chandelier stop (running high - k x ATR) forward from `start`.

    Each close at or below the stop is a breach; the trail restarts the next session. Returns the start of
    the current trail and the breaches. A breach on the last bar doesn't restart, so it shows as "stop hit".
    """
    breaches = []
    start = pd.Timestamp(start)
    while True:
        seg = close[start:]
        if seg.empty:
            break
        stop = seg.cummax() - k * atr_series.reindex(seg.index)
        hit = seg.index[(seg <= stop).to_numpy()]
        if hit.empty or hit[0] == close.index[-1]:
            break
        d = hit[0]
        breaches.append({"date": d.date().isoformat(), "close": float(seg[d]), "stop": float(stop[d])})
        start = close.index[close.index.get_loc(d) + 1]
    return start, breaches


def _true(v) -> bool:
    return v is not None and not (isinstance(v, float) and math.isnan(v)) and bool(v)


def _num(v) -> float | None:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v

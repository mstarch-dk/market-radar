"""Market regime: a handful of transparent risk-on / risk-off indicators."""
from __future__ import annotations

import pandas as pd

ON, OFF, NEUTRAL = "risk-on", "risk-off", "neutral"


def breadth_history(closes: pd.DataFrame, tickers: list[str], days: int = 200) -> pd.Series:
    """% of tickers trading above their `days`-day moving average, over time."""
    c = closes[[t for t in tickers if t in closes.columns]]
    above = c > c.rolling(days, min_periods=days).mean()
    valid = c.rolling(days, min_periods=days).mean().notna()
    return (100 * above.sum(axis=1) / valid.sum(axis=1)).where(valid.sum(axis=1) > 0).dropna()


def _ind(name, value, status, note):
    return {"name": name, "value": value, "status": status, "note": note}


def indicators(closes: pd.DataFrame, fred: pd.DataFrame, bench: str, groups: dict, labels: dict,
               vix_ticker: str, cfg: dict) -> tuple[list[dict], dict[str, pd.Series]]:
    out, breadth = [], {}

    b = closes[bench].dropna()
    sma50, sma200 = b.iloc[-50:].mean(), b.iloc[-200:].mean()
    up = b.iloc[-1] > sma200 and sma50 > sma200
    down = b.iloc[-1] < sma200 and sma50 < sma200
    out.append(_ind("Global trend (ACWI)", f"{b.iloc[-1] / sma200 - 1:+.1%} vs 200d",
                    ON if up else OFF if down else NEUTRAL,
                    "Price and 50d above 200d average" if up else "Below 200d average" if down else "Mixed trend"))

    for key, tickers in groups.items():
        h = breadth_history(closes, tickers)
        if h.empty:
            continue
        breadth[labels[key]] = h
        v = h.iloc[-1]
        st = ON if v >= cfg["breadth_strong"] else OFF if v <= cfg["breadth_weak"] else NEUTRAL
        chg = v - h.iloc[-22] if len(h) > 22 else 0
        out.append(_ind(f"Breadth – {labels[key]}", f"{v:.0f}% > 200d", st, f"{chg:+.0f} pts over 1 month"))

    if vix_ticker in closes:
        v = closes[vix_ticker].dropna().iloc[-1]
        st = ON if v < cfg["vix_calm"] else OFF if v > cfg["vix_stress"] else NEUTRAL
        out.append(_ind("Volatility (VIX)", f"{v:.1f}", st, f"Calm < {cfg['vix_calm']}, stress > {cfg['vix_stress']}"))

    if "BAMLH0A0HYM2" in fred:
        s = fred["BAMLH0A0HYM2"].dropna()
        avg = s.iloc[-126:].mean()
        st = ON if s.iloc[-1] < avg * 0.97 else OFF if s.iloc[-1] > avg * 1.03 else NEUTRAL
        out.append(_ind("Credit (US HY spread)", f"{s.iloc[-1]:.2f}%", st,
                        f"6m average {avg:.2f}% – tightening spreads support risk"))

    if "T10Y2Y" in fred:
        s = fred["T10Y2Y"].dropna()
        out.append(_ind("Yield curve (10Y-2Y)", f"{s.iloc[-1]:+.2f}%", NEUTRAL,
                        "Inverted" if s.iloc[-1] < 0 else f"{s.iloc[-1] - s.iloc[-63]:+.2f} over 3m"))

    if "DGS10" in fred:
        s = fred["DGS10"].dropna()
        out.append(_ind("US 10Y yield", f"{s.iloc[-1]:.2f}%", NEUTRAL, f"{s.iloc[-1] - s.iloc[-63]:+.2f} over 3m"))

    if "DTWEXBGS" in fred:
        s = fred["DTWEXBGS"].dropna()
        chg = s.iloc[-1] / s.iloc[-63] - 1
        st = OFF if chg > 0.03 else ON if chg < -0.03 else NEUTRAL
        out.append(_ind("US dollar (broad)", f"{chg:+.1%} over 3m", st,
                        "A sharply rising USD tends to tighten global conditions"))

    return out, breadth


def overall(inds: list[dict]) -> dict:
    on = sum(i["status"] == ON for i in inds)
    off = sum(i["status"] == OFF for i in inds)
    scored = on + off
    net = (on - off) / scored if scored else 0
    label = "Risk-on" if net > 0.33 else "Risk-off" if net < -0.33 else "Mixed"
    return {"label": label, "on": on, "off": off, "neutral": len(inds) - scored, "net": round(net, 2)}

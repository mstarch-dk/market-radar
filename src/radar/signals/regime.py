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


def net_highs_lows(closes: pd.DataFrame, tickers: list[str], window: int = 252, smooth: int = 10) -> pd.Series:
    """% of tickers at a 52-week closing high minus % at a 52-week low (smoothed), over time."""
    c = closes[[t for t in tickers if t in closes.columns]]
    hi = c >= c.rolling(window, min_periods=window).max()
    lo = c <= c.rolling(window, min_periods=window).min()
    valid = c.rolling(window, min_periods=window).max().notna().sum(axis=1)
    net = 100 * (hi.sum(axis=1) - lo.sum(axis=1)) / valid
    return net.where(valid > 0).dropna().rolling(smooth).mean().dropna()


def _chg(s: pd.Series, n: int) -> float:
    return s.iloc[-1] - s.iloc[-1 - n] if len(s) > n else float("nan")


def _ind(name, value, status, note):
    return {"name": name, "value": value, "status": status, "note": note}


def indicators(closes: pd.DataFrame, fred: pd.DataFrame, bench: str, groups: dict, labels: dict,
               macro: dict[str, str], cfg: dict, cli: pd.DataFrame | None = None,
               factset: dict | None = None) -> tuple[list[dict], dict[str, pd.Series]]:
    """`macro` maps the names in universe.yaml macro.yahoo to tickers; `cli` is external.cli_table(),
    `factset` the latest external.load_factset() row."""
    out, breadth = [], {}
    vix_ticker, vix3m_ticker = macro.get("VIX"), macro.get("VIX3M")
    copper_ticker, gold_ticker, oil_ticker = macro.get("Copper"), macro.get("Gold"), macro.get("Oil (WTI)")

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
        h50 = breadth_history(closes, tickers, 50)
        short = f"; {h50.iloc[-1]:.0f}% above 50d" if not h50.empty else ""
        out.append(_ind(f"Breadth – {labels[key]}", f"{v:.0f}% > 200d", st, f"{chg:+.0f} pts over 1 month{short}"))

    everyone = sorted({t for ts in groups.values() for t in ts})
    hl = net_highs_lows(closes, everyone)
    if not hl.empty:
        v = hl.iloc[-1]
        st = ON if v >= cfg["highs_lows_band"] else OFF if v <= -cfg["highs_lows_band"] else NEUTRAL
        out.append(_ind("New highs – new lows (all stocks)", f"{v:+.1f}%", st,
                        f"Net % of stocks at 52w highs, 10d avg; {_chg(hl, 21):+.1f} pts over 1 month"))

    if {"RSP", "SPY"} <= set(closes.columns):
        r = (closes["RSP"] / closes["SPY"]).dropna()
        chg = r.iloc[-1] / r.iloc[-64] - 1
        note = ("Broadening: the average stock is beating the index" if chg > 0
                else "Narrow: mega caps are carrying the index")
        out.append(_ind("Equal vs cap weight (RSP/SPY)", f"{chg:+.1%} over 3m", NEUTRAL, note))

    if vix_ticker in closes:
        v = closes[vix_ticker].dropna().iloc[-1]
        st = ON if v < cfg["vix_calm"] else OFF if v > cfg["vix_stress"] else NEUTRAL
        out.append(_ind("Volatility (VIX)", f"{v:.1f}", st, f"Calm < {cfg['vix_calm']}, stress > {cfg['vix_stress']}"))
        if vix3m_ticker in closes:
            r = (closes[vix_ticker] / closes[vix3m_ticker]).dropna().iloc[-1]
            st = OFF if r > 1 else ON if r < cfg["vix_term_calm"] else NEUTRAL
            out.append(_ind("VIX term structure (VIX/VIX3M)", f"{r:.2f}", st,
                            "Inverted: near-term fear above 3-month" if r > 1
                            else f"Normal upward slope; calm below {cfg['vix_term_calm']}"))

    if "BAMLH0A0HYM2" in fred:
        s = fred["BAMLH0A0HYM2"].dropna()
        avg = s.iloc[-126:].mean()
        st = ON if s.iloc[-1] < avg * 0.97 else OFF if s.iloc[-1] > avg * 1.03 else NEUTRAL
        trend = "widening (stress building)" if s.iloc[-1] > avg else "tightening (supports risk)"
        out.append(_ind("Credit (US HY spread)", f"{s.iloc[-1]:.2f}%", st, f"vs 6m average {avg:.2f}%: {trend}"))

    if "T10Y2Y" in fred:
        s = fred["T10Y2Y"].dropna()
        inverted = s.iloc[-1] < 0
        out.append(_ind("Yield curve (10Y-2Y)", f"{s.iloc[-1]:+.2f}%", OFF if inverted else NEUTRAL,
                        f"{'Inverted; ' if inverted else ''}{_chg(s, 63):+.2f} over 3m"))

    if "DGS10" in fred:
        s = fred["DGS10"].dropna()
        chg = _chg(s, 63)
        shock = chg > cfg["rates_shock"]
        out.append(_ind("US 10Y yield", f"{s.iloc[-1]:.2f}%", OFF if shock else NEUTRAL,
                        f"{chg:+.2f} over 3m" + (": a fast rise tightens conditions" if shock
                                                 else f"; risk-off if it rises > {cfg['rates_shock']} pts in 3m")))

    if "DTWEXBGS" in fred:
        s = fred["DTWEXBGS"].dropna()
        chg = s.iloc[-1] / s.iloc[-63] - 1
        st = OFF if chg > 0.03 else ON if chg < -0.03 else NEUTRAL
        out.append(_ind("US dollar (broad)", f"{chg:+.1%} over 3m", st,
                        "A sharply rising USD tends to tighten global conditions"))

    if copper_ticker in closes and gold_ticker in closes:
        r = (closes[copper_ticker] / closes[gold_ticker]).dropna()
        chg = r.iloc[-1] / r.iloc[-64] - 1
        band = cfg["copper_gold_band"]
        st = ON if chg > band else OFF if chg < -band else NEUTRAL
        out.append(_ind("Copper/gold ratio", f"{chg:+.1%} over 3m", st, "Rising = growth over defence"))

    if oil_ticker in closes:
        o = closes[oil_ticker].dropna()
        chg = o.iloc[-1] / o.iloc[-64] - 1
        shock = chg > cfg["oil_shock"]
        out.append(_ind("Oil (WTI)", f"{chg:+.1%} over 3m", OFF if shock else NEUTRAL,
                        "Oil shock: inflation and margin risk" if shock
                        else f"Risk-off above +{cfg['oil_shock']:.0%} in 3m"))

    if cli is not None and not cli.empty:
        lead = cli.iloc[0]  # the first configured area (G20) carries the vote
        st = ON if lead["phase"] == "Expansion" else OFF if lead["phase"] == "Contraction" else NEUTRAL
        others = "; ".join(f"{r.label} {r.phase.lower()}" for r in cli.iloc[1:].itertuples())
        out.append(_ind(f"Leading indicators (OECD CLI, {lead['label']})",
                        f"{lead['cli']:.1f} ({lead['chg_3m']:+.2f} 3m)", st,
                        f"{lead['phase']} as of {lead['asof']:%b %Y}. {others}"))

    if factset and factset.get("growth_now") is not None and factset.get("growth_start") is not None:
        rev = factset["growth_now"] - factset["growth_start"]
        band = cfg["revisions_band"]
        st = ON if rev > band else OFF if rev < -band else NEUTRAL
        guid = (f"; guidance +{factset['guidance_pos']:.0f} / -{factset['guidance_neg']:.0f}"
                if factset.get("guidance_pos") is not None and factset.get("guidance_neg") is not None else "")
        out.append(_ind(f"Earnings revisions (S&P 500, {factset.get('quarter') or 'current qtr'})",
                        f"{rev:+.1f} pts", st,
                        f"Growth est. {factset['growth_now']:.1f}% vs {factset['growth_start']:.1f}% at quarter start"
                        f"{guid} (FactSet {factset['report_date']:%d %b})"))

    return out, breadth


def overall(inds: list[dict]) -> dict:
    on = sum(i["status"] == ON for i in inds)
    off = sum(i["status"] == OFF for i in inds)
    scored = on + off
    net = (on - off) / scored if scored else 0
    label = "Risk-on" if net > 0.33 else "Risk-off" if net < -0.33 else "Mixed"
    return {"label": label, "on": on, "off": off, "neutral": len(inds) - scored, "net": round(net, 2)}

"""Market regime: a handful of transparent risk-on / risk-off indicators."""
from __future__ import annotations

import pandas as pd

from ..config import typed
from . import gauges as gz
from . import momentum

ON, OFF, NEUTRAL = "risk-on", "risk-off", "neutral"
NA, STALE = "n/a", "stale"  # no data / too old: shown, but not counted in the vote
CONTEXT = "context"  # the group of rows shown for context only: never in the vote, and no switch for it


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


def momentum_payoff(closes: pd.DataFrame, tickers: list[str], n: int, min_names: int = 30) -> float:
    """What the momentum score paid over the last `n` sessions: the mean return of the top score quintile minus
    the bottom quintile, with the score computed from prices up to `n` sessions ago (equal weights, listing
    currency). NaN with fewer than `min_names` scored names or too little history."""
    c = closes[[t for t in tickers if t in closes.columns]]
    if len(c) <= n + 252:
        return float("nan")
    m = momentum.metrics(c.iloc[:len(c) - n], pd.DataFrame(), list(c.columns), typed().momentum.min_history_days)
    s = momentum.score(m).set_axis(m["ticker"])
    fwd = c.iloc[-1] / c.iloc[-1 - n] - 1
    d = pd.concat({"s": s, "y": fwd}, axis=1).dropna()
    if len(d) < min_names:
        return float("nan")
    q = pd.qcut(d["s"].rank(method="first"), 5, labels=False)
    return float(d["y"][q == 4].mean() - d["y"][q == 0].mean())


def dispersion_history(closes: pd.DataFrame, tickers: list[str], n: int = 63, min_names: int = 30) -> pd.Series:
    """The spread of `n`-session returns across stocks (75th minus 25th percentile), over time."""
    c = closes[[t for t in tickers if t in closes.columns]]
    r = c / c.shift(n) - 1
    iqr = r.quantile(0.75, axis=1) - r.quantile(0.25, axis=1)
    return iqr.where(r.notna().sum(axis=1) >= min_names).dropna()


def _ordinal(x: float) -> str:
    n = int(round(x))
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _chg(s: pd.Series, n: int) -> float:
    return s.iloc[-1] - s.iloc[-1 - n] if len(s) > n else float("nan")


def _ret(s: pd.Series, n: int) -> float:
    return s.iloc[-1] / s.iloc[-1 - n] - 1 if len(s) > n else float("nan")


SHORT = "less than 3 months of history"


def _ind(name, value, status, note, source="prices", asof=None, gauge=None, group=None):
    """One regime row. `source` is the data source key (coverage.py), `asof` the last data point used,
    `gauge` the reading graded between the same thresholds the vote uses (gauges.make; display only).
    `group` names a switchable set of rows (settings.yaml regime.votes); None = always votes, CONTEXT = never."""
    return {"name": name, "value": value, "status": status, "note": note, "source": source,
            "asof": None if asof is None else pd.Timestamp(asof).date().isoformat(), "gauge": gauge,
            "group": group, "votes": group != CONTEXT}


def _na(name, source, note="no data", group=None):
    """A configured indicator without data: shown, but not counted."""
    return _ind(name, "–", NA, note, source, group=group)


def _last(s: pd.Series):
    return s.index[-1] if len(s) else None


def indicators(closes: pd.DataFrame, fred: pd.DataFrame, bench: str, groups: dict, labels: dict,
               macro: dict[str, str], cfg: dict, cli: pd.DataFrame | None = None,
               factset: dict | None = None, market_val: dict | None = None) -> tuple[list[dict], dict[str, pd.Series]]:
    """`macro` maps the names in universe.yaml macro.yahoo to tickers; `cli` is external.cli_table(),
    `factset` the latest external.load_factset() row, `market_val` signals.valuation.market(). An indicator
    whose input is missing stays as an "n/a" row, so the page shows what the reading is not based on."""
    out, breadth = [], {}
    vix_ticker, vix3m_ticker = macro.get("VIX"), macro.get("VIX3M")
    copper_ticker, gold_ticker, oil_ticker = macro.get("Copper"), macro.get("Gold"), macro.get("Oil (WTI)")

    b = closes[bench].dropna()
    sma50, sma200 = b.iloc[-50:].mean(), b.iloc[-200:].mean()
    up = b.iloc[-1] > sma200 and sma50 > sma200
    down = b.iloc[-1] < sma200 and sma50 < sma200
    out.append(_ind("Global trend (ACWI)", f"{b.iloc[-1] / sma200 - 1:+.1%} vs 200d",
                    ON if up else OFF if down else NEUTRAL,
                    "Price and 50d above 200d average" if up else "Below 200d average" if down else "Mixed trend",
                    asof=_last(b), gauge=gz.make(gz.band(-0.05, 0.05, ("downtrend", "flat", "uptrend")), b.iloc[-1] / sma200 - 1)))

    for key, tickers in groups.items():
        h = breadth_history(closes, tickers)
        if h.empty:
            out.append(_na(f"Breadth – {labels[key]}", "prices", "no stocks with 200 days of history"))
            continue
        breadth[labels[key]] = h
        v = h.iloc[-1]
        st = ON if v >= cfg["breadth_strong"] else OFF if v <= cfg["breadth_weak"] else NEUTRAL
        chg = v - h.iloc[-22] if len(h) > 22 else 0
        h50 = breadth_history(closes, tickers, 50)
        short = f"; {h50.iloc[-1]:.0f}% above 50d" if not h50.empty else ""
        n = sum(t in closes.columns for t in tickers)
        out.append(_ind(f"Breadth – {labels[key]}", f"{v:.0f}% > 200d", st,
                        f"{chg:+.0f} pts over 1 month{short}; {n} of {len(tickers)} stocks have prices",
                        asof=_last(h), gauge=gz.make(gz.band(cfg["breadth_weak"], cfg["breadth_strong"],
                                                             ("weak", "neutral", "strong")), v)))

    everyone = sorted({t for ts in groups.values() for t in ts})
    hl = net_highs_lows(closes, everyone)
    if not hl.empty:
        v = hl.iloc[-1]
        st = ON if v >= cfg["highs_lows_band"] else OFF if v <= -cfg["highs_lows_band"] else NEUTRAL
        out.append(_ind("New highs – new lows (all stocks)", f"{v:+.1f}%", st,
                        f"Net % of stocks at 52w highs, 10d avg; {_chg(hl, 21):+.1f} pts over 1 month",
                        asof=_last(hl), gauge=gz.make(gz.band(-cfg["highs_lows_band"], cfg["highs_lows_band"],
                                                              ("more new lows", "balanced", "more new highs")), v)))
    else:
        out.append(_na("New highs – new lows (all stocks)", "prices", "no stocks with a year of history"))

    if {"RSP", "SPY"} <= set(closes.columns):
        r = (closes["RSP"] / closes["SPY"]).dropna()
        chg = _ret(r, 63)
        note = ("Broadening: the average stock is beating the index" if chg > 0
                else "Narrow: mega caps are carrying the index")
        out.append(_ind("Equal vs cap weight (RSP/SPY)", f"{chg:+.1%} over 3m", NEUTRAL, note, asof=_last(r),
                        gauge=gz.make(gz.band(-0.03, 0.03, ("narrowing", "even", "broadening")), chg))
                   if pd.notna(chg) else _na("Equal vs cap weight (RSP/SPY)", "prices", SHORT))
    else:
        out.append(_na("Equal vs cap weight (RSP/SPY)", "prices"))

    # the momentum factor itself: shown for context, never in the vote
    pay3, pay1 = momentum_payoff(closes, everyone, 63), momentum_payoff(closes, everyone, 21)
    if pd.notna(pay3):
        band = cfg["momentum_payoff_band"]
        mt = ""
        if "MTUM" in closes.columns and bench in closes.columns:
            rel = _ret(closes["MTUM"].dropna(), 63) - _ret(b, 63)
            mt = f"; MTUM vs ACWI {rel:+.1%}" if pd.notna(rel) else ""
        out.append(_ind("Momentum payoff (top − bottom quintile)", f"{pay3:+.1%} over 3m", NEUTRAL,
                        "The score's top fifth minus its bottom fifth, scored 3 months ago"
                        + (f"; {pay1:+.1%} over 1m" if pd.notna(pay1) else "") + mt + ". Context, not a vote",
                        asof=_last(b), gauge=gz.make(gz.band(-band, band, ("losing", "flat", "paying")), pay3), group=CONTEXT))
    else:
        out.append(_na("Momentum payoff (top − bottom quintile)", "prices", "less than 15 months of history", CONTEXT))
    disp = dispersion_history(closes, everyone)
    if len(disp) >= 126:
        v = disp.iloc[-1]
        pct = 100 * float((disp < v).mean())
        lo, hi = cfg["dispersion_low_pct"], cfg["dispersion_high_pct"]
        out.append(_ind("Return dispersion (3m, all stocks)", f"{v:.1%}", NEUTRAL,
                        f"Spread between the 75th and 25th percentile 3-month return; {_ordinal(pct)} percentile since "
                        f"{disp.index[0]:%Y}. Wide spreads give momentum more to sort on. Context, not a vote",
                        asof=_last(disp), gauge=gz.make(gz.band(lo, hi, ("narrow", "normal", "wide")), pct), group=CONTEXT))
    else:
        out.append(_na("Return dispersion (3m, all stocks)", "prices", "less than 9 months of history", CONTEXT))
    r24, r1 = _ret(b, 504), _ret(b, 21)
    if pd.notna(r24):
        bear = r24 < 0
        setup = bear and r1 >= cfg["crash_rebound"]
        note = (f"ACWI {r24:+.1%} over 2 years and {r1:+.1%} over 1 month: "
                + ("a sharp rebound after a bear market, when momentum has crashed hardest historically" if setup
                   else "a bear market: a sharp rebound would hit momentum's winners" if bear
                   else "no bear market behind it") + ". Context, not a vote")
        out.append(_ind("Momentum-crash setup (ACWI)", "yes" if setup else "watch" if bear else "no", NEUTRAL, note,
                        asof=_last(b), gauge=gz.make(gz.rising_risk(0.5, 1.5, ("no", "watch", "watch", "setup")),
                                                     2.0 if setup else 1.0 if bear else 0.0), group=CONTEXT))
    else:
        out.append(_na("Momentum-crash setup (ACWI)", "prices", "less than 2 years of ACWI history", CONTEXT))

    if vix_ticker in closes:
        s = closes[vix_ticker].dropna()
        v = s.iloc[-1]
        st = ON if v < cfg["vix_calm"] else OFF if v > cfg["vix_stress"] else NEUTRAL
        out.append(_ind("Volatility (VIX)", f"{v:.1f}", st, f"Calm < {cfg['vix_calm']}, stress > {cfg['vix_stress']}",
                        asof=_last(s), gauge=gz.make(gz.rising_risk(cfg["vix_calm"], cfg["vix_stress"],
                                                                    ("calm", "normal", "elevated", "stress")), v)))
    else:
        out.append(_na("Volatility (VIX)", "prices"))
    if vix_ticker in closes and vix3m_ticker in closes:
        s = (closes[vix_ticker] / closes[vix3m_ticker]).dropna()
        r = s.iloc[-1]
        st = OFF if r > 1 else ON if r < cfg["vix_term_calm"] else NEUTRAL
        out.append(_ind("VIX term structure (VIX/VIX3M)", f"{r:.2f}", st,
                        "Inverted: near-term fear above 3-month" if r > 1
                        else f"Normal upward slope; calm below {cfg['vix_term_calm']}", asof=_last(s),
                        gauge=gz.make(gz.rising_risk(cfg["vix_term_calm"], 1.0, ("calm", "normal", "flattening", "inverted")), r)))
    else:
        out.append(_na("VIX term structure (VIX/VIX3M)", "prices"))

    def series(sid):
        return fred[sid].dropna() if sid in fred else pd.Series(dtype=float)

    s = series("BAMLH0A0HYM2")
    if len(s):
        avg = s.iloc[-126:].mean()
        st = ON if s.iloc[-1] < avg * 0.97 else OFF if s.iloc[-1] > avg * 1.03 else NEUTRAL
        trend = "widening (stress building)" if s.iloc[-1] > avg else "tightening (supports risk)"
        out.append(_ind("Credit (US HY spread)", f"{s.iloc[-1]:.2f}%", st, f"vs 6m average {avg:.2f}%: {trend}",
                        "fred", _last(s), gz.make(gz.band(1.03, 0.97, ("widening", "steady", "tightening")), s.iloc[-1] / avg)))
    else:
        out.append(_na("Credit (US HY spread)", "fred"))

    s = series("BAMLHE00EHYIOAS")
    if len(s) > 63:
        avg = s.iloc[-126:].mean()
        st = ON if s.iloc[-1] < avg * 0.97 else OFF if s.iloc[-1] > avg * 1.03 else NEUTRAL
        trend = "widening (stress building)" if s.iloc[-1] > avg else "tightening (supports risk)"
        out.append(_ind("Euro credit (HY spread)", f"{s.iloc[-1]:.2f}%", st, f"vs 6m average {avg:.2f}%: {trend}",
                        "fred", _last(s), gz.make(gz.band(1.03, 0.97, ("widening", "steady", "tightening")), s.iloc[-1] / avg),
                        group="credit_eu"))
    else:
        out.append(_na("Euro credit (HY spread)", "fred", group="credit_eu"))

    s = series("T10Y2Y")
    if len(s):
        inverted = s.iloc[-1] < 0
        out.append(_ind("Yield curve (10Y-2Y)", f"{s.iloc[-1]:+.2f}%", OFF if inverted else NEUTRAL,
                        f"{'Inverted; ' if inverted else ''}{_chg(s, 63):+.2f} over 3m", "fred", _last(s),
                        gz.make(gz.band(0.0, 0.75, ("inverted", "flat", "steep")), s.iloc[-1])))
    else:
        out.append(_na("Yield curve (10Y-2Y)", "fred"))

    s = series("DGS10")
    if len(s):
        chg = _chg(s, 63)
        shock = chg > cfg["rates_shock"]
        out.append(_ind("US 10Y yield", f"{s.iloc[-1]:.2f}%", OFF if shock else NEUTRAL,
                        f"{chg:+.2f} over 3m" + (": a fast rise tightens conditions" if shock
                                                 else f"; risk-off if it rises > {cfg['rates_shock']} pts in 3m"),
                        "fred", _last(s), gz.make(gz.rising_risk(cfg["rates_shock"] * 0.4, cfg["rates_shock"],
                                                                 ("steady", "rising", "fast rise", "rate shock")), chg)))
    else:
        out.append(_na("US 10Y yield", "fred"))

    s = series("DTWEXBGS")
    if len(s) > 63:
        chg = _ret(s, 63)
        st = OFF if chg > 0.03 else ON if chg < -0.03 else NEUTRAL
        out.append(_ind("US dollar (broad)", f"{chg:+.1%} over 3m", st,
                        "A sharply rising USD tends to tighten global conditions", "fred", _last(s),
                        gz.make(gz.band(0.03, -0.03, ("rising fast", "stable", "falling")), chg)))
    else:
        out.append(_na("US dollar (broad)", "fred"))

    if copper_ticker in closes and gold_ticker in closes:
        r = (closes[copper_ticker] / closes[gold_ticker]).dropna()
        chg = _ret(r, 63)
        band = cfg["copper_gold_band"]
        st = ON if chg > band else OFF if chg < -band else NEUTRAL
        out.append(_ind("Copper/gold ratio", f"{chg:+.1%} over 3m", st, "Rising = growth over defence",
                        asof=_last(r), gauge=gz.make(gz.band(-band, band, ("defensive", "neutral", "growth")), chg))
                   if pd.notna(chg) else _na("Copper/gold ratio", "prices", SHORT))
    else:
        out.append(_na("Copper/gold ratio", "prices"))

    if oil_ticker in closes:
        o = closes[oil_ticker].dropna()
        chg = _ret(o, 63)
        shock = chg > cfg["oil_shock"]
        out.append(_ind("Oil (WTI)", f"{chg:+.1%} over 3m", OFF if shock else NEUTRAL,
                        "Oil shock: inflation and margin risk" if shock
                        else f"Risk-off above +{cfg['oil_shock']:.0%} in 3m", asof=_last(o),
                        gauge=gz.make(gz.rising_risk(cfg["oil_shock"] / 2, cfg["oil_shock"],
                                                     ("calm", "rising", "fast rise", "oil shock")), chg))
                   if pd.notna(chg) else _na("Oil (WTI)", "prices", SHORT))
    else:
        out.append(_na("Oil (WTI)", "prices"))

    if cli is not None and not cli.empty:
        lead = cli.iloc[0]  # the first configured area (G20) carries the vote
        st = ON if lead["phase"] == "Expansion" else OFF if lead["phase"] == "Contraction" else NEUTRAL
        others = "; ".join(f"{r.label} {r.phase.lower()}" for r in cli.iloc[1:].itertuples())
        out.append(_ind(f"Leading indicators (OECD CLI, {lead['label']})",
                        f"{lead['cli']:.1f} ({lead['chg_3m']:+.2f} 3m)", st,
                        f"{lead['phase']} as of {lead['asof']:%b %Y}. {others}", "oecd", lead["asof"],
                        gz.gauge("cli_chg", lead["chg_3m"])))
    else:
        out.append(_na("Leading indicators (OECD CLI)", "oecd"))

    if factset and pd.notna(factset.get("growth_now")) and pd.notna(factset.get("growth_start")):  # NaN from parquet
        rev = factset["growth_now"] - factset["growth_start"]
        band = cfg["revisions_band"]
        st = ON if rev > band else OFF if rev < -band else NEUTRAL
        guid = (f"; guidance +{factset['guidance_pos']:.0f} / -{factset['guidance_neg']:.0f}"
                if factset.get("guidance_pos") is not None and factset.get("guidance_neg") is not None else "")
        quarter = factset.get("quarter") if pd.notna(factset.get("quarter")) else "current qtr"
        out.append(_ind(f"Earnings revisions (S&P 500, {quarter})",
                        f"{rev:+.1f} pts", st,
                        f"Growth est. {factset['growth_now']:.1f}% vs {factset['growth_start']:.1f}% at quarter start"
                        f"{guid} (FactSet {factset['report_date']:%d %b})", "factset", factset["report_date"],
                        gz.make(gz.band(-band, band, ("cut", "stable", "raised")), rev)))
    else:
        out.append(_na("Earnings revisions (S&P 500)", "factset",
                       "the latest FactSet report's growth figures could not be read" if factset else "no data"))

    mv = market_val or {}
    c = mv.get("cape")
    if c and c.get("pct_all") is not None:
        pct = c["pct_all"]
        st = OFF if pct >= cfg["cape_rich_pct"] else ON if pct <= cfg["cape_cheap_pct"] else NEUTRAL
        out.append(_ind("Valuation (Shiller CAPE, US)", f"{c['value']:.1f}", st,
                        f"{pct:.0f}th percentile since {c['since'][:4]} ({c['pct_1990']:.0f}th since 1990), median "
                        f"{c['median']:.1f}; risk-off at or above the {cfg['cape_rich_pct']}th", "cape", c["asof"],
                        gz.gauge("cape_pct", pct), group="valuation"))
    else:
        out.append(_na("Valuation (Shiller CAPE, US)", "cape", group="valuation"))
    e = mv.get("erp")
    if e and e.get("pct") is not None:
        pct = e["pct"]
        st = OFF if pct <= cfg["erp_low_pct"] else ON if pct >= cfg["erp_high_pct"] else NEUTRAL
        out.append(_ind("Equity risk premium (Damodaran, S&P 500)", f"{e['value']:.2%}", st,
                        f"{pct:.0f}th percentile since {e['since'][:4]}, median {e['median']:.2%}; "
                        f"risk-off at or below the {cfg['erp_low_pct']}th", "erp", e["asof"],
                        gz.gauge("erp_pct", pct), group="valuation"))
    else:
        out.append(_na("Equity risk premium (Damodaran, S&P 500)", "erp", group="valuation"))

    return out, breadth


def apply_freshness(inds: list[dict], ref, max_age: dict) -> list[dict]:
    """Rows whose data is more than their source's max age (days) before `ref` turn "stale": the reading
    stays visible but no longer counts in the vote."""
    ref = pd.Timestamp(ref)
    for i in inds:
        limit = max_age.get(i.get("source"))
        if i["status"] == NA or i.get("asof") is None or limit is None:
            continue
        if (ref - pd.Timestamp(i["asof"])).days > limit:
            i["status"] = STALE
            i["note"] += f" (data from {pd.Timestamp(i['asof']):%d %b %Y}, older than {limit} days: not counted)"
    return inds


def apply_votes(inds: list[dict], votes: dict[str, bool]) -> list[dict]:
    """Mark each row voting or not: a row in a group switched off (settings.yaml regime.votes, or your choice on
    the Regime page) keeps its reading but leaves the vote. Rows without a group always vote; CONTEXT rows never."""
    for i in inds:
        g = i.get("group")
        i["votes"] = g is None or (g != CONTEXT and bool(votes.get(g, True)))
    return inds


def overall(inds: list[dict], votes: dict[str, bool] | None = None) -> dict:
    """Net vote of the voting risk-on / risk-off rows. Neutral rows inform; n/a and stale rows don't count at
    all, and nor do CONTEXT rows or rows whose group is switched off in `votes`."""
    if votes is not None:
        apply_votes(inds, votes)
    voting = [i for i in inds if i.get("votes", True)]
    count = {s: sum(i["status"] == s for i in voting) for s in (ON, OFF, NEUTRAL, NA, STALE)}
    on, off = count[ON], count[OFF]
    scored = on + off
    net = (on - off) / scored if scored else 0
    label = "Risk-on" if net > 0.33 else "Risk-off" if net < -0.33 else "Mixed"
    groups = sorted({i["group"] for i in inds if i.get("group") not in (None, CONTEXT)})
    return {"label": label, "on": on, "off": off, "neutral": count[NEUTRAL], "na": count[NA],
            "stale": count[STALE], "total": len(voting), "net": round(net, 2),
            "not_voting": len(inds) - len(voting),
            "voting_groups": [g for g in groups if any(i.get("votes", True) for i in inds if i.get("group") == g)]}

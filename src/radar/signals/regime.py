"""Market regime: a handful of transparent risk-on / risk-off indicators."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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


@dataclass(frozen=True)
class Inputs:
    """What the regime rows read. `macro` maps the names in universe.yaml macro.yahoo to tickers; `cli` is
    external.cli_table(), `factset` the latest external.load_factset() row, `market_val` signals.valuation.market()."""
    closes: pd.DataFrame
    fred: pd.DataFrame
    bench: str
    everyone: list[str]
    cfg: dict
    macro: dict[str, str]
    cli: pd.DataFrame | None = None
    factset: dict | None = None
    market_val: dict | None = None

    @property
    def b(self) -> pd.Series:
        return self.closes[self.bench].dropna()

    def yahoo(self, name: str) -> pd.Series | None:
        """The closes of a macro.yahoo name, or None when it isn't configured or not in the price store."""
        t = self.macro.get(name)
        return self.closes[t].dropna() if t in self.closes else None

    def series(self, sid: str) -> pd.Series:
        return self.fred[sid].dropna() if sid in self.fred else pd.Series(dtype=float)


@dataclass(frozen=True)
class Reading:
    """One row's reading; `name` replaces the spec's name when the row names its own subject (area, quarter)."""
    value: str
    status: str
    note: str
    asof: Any = None
    gauge: dict | None = None
    name: str | None = None


@dataclass(frozen=True)
class IndicatorSpec:
    """One regime row: `read` gives its reading, or a str saying why the row is n/a."""
    name: str
    read: Callable[[Inputs], Reading | str]
    source: str = "prices"
    group: str | None = None


def _trend(x: Inputs) -> Reading:
    b = x.b
    sma50, sma200 = b.iloc[-50:].mean(), b.iloc[-200:].mean()
    up = b.iloc[-1] > sma200 and sma50 > sma200
    down = b.iloc[-1] < sma200 and sma50 < sma200
    return Reading(f"{b.iloc[-1] / sma200 - 1:+.1%} vs 200d", ON if up else OFF if down else NEUTRAL,
                   "Price and 50d above 200d average" if up else "Below 200d average" if down else "Mixed trend",
                   _last(b), gz.make(gz.band(-0.05, 0.05, ("downtrend", "flat", "uptrend")), b.iloc[-1] / sma200 - 1))


def _breadth(x: Inputs, label: str, tickers: list[str]) -> tuple[dict, pd.Series]:
    name, cfg = f"Breadth – {label}", x.cfg
    h = breadth_history(x.closes, tickers)
    if h.empty:
        return _na(name, "prices", "no stocks with 200 days of history"), h
    v = h.iloc[-1]
    st = ON if v >= cfg["breadth_strong"] else OFF if v <= cfg["breadth_weak"] else NEUTRAL
    month = f"{v - h.iloc[-22]:+.0f} pts over 1 month" if len(h) > 22 else "less than a month of history"
    h50 = breadth_history(x.closes, tickers, 50)
    short = f"; {h50.iloc[-1]:.0f}% above 50d" if not h50.empty else ""
    n = sum(t in x.closes.columns for t in tickers)
    return _ind(name, f"{v:.0f}% > 200d", st, f"{month}{short}; {n} of {len(tickers)} stocks have prices",
                asof=_last(h), gauge=gz.make(gz.band(cfg["breadth_weak"], cfg["breadth_strong"],
                                                     ("weak", "neutral", "strong")), v)), h


def _highs_lows(x: Inputs) -> Reading | str:
    hl = net_highs_lows(x.closes, x.everyone)
    if hl.empty:
        return "no stocks with a year of history"
    v, band = hl.iloc[-1], x.cfg["highs_lows_band"]
    return Reading(f"{v:+.1f}%", ON if v >= band else OFF if v <= -band else NEUTRAL,
                   f"Net % of stocks at 52w highs, 10d avg; {_chg(hl, 21):+.1f} pts over 1 month", _last(hl),
                   gz.make(gz.band(-band, band, ("more new lows", "balanced", "more new highs")), v))


def _equal_weight(x: Inputs) -> Reading | str:
    if not {"RSP", "SPY"} <= set(x.closes.columns):
        return "no data"
    r = (x.closes["RSP"] / x.closes["SPY"]).dropna()
    chg = _ret(r, 63)
    if pd.isna(chg):
        return SHORT
    return Reading(f"{chg:+.1%} over 3m", NEUTRAL,
                   "Broadening: the average stock is beating the index" if chg > 0
                   else "Narrow: mega caps are carrying the index",
                   _last(r), gz.make(gz.band(-0.03, 0.03, ("narrowing", "even", "broadening")), chg))


def _momentum_payoff(x: Inputs) -> Reading | str:
    pay3, pay1 = momentum_payoff(x.closes, x.everyone, 63), momentum_payoff(x.closes, x.everyone, 21)
    if pd.isna(pay3):
        return "less than 15 months of history"
    band, b, mt = x.cfg["momentum_payoff_band"], x.b, ""
    if "MTUM" in x.closes.columns:
        rel = _ret(x.closes["MTUM"].dropna(), 63) - _ret(b, 63)
        mt = f"; MTUM vs ACWI {rel:+.1%}" if pd.notna(rel) else ""
    return Reading(f"{pay3:+.1%} over 3m", NEUTRAL,
                   "The score's top fifth minus its bottom fifth, scored 3 months ago"
                   + (f"; {pay1:+.1%} over 1m" if pd.notna(pay1) else "") + mt + ". Context, not a vote",
                   _last(b), gz.make(gz.band(-band, band, ("losing", "flat", "paying")), pay3))


def _dispersion(x: Inputs) -> Reading | str:
    disp = dispersion_history(x.closes, x.everyone)
    if len(disp) < 126:
        return "less than 9 months of history"
    v = disp.iloc[-1]
    pct = 100 * float((disp < v).mean())
    lo, hi = x.cfg["dispersion_low_pct"], x.cfg["dispersion_high_pct"]
    return Reading(f"{v:.1%}", NEUTRAL,
                   f"Spread between the 75th and 25th percentile 3-month return; {_ordinal(pct)} percentile since "
                   f"{disp.index[0]:%Y}. Wide spreads give momentum more to sort on. Context, not a vote",
                   _last(disp), gz.make(gz.band(lo, hi, ("narrow", "normal", "wide")), pct))


def _crash_setup(x: Inputs) -> Reading | str:
    b = x.b
    r24, r1 = _ret(b, 504), _ret(b, 21)
    if pd.isna(r24):
        return "less than 2 years of ACWI history"
    bear = r24 < 0
    setup = bear and r1 >= x.cfg["crash_rebound"]
    note = (f"ACWI {r24:+.1%} over 2 years and {r1:+.1%} over 1 month: "
            + ("a sharp rebound after a bear market, when momentum has crashed hardest historically" if setup
               else "a bear market: a sharp rebound would hit momentum's winners" if bear
               else "no bear market behind it") + ". Context, not a vote")
    return Reading("yes" if setup else "watch" if bear else "no", NEUTRAL, note, _last(b),
                   gz.make(gz.rising_risk(0.5, 1.5, ("no", "watch", "watch", "setup")),
                           2.0 if setup else 1.0 if bear else 0.0))


def _vix(x: Inputs) -> Reading | str:
    s = x.yahoo("VIX")
    if s is None or s.empty:
        return "no data"
    v, calm, stress = s.iloc[-1], x.cfg["vix_calm"], x.cfg["vix_stress"]
    return Reading(f"{v:.1f}", ON if v < calm else OFF if v > stress else NEUTRAL, f"Calm < {calm}, stress > {stress}",
                   _last(s), gz.make(gz.rising_risk(calm, stress, ("calm", "normal", "elevated", "stress")), v))


def _vix_term(x: Inputs) -> Reading | str:
    vix, vix3m = x.yahoo("VIX"), x.yahoo("VIX3M")
    if vix is None or vix3m is None:
        return "no data"
    s = (vix / vix3m).dropna()
    if s.empty:
        return "no data"
    r, calm = s.iloc[-1], x.cfg["vix_term_calm"]
    return Reading(f"{r:.2f}", OFF if r > 1 else ON if r < calm else NEUTRAL,
                   "Inverted: near-term fear above 3-month" if r > 1 else f"Normal upward slope; calm below {calm}",
                   _last(s), gz.make(gz.rising_risk(calm, 1.0, ("calm", "normal", "flattening", "inverted")), r))


def _spread_vs_avg(sid: str, min_obs: int = 63) -> Callable[[Inputs], Reading | str]:
    """A credit spread against its 6-month average: risk-on 3 % below it, risk-off 3 % above. Needs more than
    `min_obs` points, or the "average" is of a handful of days."""
    def read(x: Inputs) -> Reading | str:
        s = x.series(sid)
        if len(s) <= min_obs:
            return SHORT if len(s) else "no data"
        last, avg = s.iloc[-1], s.iloc[-126:].mean()
        trend = "widening (stress building)" if last > avg else "tightening (supports risk)"
        return Reading(f"{last:.2f}%", ON if last < avg * 0.97 else OFF if last > avg * 1.03 else NEUTRAL,
                       f"vs 6m average {avg:.2f}%: {trend}", _last(s),
                       gz.make(gz.band(1.03, 0.97, ("widening", "steady", "tightening")), last / avg))
    return read


def _curve(x: Inputs) -> Reading | str:
    s = x.series("T10Y2Y")
    if not len(s):
        return "no data"
    inverted = s.iloc[-1] < 0
    return Reading(f"{s.iloc[-1]:+.2f}%", OFF if inverted else NEUTRAL,
                   f"{'Inverted; ' if inverted else ''}{_chg(s, 63):+.2f} over 3m", _last(s),
                   gz.make(gz.band(0.0, 0.75, ("inverted", "flat", "steep")), s.iloc[-1]))


def _us10y(x: Inputs) -> Reading | str:
    s = x.series("DGS10")
    if not len(s):
        return "no data"
    chg, limit = _chg(s, 63), x.cfg["rates_shock"]
    shock = chg > limit
    return Reading(f"{s.iloc[-1]:.2f}%", OFF if shock else NEUTRAL,
                   f"{chg:+.2f} over 3m" + (": a fast rise tightens conditions" if shock
                                            else f"; risk-off if it rises > {limit} pts in 3m"), _last(s),
                   gz.make(gz.rising_risk(limit * 0.4, limit, ("steady", "rising", "fast rise", "rate shock")), chg))


def _dollar(x: Inputs) -> Reading | str:
    s = x.series("DTWEXBGS")
    if len(s) <= 63:
        return SHORT if len(s) else "no data"
    chg = _ret(s, 63)
    return Reading(f"{chg:+.1%} over 3m", OFF if chg > 0.03 else ON if chg < -0.03 else NEUTRAL,
                   "A sharply rising USD tends to tighten global conditions", _last(s),
                   gz.make(gz.band(0.03, -0.03, ("rising fast", "stable", "falling")), chg))


def _copper_gold(x: Inputs) -> Reading | str:
    copper, gold = x.yahoo("Copper"), x.yahoo("Gold")
    if copper is None or gold is None:
        return "no data"
    r = (copper / gold).dropna()
    chg, band = _ret(r, 63), x.cfg["copper_gold_band"]
    if pd.isna(chg):
        return SHORT
    return Reading(f"{chg:+.1%} over 3m", ON if chg > band else OFF if chg < -band else NEUTRAL,
                   "Rising = growth over defence", _last(r),
                   gz.make(gz.band(-band, band, ("defensive", "neutral", "growth")), chg))


def _oil(x: Inputs) -> Reading | str:
    o = x.yahoo("Oil (WTI)")
    if o is None:
        return "no data"
    chg, limit = _ret(o, 63), x.cfg["oil_shock"]
    if pd.isna(chg):
        return SHORT
    shock = chg > limit
    return Reading(f"{chg:+.1%} over 3m", OFF if shock else NEUTRAL,
                   "Oil shock: inflation and margin risk" if shock else f"Risk-off above +{limit:.0%} in 3m", _last(o),
                   gz.make(gz.rising_risk(limit / 2, limit, ("calm", "rising", "fast rise", "oil shock")), chg))


def _cli(x: Inputs) -> Reading | str:
    if x.cli is None or x.cli.empty:
        return "no data"
    lead = x.cli.iloc[0]  # the first configured area (G20) carries the vote
    st = ON if lead["phase"] == "Expansion" else OFF if lead["phase"] == "Contraction" else NEUTRAL
    others = "; ".join(f"{r.label} {r.phase.lower()}" for r in x.cli.iloc[1:].itertuples())
    return Reading(f"{lead['cli']:.1f} ({lead['chg_3m']:+.2f} 3m)", st,
                   f"{lead['phase']} as of {lead['asof']:%b %Y}. {others}", lead["asof"],
                   gz.gauge("cli_chg", lead["chg_3m"]), name=f"Leading indicators (OECD CLI, {lead['label']})")


def _revisions(x: Inputs) -> Reading | str:
    fs = x.factset
    if not (fs and pd.notna(fs.get("growth_now")) and pd.notna(fs.get("growth_start"))):  # NaN from parquet
        return "the latest FactSet report's growth figures could not be read" if fs else "no data"
    rev, band = fs["growth_now"] - fs["growth_start"], x.cfg["revisions_band"]
    guid = (f"; guidance +{fs['guidance_pos']:.0f} / -{fs['guidance_neg']:.0f}"
            if fs.get("guidance_pos") is not None and fs.get("guidance_neg") is not None else "")
    quarter = fs.get("quarter") if pd.notna(fs.get("quarter")) else "current qtr"
    return Reading(f"{rev:+.1f} pts", ON if rev > band else OFF if rev < -band else NEUTRAL,
                   f"Growth est. {fs['growth_now']:.1f}% vs {fs['growth_start']:.1f}% at quarter start"
                   f"{guid} (FactSet {fs['report_date']:%d %b})", fs["report_date"],
                   gz.make(gz.band(-band, band, ("cut", "stable", "raised")), rev),
                   name=f"Earnings revisions (S&P 500, {quarter})")


def _cape(x: Inputs) -> Reading | str:
    c = (x.market_val or {}).get("cape")
    if not (c and c.get("pct_all") is not None):
        return "no data"
    pct, rich, cheap = c["pct_all"], x.cfg["cape_rich_pct"], x.cfg["cape_cheap_pct"]
    return Reading(f"{c['value']:.1f}", OFF if pct >= rich else ON if pct <= cheap else NEUTRAL,
                   f"{pct:.0f}th percentile since {c['since'][:4]} ({c['pct_1990']:.0f}th since 1990), median "
                   f"{c['median']:.1f}; risk-off at or above the {rich}th", c["asof"], gz.gauge("cape_pct", pct))


def _erp(x: Inputs) -> Reading | str:
    e = (x.market_val or {}).get("erp")
    if not (e and e.get("pct") is not None):
        return "no data"
    pct, low, high = e["pct"], x.cfg["erp_low_pct"], x.cfg["erp_high_pct"]
    return Reading(f"{e['value']:.2%}", OFF if pct <= low else ON if pct >= high else NEUTRAL,
                   f"{pct:.0f}th percentile since {e['since'][:4]}, median {e['median']:.2%}; "
                   f"risk-off at or below the {low}th", e["asof"], gz.gauge("erp_pct", pct))


TREND = IndicatorSpec("Global trend (ACWI)", _trend)
# The rows after the breadth rows, in the order the page shows them.
SPECS = [
    IndicatorSpec("New highs – new lows (all stocks)", _highs_lows),
    IndicatorSpec("Equal vs cap weight (RSP/SPY)", _equal_weight),
    # the momentum factor itself: shown for context, never in the vote
    IndicatorSpec("Momentum payoff (top − bottom quintile)", _momentum_payoff, group=CONTEXT),
    IndicatorSpec("Return dispersion (3m, all stocks)", _dispersion, group=CONTEXT),
    IndicatorSpec("Momentum-crash setup (ACWI)", _crash_setup, group=CONTEXT),
    IndicatorSpec("Volatility (VIX)", _vix),
    IndicatorSpec("VIX term structure (VIX/VIX3M)", _vix_term),
    IndicatorSpec("Credit (US HY spread)", _spread_vs_avg("BAMLH0A0HYM2"), "fred"),
    IndicatorSpec("Euro credit (HY spread)", _spread_vs_avg("BAMLHE00EHYIOAS"), "fred", "credit_eu"),
    IndicatorSpec("Yield curve (10Y-2Y)", _curve, "fred"),
    IndicatorSpec("US 10Y yield", _us10y, "fred"),
    IndicatorSpec("US dollar (broad)", _dollar, "fred"),
    IndicatorSpec("Copper/gold ratio", _copper_gold),
    IndicatorSpec("Oil (WTI)", _oil),
    IndicatorSpec("Leading indicators (OECD CLI)", _cli, "oecd"),
    IndicatorSpec("Earnings revisions (S&P 500)", _revisions, "factset"),
    IndicatorSpec("Valuation (Shiller CAPE, US)", _cape, "cape", "valuation"),
    IndicatorSpec("Equity risk premium (Damodaran, S&P 500)", _erp, "erp", "valuation"),
]


def _row(spec: IndicatorSpec, x: Inputs) -> dict:
    r = spec.read(x)
    if isinstance(r, str):
        return _na(spec.name, spec.source, r, spec.group)
    return _ind(r.name or spec.name, r.value, r.status, r.note, spec.source, r.asof, r.gauge, spec.group)


def indicators(closes: pd.DataFrame, fred: pd.DataFrame, bench: str, groups: dict, labels: dict,
               macro: dict[str, str], cfg: dict, cli: pd.DataFrame | None = None,
               factset: dict | None = None, market_val: dict | None = None) -> tuple[list[dict], dict[str, pd.Series]]:
    """The regime rows (the arguments: see `Inputs`): the trend, one breadth row per group, then `SPECS`. An
    indicator whose input is missing stays as an "n/a" row, so the page shows what the reading is not based on."""
    x = Inputs(closes, fred, bench, sorted({t for ts in groups.values() for t in ts}), cfg, macro, cli, factset,
               market_val)
    out, breadth = [_row(TREND, x)], {}
    for key, tickers in groups.items():
        row, h = _breadth(x, labels[key], tickers)
        out.append(row)
        if not h.empty:
            breadth[labels[key]] = h
    out += [_row(s, x) for s in SPECS]
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

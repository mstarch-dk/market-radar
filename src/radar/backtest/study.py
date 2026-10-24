"""How well the momentum score (with `signal=`, the kvalitets- and værdiscore) ranked stocks at every past month-end,
judged on the returns that followed: the evidence for the score and a fair test of variants that might improve it
(`radar study score` writes reports/score-study.json). The exit rule's variants are backtest/exit_rules.py,
redeploying the exit money backtest/redeploy.py.

The method: guide/laerebog/test-af-scoren.md; the data rules: docs/data-conventions.md, *Point-in-time backtests*."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from .. import performance, simulate, tracked
from ..config import typed
from ..model import artifacts
from ..model.panels import Panels, fill_session, formation_dates, panels, score_at, within
from ..model.stats import (
    QUANTILES,
    cross_section,
    holdout_diff_t,
    nw_t,
    split_holdout,
    summarize,
    turnover,
    variant_verdict,
)
from ..model.stats import mean as _mean
from ..signals.score import COMPONENTS
from ..signals.score import mean_pct as pct

if TYPE_CHECKING:
    from ..market import Market

HORIZONS = {1: 21, 3: 63, 6: 126, 12: 252}      # months -> sessions
GROUP_MIN = 10                                   # names a stock group needs on a date for its own IC
SECTOR_MIN = 5                                   # names a sector needs for the sector-neutral variant
REPORT_FILE = "score-study.json"
BASELINE = "score"


# ---------------- the variants: higher = stronger, from data up to D ----------------

_within = within


def _row(p: Panels, col: str, day) -> pd.Series:
    return p.m[col].loc[day]


def _comp(p: Panels, day) -> pd.DataFrame:
    return pd.DataFrame({c: _row(p, c, day) for c in COMPONENTS})


_score = score_at


def _score_trend(p, day):
    s, ok = _score(p, day), _row(p, "trend_ok", day)
    return s.where(ok.eq(True), s - 100).where(ok.notna())


def _score_vol(p, day):
    v = p.vol.loc[day].where(lambda x: x > 0)
    return pct(_comp(p, day).div(v, axis=0))


def _at(df: pd.DataFrame, day, back: int) -> pd.Series:
    """Row `back` sessions before D on the frame's own calendar (NaN when the history is shorter)."""
    i = int(df.index.searchsorted(day, side="right")) - 1
    return df.iloc[i - back] if i >= back else pd.Series(np.nan, index=df.columns)


def _score_skip(p, day):
    """The score with the latest month skipped in all three components: 12-1, 6-1 and 3-1 months."""
    c = p.closes
    m1 = _at(c, day, 21)
    return pct(pd.DataFrame({"r12_1": _row(p, "r12_1", day), "r6_1": m1 / _at(c, day, 126) - 1,
                             "r3_1": m1 / _at(c, day, 63) - 1}))


BETA_WEEKS, BETA_MIN_WEEKS = 104, 52


def _resid(p, day):
    """Residual momentum (after Blitz, Huij & Martens 2011), on one market factor: each stock's beta to ACWI from
    weekly DKK returns over up to two years to D; its eleven monthly returns of the 12-1 window less beta × ACWI's,
    summed and divided by their standard deviation. Beta-adjusted rather than alpha-removed: with only a year or
    two of history an intercept would absorb most of the window being measured."""
    c = p.dkk.loc[:day]
    b = p.bench_dkk.reindex(c.index).ffill()
    wc = c.resample("W-FRI").last().pct_change(fill_method=None).iloc[-BETA_WEEKS:]
    wb = b.resample("W-FRI").last().pct_change(fill_method=None).iloc[-BETA_WEEKS:]
    ok = wc.notna() & wb.notna().to_numpy()[:, None]
    n = ok.sum()
    B = pd.DataFrame(np.repeat(wb.to_numpy()[:, None], wc.shape[1], 1), index=wc.index, columns=wc.columns).where(ok)
    C = wc.where(ok)
    cov = ((B - B.mean()) * (C - C.mean())).sum() / (n - 1)
    beta = (cov / B.var()).where(n >= BETA_MIN_WEEKS)
    pts = [(_at(c, day, k), b.iloc[len(b) - 1 - k] if len(b) > k else np.nan) for k in range(252, 20, -21)]
    e = pd.DataFrame({i: (s1 / s0 - 1) - beta * (b1 / b0 - 1)
                      for i, ((s0, b0), (s1, b1)) in enumerate(zip(pts, pts[1:]))})
    sd = e.std(axis=1).where(lambda x: x > 0)
    return (e.sum(axis=1, skipna=False) / sd).where(_row(p, "r12_1", day).notna())


def _fip(p, day):
    """Frog in the pan (Da, Gurun & Warachka 2014): −sign(12-1 return) × (share of down days − share of up days)
    over the 12-1 window, so a return made of many small moves ranks above the same return made in a few jumps.
    Sessions without a move (holidays, forward-filled gaps) count as neither."""
    i = int(p.closes.index.searchsorted(day, side="right"))       # one past D
    if i < 253:
        return pd.Series(np.nan, index=p.closes.columns)
    d = p.closes.iloc[i - 253:i - 21].pct_change(fill_method=None).iloc[1:]     # closes D-252 .. D-21
    n = d.notna().sum().where(lambda x: x > 0)
    info = np.sign(_row(p, "r12_1", day)) * ((d < 0).sum() / n - (d > 0).sum() / n)
    return -info


def _score_fip(p, day):
    """Score blended 2:1 with frog in the pan (both as percentiles)."""
    return (2 * _score(p, day) + pct(_fip(p, day).to_frame("fip"))) / 3


def _vol_surge(p, day):
    """20-session mean volume over the 120-session mean (the Momentum page's column), as of D."""
    if p.volumes is None:
        return pd.Series(np.nan, index=p.closes.columns)
    v = p.volumes.reindex(columns=p.closes.columns).loc[:day]
    if len(v) < 120:
        return pd.Series(np.nan, index=p.closes.columns)
    return v.iloc[-20:].mean() / v.iloc[-120:].mean().where(lambda x: x > 0)


@dataclass(frozen=True)
class Variant:
    key: str
    label: str
    fn: Callable
    pit: bool = True
    note: str = ""


VARIANTS = [
    Variant("score", "Momentum score (pooled, as on My holdings)", _score,
            note="mean percentile of 12-1, 6- and 3-month returns against every stock"),
    Variant("score_region", "Score ranked within each region (as on the Momentum page)",
            lambda p, d: _within(p.group, _comp(p, d))),
    Variant("r12_1", "12-1-month return alone", lambda p, d: _row(p, "r12_1", d)),
    Variant("r6m", "6-month return alone", lambda p, d: _row(p, "r6m", d)),
    Variant("r3m", "3-month return alone", lambda p, d: _row(p, "r3m", d)),
    Variant("r1m", "1-month return alone", lambda p, d: _row(p, "r1m", d),
            note="short-term reversal check: a negative IC means last month's winners tend to give back"),
    Variant("score_trend", "Score, uptrend first", _score_trend,
            note="names above a rising 200-day average rank ahead of the rest, by score within each half"),
    Variant("score_vol", "Volatility-adjusted score", _score_vol,
            note="each return divided by its 63-session volatility before ranking"),
    Variant("from_high", "Nearness to the 52-week high", lambda p, d: _row(p, "from_high", d)),
    Variant("score_sector", "Score ranked within each sector", lambda p, d: _within(p.sector.replace("", np.nan), _comp(p, d), SECTOR_MIN),
            pit=False, note="uses today's sectors (not known as of D)"),
    Variant("score_skip", "Score with the latest month skipped in every component", _score_skip,
            note="12-1, 6-1 and 3-1 months: keeps last month's short-term reversal out of the 6- and 3-month parts"),
    Variant("resid", "Residual momentum (beta to ACWI removed)", _resid,
            note="12-1-month return less beta × ACWI's, month by month in DKK, divided by its own volatility"),
    Variant("fip", "Frog in the pan (smooth path)", _fip,
            note="the share of up days minus down days in the 12-1 window, signed by its return"),
    Variant("score_fip", "Score blended 2:1 with frog in the pan", _score_fip),
    Variant("vol_surge", "Volume surge (20 vs 120 sessions) alone", _vol_surge,
            note="the Momentum page's column; a negative IC means high recent volume precedes weaker returns"),
]
BY_KEY = {v.key: v for v in VARIANTS}


# ---------------- the fundamentals signals (backtest/fund.py) ----------------

def _f(key: str):
    return lambda p, d: p.fund.col(d, key)


def _mom_on(p, day) -> pd.Series:
    """The momentum score ranked among the names with a K+V that day (so the two compare on the same names)."""
    names = p.fund.col(day, "qv").dropna().index
    return pct(_comp(p, day).reindex(names))


def _magic(p, day):
    t = p.fund.table(day)
    return pct(t[["rank_roic", "rank_ebit_ev"]]) if {"rank_roic", "rank_ebit_ev"} <= set(t) else pd.Series(dtype=float)


def _qvm(p, day):
    return (p.fund.col(day, "qv") + _mom_on(p, day)) / 2


FUND_VARIANTS = [
    Variant("qv", "K+V (kvalitet + værdi), as on the Quality & value page", _f("qv")),
    Variant("quality", "Kvalitetsscore", _f("quality")),
    Variant("value", "Værdiscore", _f("value")),
    Variant("q_profitability", "Pillar: profitability (FCF margin, ROIC)", _f("q_profitability")),
    Variant("q_durability", "Pillar: durability (margin and revenue steadiness)", _f("q_durability")),
    Variant("q_balance", "Pillar: balance sheet (net debt / EBITDA, interest cover)", _f("q_balance")),
    Variant("q_record", "Pillar: dividend record", _f("q_record")),
    Variant("roic", "ROIC alone", _f("rank_roic")),
    Variant("fcf_margin", "FCF margin alone", _f("rank_fcf_margin")),
    Variant("gross_prof", "Gross profitability (Novy-Marx)", _f("gross_prof"),
            note="gross profit over total assets, the last twelve months"),
    Variant("fcf_yield", "FCF yield alone", _f("rank_fcf_yield")),
    Variant("ebit_ev", "EBIT / EV alone", _f("rank_ebit_ev")),
    Variant("magic", "Magic formula (Greenblatt)", _magic, note="mean percentile of ROIC and EBIT / EV"),
    Variant("shareholder_yield", "Shareholder yield alone", _f("rank_shareholder_yield")),
    Variant("ey_vs_history", "EBIT / EV against its own history", _f("rank_ey_vs_history")),
    Variant("qvm", "K+V blended 1:1 with momentum", _qvm, note="the mean of K+V and the momentum score on the same names"),
    Variant("momentum", "Momentum score on the same names", _mom_on,
            note="for reference: the production score ranked among the names with a K+V"),
]

FUND_CAVEATS = [
    "US only: SEC EDGAR is the one source with filing dates, so other regions have no point-in-time statements. "
    "Peers are the US names, where the app pools every region.",
    "Survivorship: the universe is today's S&P 500, so companies that left it (often after a bad run, sometimes "
    "after a takeover) are missing.",
    "Sectors and industries are today's: the peer groups and the bank/insurer set aren't strictly as of D.",
    "Facts count from their filing date plus backtest.fundamentals_lag_days; a restatement filed later doesn't "
    "change an earlier date. Yahoo's market-value check is skipped (its figure is today's).",
    "Monthly dates over a short price history (history_years, at most backtest.max_years), and statements "
    "move slowly, so neighbouring months share most of their information. The t-statistics use Newey-West errors "
    "for overlapping horizons, but the number of independent periods is small.",
    "Several variants are tried: a few will look better by chance. Only one that also holds in the holdout counts.",
    "The forward A/B test (radar abtest) is the clean out-of-sample test; this study is the look back.",
]


@dataclass(frozen=True)
class Signal:
    key: str
    label: str
    baseline: str
    variants: tuple
    report: str
    caveats: tuple
    fund: bool = False

    @property
    def by_key(self) -> dict:
        return {v.key: v for v in self.variants}


SIGNALS = {
    "momentum": Signal("momentum", "Momentum score", BASELINE, tuple(VARIANTS), REPORT_FILE, ()),
    **{k: Signal(k, lbl, k, tuple(FUND_VARIANTS), f"score-study-{k}.json", tuple(FUND_CAVEATS), fund=True)
       for k, lbl in (("quality", "Kvalitetsscore"), ("value", "Værdiscore"), ("qv", "K+V"))},
}


# ---------------- statistics ----------------

# ---------------- the study ----------------

def forward(p: Panels, fi: int, h: int, dkk: bool = False) -> pd.Series | None:
    """Forward returns from session `fi` over `h` sessions (None when that end is beyond the data)."""
    if fi + h >= len(p.sessions):
        return None
    f, e = p.sessions[fi], p.sessions[fi + h]
    c = p.dkk if dkk else p.closes
    return c.loc[e] / c.loc[f] - 1


def run(market: Market, horizons=(1, 3, 6, 12), variants: list[str] | None = None, n_top: int = 15, exits: int | None = None,
        seasoned: bool = False, since=None, with_regime: bool = True, log=lambda *_: None, p: Panels | None = None,
        signal: str = "momentum") -> dict:
    """The study at every month-end D on the benchmark calendar: each variant from prices up to D only
    (momentum.metrics_panel, row D, as pit.py), judged on the adjusted return from the fill session over H sessions in
    the listing's currency, as excess over the equal-weight universe on D (the top N also in DKK against ACWI). A name
    without a forward return is left out and counted, never 0. Across dates: means with Newey-West t (lag H−1 months),
    the splits and each variant's verdict against the baseline. A fundamental signal (`signal=`) scores the facts
    known by D with backtest/fund.py and writes score-study-<signal>.json; `exits=H` adds exit_study."""
    if signal not in SIGNALS:
        raise ValueError(f"unknown signal {signal} (known: {', '.join(SIGNALS)})")
    sig = SIGNALS[signal]
    BY_KEY, BASELINE = sig.by_key, sig.baseline       # the module's momentum names, here per signal
    if sig.fund and exits:
        raise ValueError("the exit-rule test runs on the momentum score only")
    bt = typed().backtest
    min_names = bt.study_min_names
    fill = bt.fill
    holdout = pd.Timestamp(bt.study_holdout_from)
    keys = variants or [v.key for v in sig.variants]
    unknown = [k for k in keys if k not in BY_KEY]
    if unknown:
        raise ValueError(f"unknown variant(s): {', '.join(unknown)} (known: {', '.join(BY_KEY)})")
    if BASELINE not in keys:
        keys = [BASELINE, *keys]
    for h in horizons:
        if h not in HORIZONS:
            raise ValueError(f"horizons are months among {', '.join(map(str, HORIZONS))}")
    p = p or panels(market)
    if sig.fund and p.fund is None:
        from .fund import FundPIT

        p.fund = FundPIT(market)
        if not p.fund.names:
            raise ValueError("no SEC EDGAR statements stored: run `radar fundamentals update --source edgar --all` first")
        log(f"{len(p.fund.names)} US stocks with SEC EDGAR statements, the first known {p.fund.first_known:%Y-%m-%d}")
        since = max(pd.Timestamp(since), p.fund.first_known) if since else p.fund.first_known
    log(f"{len(p.closes.columns)} stocks, {len(keys)} variants")
    ctx = None
    if with_regime or exits:
        from .pit import Context

        ctx = Context.build(market, set())
    per: dict[int, dict[str, list[dict]]] = {h: {k: [] for k in keys} for h in horizons}
    groups_res: dict[int, dict[str, dict[str, list[dict]]]] = {h: {k: {} for k in keys} for h in horizons}
    tops: dict[str, list] = {k: [] for k in keys}
    dates_out = []
    for day in formation_dates(p.sessions, since):
        fi = fill_session(p.sessions, day, fill)
        if fi is None:
            continue
        last = p.m["last"].loc[day]
        listed = last.notna()
        if seasoned:
            listed &= p.m["history"].loc[day] >= 252
        xs = {k: BY_KEY[k].fn(p, day).reindex(listed.index).where(listed) for k in keys}
        base = xs[BASELINE]
        if base.notna().sum() < min_names:
            continue
        rg = ctx.regime(day)["label"] if ctx is not None and with_regime else None
        rec = {"date": day.date().isoformat(), "fill": p.sessions[fi].date().isoformat(), "regime": rg,
               "ranked": int(base.notna().sum()), "no_price": int((~last.notna()).sum()),
               "no_score": int((last.notna() & base.isna()).sum()), "horizons": {}}
        if sig.fund:
            mom = _mom_on(p, day).reindex(base.index)
            rc = base.rank().corr(mom.rank())
            rec["momentum_corr"] = None if pd.isna(rc) else float(rc)
        for k in keys:
            x = xs[k].dropna()
            tops[k].append(set(x.sort_values(ascending=False).index[: max(len(x) // QUANTILES, 1)]))
        for h in horizons:
            y = forward(p, fi, HORIZONS[h])
            if y is None:
                continue
            yd = forward(p, fi, HORIZONS[h], dkk=True)
            f, e = p.sessions[fi], p.sessions[fi + HORIZONS[h]]
            b = p.bench_dkk
            acwi = float(b.asof(e) / b.asof(f) - 1) if len(b) else None
            hrec: dict[str, Any] = {"fwd_missing": int((base.notna() & y.isna()).sum()), "acwi_dkk": acwi, "ic": {}}
            for k in keys:
                cs = cross_section(xs[k], y, n_top, min_names, yd)
                if cs is None:
                    continue
                cs |= {"date": day, "regime": rg, "acwi_dkk": acwi}
                if k == BASELINE:
                    hrec["top"] = cs["top"]
                    hrec["top_dkk"] = cs.get("top_dkk")
                per[h][k].append(cs)
                hrec["ic"][k] = cs["ic"]
                for g in p.group.dropna().unique():
                    members = p.group.index[p.group == g]
                    gc = cross_section(xs[k].reindex(members), y.reindex(members), min(n_top, 5), GROUP_MIN)
                    if gc is not None:
                        groups_res[h][k].setdefault(g, []).append(gc)
            rec["horizons"][str(h)] = hrec
        dates_out.append(rec)
    if not dates_out:
        raise ValueError(f"no formation date with {min_names} ranked names: not enough price history yet")
    log(f"{len(dates_out)} formation dates, {dates_out[0]['date']} to {dates_out[-1]['date']}")

    results: dict[str, dict] = {}
    verdicts: dict[str, dict] = {}
    decay: dict[str, dict] = {k: {} for k in keys}
    for h in horizons:
        lag = max(h - 1, 0)
        results[str(h)] = {}
        for k in keys:
            rows = per[h][k]
            res = {**{p: summarize(xs, lag) for p, xs in split_holdout(rows, holdout).items()},
                   "by_year": {str(y): summarize([r for r in rows if r["date"].year == y], lag)
                               for y in sorted({r["date"].year for r in rows})},
                   "by_regime": {str(g): summarize([r for r in rows if r["regime"] == g], lag)
                                 for g in sorted({r["regime"] for r in rows}, key=str)},
                   "by_group": {g: summarize(v, lag) for g, v in groups_res[h][k].items()}}
            results[str(h)][k] = res
            decay[k][str(h)] = (res["all"] or {}).get("ic_mean")
        base = results[str(h)][BASELINE]
        verdicts[str(h)] = {
            k: variant_verdict(results[str(h)][k], base, holdout_diff_t(per[h][k], per[h][BASELINE], holdout, lag))
            for k in keys if k != BASELINE}

    out = {
        "signal": sig.key, "signal_label": sig.label,
        "generated": pd.Timestamp.now().isoformat(timespec="seconds"), "asof": p.sessions[-1].date().isoformat(),
        "settings": {"n_top": n_top, "min_names": min_names, "fill": fill, "seasoned": seasoned,
                     "holdout_from": holdout.date().isoformat() if holdout is not None else None,
                     "horizons": {str(h): HORIZONS[h] for h in horizons}, "fee_bps": bt.fee_bps},
        "universe": {"tickers": int(len(p.closes.columns)),
                     "groups": {g: int((p.group == g).sum()) for g in p.group.dropna().unique()},
                     "first": dates_out[0]["date"], "last": dates_out[-1]["date"]},
        "variants": [{"key": k, "label": BY_KEY[k].label, "pit": BY_KEY[k].pit, "note": BY_KEY[k].note,
                      "baseline": k == BASELINE} for k in keys],
        "variants_tried": len(keys) - 1,
        "results": results, "verdicts": verdicts, "decay": decay,
        "turnover": {k: turnover(tops[k]) for k in keys},
        "dates": dates_out,
        "exits": exit_study(market, p, ctx, dates_out, exits, n_top, log) if exits else None,
        "caveats": list(sig.caveats) if sig.fund else CAVEATS,
    }
    if sig.fund:
        mc = [d.get("momentum_corr") for d in dates_out]
        assert p.fund is not None                 # loaded above
        out["universe"]["fund_names"] = len(p.fund.names)
        out["momentum_corr"] = {"mean": _mean(mc), "dates": sum(v is not None for v in mc),
                                "note": "rank correlation of the baseline with the momentum score per date: near 0 "
                                        "or below means the two pick different stocks"}
    return out


CAVEATS = [
    "Survivorship: the universe is today's (S&P 500 constituents from SPY and the curated lists). Names that left "
    "it are missing, and stocks that joined after strong runs are in it, which flatters momentum most.",
    "Sectors are today's, so the sector-neutral variant isn't strictly as of D.",
    "Adjusted prices are rewritten after each dividend or split; that moves price levels, barely returns.",
    "Monthly dates with horizons longer than a month overlap: the t-statistics use Newey-West errors for that, "
    "but the number of independent periods is still small (about one per horizon).",
    "Several variants are tried: a few will look better by chance. Only an improvement that holds in the holdout "
    "too counts, and even then it is a candidate for a decision, not a change.",
    "Costs and taxes: the basket returns are before tax; the exit-rule comparison charges backtest.fee_bps per "
    "trade, and realised gains would be taxed differently in frie midler and an aktiesparekonto.",
]


# ---------------- the exit rule across dates ----------------

def exit_study(market: Market, p: Panels, ctx, dates: list[dict], months: int, n_top: int, log) -> dict:
    """Each date's top-N basket (production score, equal weights) held for `months` against the same buys with the
    rule (both halves, stop only, take-profit only), in DKK, fees included."""
    from . import exits as ex

    if months not in HORIZONS:
        raise ValueError(f"the exit study horizon must be one of {', '.join(map(str, HORIZONS))} months")
    h = HORIZONS[months]
    bt = typed().backtest
    fee = bt.fee_bps
    park = bt.park or tracked.benchmark()
    capital = 100_000.0
    baskets = []
    for d in dates:
        day = pd.Timestamp(d["date"])
        fi = int(p.sessions.searchsorted(pd.Timestamp(d["fill"])))
        if fi + h >= len(p.sessions):
            continue
        baskets.append((d["date"], fi, top_names(p, day, n_top)))
    if not baskets:
        return {"months": months, "dates": [], "summary": None, "note": "no date with a complete horizon"}
    held = {t for _, _, b in baskets for t in b} | {park}
    from .pit import Context

    ctx = fast(Context.build(market, held), p)
    rows_out = []
    missing: dict[str, int] = {}
    rule_days = 0
    for i, (ds, fi, tickers) in enumerate(baskets):
        f, e = p.sessions[fi], p.sessions[fi + h]
        rows, problems = simulate.basket_rows(market, {t: 1 / len(tickers) for t in tickers}, f, capital, fee)
        if not rows:
            continue
        rec = {"date": ds, "fill": f.date().isoformat(), "end": e.date().isoformat(), "skipped": problems}
        rec["hold"] = performance.return_on_paid_in(rows, market, e)
        for rule in ex.RULES:
            rep = ex.replay(rows, ctx, "rules", end=e, spec=ex.ablation(rule), fee_bps=fee)
            rec[rule] = performance.return_on_paid_in(rep["rows"], market, e)
            rec[f"{rule}_exits"] = len(rep["exits"])
            if rule == "both":
                c = rep["counts"]
                rule_days += c["rule_days"]
                for k, n in c["missing"].items():
                    missing[k] = missing.get(k, 0) + n
        b = performance.bench_dkk(market)
        rec["acwi"] = float(b.asof(e) / b.asof(f) - 1)
        rows_out.append(rec)
        if (i + 1) % 12 == 0:
            log(f"exit rule: {i + 1} of {len(baskets)} dates")
    lag = max(months - 1, 0)
    summ = {}
    for rule in ex.RULES:
        diff = [r[rule] - r["hold"] for r in rows_out if r.get(rule) is not None and r.get("hold") is not None]
        summ[rule] = {"dates": len(diff), "mean_diff": _mean(diff), "t": nw_t(diff, lag),
                      "helped": _mean([float(x > 0) for x in diff]), "worst": min(diff) if diff else None,
                      "best": max(diff) if diff else None,
                      "exits_mean": _mean([r[f"{rule}_exits"] for r in rows_out])}
    summ["hold"] = {"mean": _mean([r["hold"] for r in rows_out]),
                    "beats_acwi": _mean([float(r["hold"] > r["acwi"]) for r in rows_out if r.get("hold") is not None]),
                    "acwi_mean": _mean([r["acwi"] for r in rows_out])}
    return {"months": months, "n_top": n_top, "fee_bps": fee, "park": park, "dates": rows_out, "summary": summ,
            "inputs_missing": {k: n / rule_days for k, n in missing.items()} if rule_days else {},
            "note": "the rule as it would have been set then: inputs that didn't exist yet (analyst data before "
                    "fetching began) move nothing, so for early dates it isn't quite today's rule"}


def top_names(p: Panels, day: pd.Timestamp, n: int) -> list[str]:
    """The `n` best by score on `day` among names with a price and a DKK rate (so they can be bought)."""
    ok = p.m["last"].loc[day].notna() & p.dkk.loc[day].notna()
    x = _score(p, day).where(ok).dropna()
    return list(x.sort_values(ascending=False, kind="stable").index[:n])


def fast(ctx, p: Panels):
    """The same answers, faster: the score for every stock at once per day (as Context.score, one name at a time),
    and each (stops variant, name, day, anchor)'s levels computed once, however many replays ask."""
    day_scores: dict = {}

    def score(t, d):
        if d not in day_scores:
            day_scores[d] = _score(p, d).round(1)
        v = day_scores[d].get(t)
        return None if v is None or pd.isna(v) else float(v)
    levels_at, cached = ctx.levels, {}

    def levels(t, d, anchor, stops=None):
        k = (tuple(sorted(stops.items())) if stops else (), t, d, anchor)
        if k not in cached:
            cached[k] = levels_at(t, d, anchor, stops)
        return cached[k]
    ctx.score, ctx.levels = score, levels
    return ctx


def write(rep: dict) -> artifacts.ScoreStudy:
    out = artifacts.write("score-study", rep, data_asof=rep["asof"], file=SIGNALS[rep.get("signal", "momentum")].report)
    assert isinstance(out, artifacts.ScoreStudy)
    return out


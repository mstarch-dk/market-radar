"""Attribution of an active return vs a benchmark, as pure math: single-period Brinson–Fachler by segment, the
currency effect in DKK, and Carino's linking of single periods into a longer one; and the factor regression that
asks whether what's left looks like skill. Weights and returns in, effects out; no data is read here. The method:
plans/F4-attribution.md, 4.3 and 4.4; the textbook's chapter on attribution.

Conventions. Each side's weights sum to 1 (cash and unclassified value are segments of their own). A segment the
benchmark doesn't hold takes the benchmark's total return as its benchmark return unless the caller gives one: with
no benchmark weight there is no selection, so an unclassified segment's excess return shows as interaction, and cash
(given its own return, 0, as benchmark return) shows as allocation: the cash drag. A segment the portfolio doesn't
hold has no selection. A held segment without a return makes the period missing (None), never a 0 % return."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..values import num
from .stats import nw_lag, ols_nw, periods_to_t

EFFECTS = ("allocation", "selection", "interaction")
WEIGHT_TOL = 1e-9          # how far a side's weights may sum from 1 (float noise)
FACTORS = ("market", "SMB", "HML", "RMW", "CMA", "WML")   # French's developed five factors and momentum
WEEKS_PER_YEAR = 52


def _weights(w: pd.Series, what: str) -> pd.Series:
    w = w.astype(float)
    if not np.isfinite(w.to_numpy()).all():
        raise ValueError(f"{what} weights must be finite")
    if abs(float(w.sum()) - 1.0) > WEIGHT_TOL:
        raise ValueError(f"{what} weights sum to {float(w.sum()):.12f}, not 1")
    return w


def brinson_fachler(wp: pd.Series, wb: pd.Series, rp: pd.Series, rb: pd.Series) -> pd.DataFrame | None:
    """One period's Brinson–Fachler attribution by segment.

    wp, wb: portfolio and benchmark weights by segment (each sums to 1; a segment one side lacks weighs 0 there).
    rp, rb: the segments' returns in the portfolio and in the benchmark. A segment the benchmark doesn't hold gets the
    benchmark's total return R_b as rb unless one is given; a segment the portfolio doesn't hold gets rb as rp.

    allocation = (wp − wb)(rb − R_b), selection = wb (rp − rb), interaction = (wp − wb)(rp − rb); their sum over the
    segments is r_p − R_b with r_p = Σ wp·rp and R_b = Σ wb·rb. Returns one row per segment with wp, wb, rp, rb, the
    three effects and their total, or None when a segment with weight has no return."""
    keys = wp.index.union(wb.index)
    wp_ = _weights(wp.reindex(keys, fill_value=0.0), "portfolio")
    wb_ = _weights(wb.reindex(keys, fill_value=0.0), "benchmark")
    rb_ = rb.reindex(keys).astype(float)
    if rb_[wb_ > 0].isna().any():
        return None
    big_rb = float((wb_ * rb_.fillna(0.0)).sum())   # zero: only segments with no benchmark weight are filled
    rb_ = rb_.where(rb_.notna(), big_rb)
    rp_ = rp.reindex(keys).astype(float)
    if rp_[wp_ > 0].isna().any():
        return None
    rp_ = rp_.where(rp_.notna(), rb_)
    active_w = wp_ - wb_
    out = pd.DataFrame({"wp": wp_, "wb": wb_, "rp": rp_, "rb": rb_,
                        "allocation": active_w * (rb_ - big_rb), "selection": wb_ * (rp_ - rb_),
                        "interaction": active_w * (rp_ - rb_)})
    out["total"] = out[list(EFFECTS)].sum(axis=1)
    return out


def totals(frame: pd.DataFrame) -> dict[str, float]:
    """A Brinson frame's portfolio and benchmark returns and its effects summed over the segments."""
    rp = float((frame["wp"] * frame["rp"]).sum())
    rb = float((frame["wb"] * frame["rb"]).sum())
    return {"rp": rp, "rb": rb, "active": rp - rb, **{e: float(frame[e].sum()) for e in EFFECTS}}


def currency_effect(wp: pd.Series, wb: pd.Series, fx: pd.Series) -> pd.DataFrame | None:
    """One period's currency effect in DKK by currency: (wp_c − wb_c)(f_c − F_b), with f_c the currency's return
    against DKK and F_b = Σ wb_c·f_c. A currency's return is the same on both sides, so there is no selection.

    wp, wb: the value shares by currency (each sums to 1; value whose currency isn't known is passed under a key of
    its own with f = 0, so its whole return counts as local and the row shows its share). None when a currency with
    weight has no return. Summed, the effect is Σ wp_c·f_c − F_b."""
    keys = wp.index.union(wb.index)
    wp_ = _weights(wp.reindex(keys, fill_value=0.0), "portfolio currency")
    wb_ = _weights(wb.reindex(keys, fill_value=0.0), "benchmark currency")
    f = fx.reindex(keys).astype(float)
    if f[(wp_ > 0) | (wb_ > 0)].isna().any():
        return None
    f = f.fillna(0.0)   # zero: only currencies neither side holds, whose rows are 0 either way
    big_f = float((wb_ * f).sum())
    return pd.DataFrame({"wp": wp_, "wb": wb_, "fx": f, "effect": (wp_ - wb_) * (f - big_f)})


def split_dkk(r_dkk: float, fx: float) -> float:
    """The local return inside a DKK return: 1 + r_DKK = (1 + r_local)(1 + f)."""
    return (1 + r_dkk) / (1 + fx) - 1


def day_effects(rp_dkk: float, rb_dkk: float, local: pd.DataFrame, currency: pd.DataFrame) -> dict[str, float]:
    """One period's effects in DKK: the Brinson effects on local returns (`local`, from brinson_fachler), the
    currency effect (`currency`, from currency_effect) and the cross term, which is what's left of the DKK active
    return: Σ w·r_local·f on the portfolio side less the benchmark's. So the five add up to rp_dkk − rb_dkk exactly;
    the cross term is shown, never dropped."""
    t = totals(local)
    cur = float(currency["effect"].sum())
    active = rp_dkk - rb_dkk
    return {**{e: t[e] for e in EFFECTS}, "currency": cur, "cross": active - t["active"] - cur, "active": active,
            "rp": rp_dkk, "rb": rb_dkk}


def brinson_panel(wp: pd.DataFrame, wb: pd.DataFrame, rp: pd.DataFrame, rb: pd.DataFrame) -> dict:
    """`brinson_fachler` for many periods at once (rows: periods, columns: segments; the four frames on the same
    rows and columns). Weights where a side doesn't hold a segment are 0; returns where it doesn't are NaN and are
    filled as `brinson_fachler` fills them (the benchmark's total return; the segment's benchmark return). A period
    whose weights don't sum to 1 on either side, or where a held segment has no return, is invalid: its effects are
    NaN. Returns the three effect frames, each side's return per period (r_p, R_b) and `valid`."""
    wp_, wb_ = wp.astype(float), wb.astype(float)
    ok = ((wp_.sum(axis=1) - 1).abs() <= WEIGHT_TOL) & ((wb_.sum(axis=1) - 1).abs() <= WEIGHT_TOL)
    ok &= ~((wb_ > 0) & rb.isna()).any(axis=1) & ~((wp_ > 0) & rp.isna()).any(axis=1)
    big_rb = (wb_ * rb.fillna(0.0)).sum(axis=1)   # zero: only segments without benchmark weight are filled
    rb_ = rb.astype(float).apply(lambda c: c.fillna(big_rb))
    rp_ = rp.astype(float).fillna(rb_)
    active_w = wp_ - wb_
    out = {"allocation": active_w.mul(rb_.sub(big_rb, axis=0)), "selection": wb_ * (rp_ - rb_),
           "interaction": active_w * (rp_ - rb_)}
    out = {k: v.where(ok, axis=0) for k, v in out.items()}
    return out | {"rp": (wp_ * rp_).sum(axis=1).where(ok), "rb": big_rb.where(ok), "valid": ok}


def currency_panel(wp: pd.DataFrame, wb: pd.DataFrame, fx: pd.DataFrame) -> dict:
    """`currency_effect` for many periods at once (rows: periods, columns: currencies). A period whose weights don't
    sum to 1, or where a currency with weight has no return, is invalid (NaN). Returns the effect frame, F_b and
    `valid`."""
    wp_, wb_ = wp.astype(float), wb.astype(float)
    ok = ((wp_.sum(axis=1) - 1).abs() <= WEIGHT_TOL) & ((wb_.sum(axis=1) - 1).abs() <= WEIGHT_TOL)
    ok &= ~(((wp_ > 0) | (wb_ > 0)) & fx.isna()).any(axis=1)
    f = fx.astype(float).fillna(0.0)   # zero: only currencies neither side holds that day, whose effect is 0
    big_f = (wb_ * f).sum(axis=1)
    return {"effect": ((wp_ - wb_) * f.sub(big_f, axis=0)).where(ok, axis=0), "fb": big_f.where(ok), "valid": ok}


def carino_k(rp: float, rb: float) -> float:
    """Carino's factor for one period: (ln(1 + r_p) − ln(1 + r_b)) / (r_p − r_b), and its limit 1 / (1 + r) when the
    two returns are equal."""
    if abs(rp - rb) < 1e-12:
        return 1.0 / (1.0 + rp)
    return (math.log1p(rp) - math.log1p(rb)) / (rp - rb)


def carino_weights(rp: pd.Series, rb: pd.Series) -> pd.Series:
    """Each period's linking weight k_t / K, where K is Carino's factor of the compounded period: a period's effects
    times its weight, summed over the periods, add up to the compounded active return R_p − R_b exactly when each
    period's effects add up to its own r_p − r_b (Carino 1999)."""
    if len(rp) != len(rb) or not rp.index.equals(rb.index):
        raise ValueError("portfolio and benchmark returns must cover the same periods")
    if rp.isna().any() or rb.isna().any():
        raise ValueError("a period without a return can't be linked: leave it out first")
    big_rp = float(np.prod(1 + rp.to_numpy()) - 1)
    big_rb = float(np.prod(1 + rb.to_numpy()) - 1)
    big_k = carino_k(big_rp, big_rb)
    return pd.Series([carino_k(a, b) / big_k for a, b in zip(rp, rb, strict=True)], index=rp.index)


def link(effects: pd.DataFrame, weights: pd.Series) -> pd.Series:
    """Effects per period (rows) linked over the periods: Σ_t weight_t · effect_t, per column."""
    return effects.mul(weights.reindex(effects.index), axis=0).sum()


def linking_error(linked_total: float, rp: pd.Series, rb: pd.Series) -> float:
    """|Σ linked effects − (R_p − R_b)|: how far the linked effects miss the compounded active return."""
    big = float(np.prod(1 + rp.to_numpy()) - 1) - float(np.prod(1 + rb.to_numpy()) - 1)
    return abs(linked_total - big)


# ---------------- factor regression: skill or luck ----------------

def regression_frame(port: pd.Series, ff: pd.DataFrame, usd: pd.Series, rf: pd.Series) -> pd.DataFrame:
    """The weekly data for the factor regression, in DKK: y = the portfolio's return less the DKK risk-free rate;
    market = French's developed market in DKK, (1 + Mkt-RF + RF)(1 + USD/DKK) − 1, less the same rate; SMB, HML, RMW,
    CMA and WML as French gives them (long-short in USD, treated as currency-neutral: a self-financing position's
    currency exposure is second order). `port`, `usd` (USD/DKK's return) and `rf` (DKK risk-free) are weekly
    returns on the same W-FRI dates as `ff`. Only weeks where every input is known."""
    need = ["Mkt-RF", "RF", "SMB", "HML", "RMW", "CMA", "WML"]
    if missing := [c for c in need if c not in ff]:
        raise ValueError(f"the factor data lacks {', '.join(missing)}")
    df = pd.concat({"port": port, "usd": usd, "rf": rf}, axis=1, sort=True).join(ff[need], how="inner").dropna()
    out = pd.DataFrame({"y": df["port"] - df["rf"],
                        "market": (1 + df["Mkt-RF"] + df["RF"]) * (1 + df["usd"]) - 1 - df["rf"]}, index=df.index)
    for c in FACTORS[1:]:
        out[c] = df[c]
    return out


def factor_regression(frame: pd.DataFrame, min_weeks: int, lag: int | None = None) -> dict | None:
    """The portfolio's weekly excess return on the factors (a frame from `regression_frame`), with Newey-West t-stats
    (lag `lag`, else the Newey-West rule for this many weeks). Alpha comes with its t and n always, and with the weeks
    and months of data it would take to reach t = 2 at this alpha and noise (`periods_to_t`; 'reached' when |t| ≥ 2
    already). None under `min_weeks` weeks: too short to say anything."""
    n = len(frame)
    if n < min_weeks or n <= len(FACTORS) + 1:
        return None
    lag = nw_lag(n) if lag is None else lag
    fit = ols_nw(frame["y"].to_numpy(), frame[list(FACTORS)].to_numpy(), lag)
    t_alpha = num(fit["t"][0])
    weeks = periods_to_t(t_alpha, n) if t_alpha is not None else None
    reached = t_alpha is not None and abs(t_alpha) >= 2
    return {"n_weeks": n, "start": frame.index[0].date().isoformat(), "end": frame.index[-1].date().isoformat(),
            "nw_lag": lag, "r2": num(fit["r2"]),
            "alpha_ann": num(fit["coef"][0] * WEEKS_PER_YEAR), "alpha_t": t_alpha,
            "alpha_se_ann": num(fit["se"][0] * WEEKS_PER_YEAR), "reached": reached,
            "weeks_to_t2": None if reached or weeks is None else weeks,
            "months_to_t2": None if reached or weeks is None else weeks * 12 / WEEKS_PER_YEAR,
            "loadings": [{"factor": f, "beta": num(fit["coef"][i + 1]), "t": num(fit["t"][i + 1])}
                         for i, f in enumerate(FACTORS)]}

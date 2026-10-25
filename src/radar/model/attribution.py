"""Attribution of an active return vs a benchmark, as pure math: single-period Brinson–Fachler by segment, the
currency effect in DKK, and Carino's linking of single periods into a longer one. Weights and returns in, effects
out; no data is read here. The method: plans/F4-attribution.md, 4.3; the textbook's chapter on attribution.

Conventions. Each side's weights sum to 1 (cash and unclassified value are segments of their own). A segment the
benchmark doesn't hold takes the benchmark's total return as its benchmark return unless the caller gives one: with
no benchmark weight there is no selection, so an unclassified segment's excess return shows as interaction, and cash
(given its own return, 0, as benchmark return) shows as allocation: the cash drag. A segment the portfolio doesn't
hold has no selection. A held segment without a return makes the period missing (None), never a 0 % return."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

EFFECTS = ("allocation", "selection", "interaction")
WEIGHT_TOL = 1e-9          # how far a side's weights may sum from 1 (float noise)


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

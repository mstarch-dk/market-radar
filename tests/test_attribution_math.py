"""Attribution math (model/attribution.py) against hand calculations: Brinson–Fachler adds up to the active return,
a portfolio with the benchmark's weights has no allocation, the currency effect and the cross term close the DKK
identity, and Carino's linking reproduces the compounded active return."""
import numpy as np
import pandas as pd
import pytest

from radar.model import attribution as at


def S(**kw):
    return pd.Series(kw, dtype=float)


WP, WB = S(A=0.5, B=0.3, C=0.2), S(A=0.4, B=0.4, C=0.2)
RP, RB = S(A=0.10, B=0.02, C=-0.05), S(A=0.08, B=0.03, C=-0.02)


def test_brinson_fachler_hand_example_sums_to_the_active_return():
    f = at.brinson_fachler(WP, WB, RP, RB)
    # R_b = 0.040, r_p = 0.046: allocation 0.005, selection -0.002, interaction 0.003
    assert f["allocation"].tolist() == pytest.approx([0.004, 0.001, 0.0])
    assert f["selection"].tolist() == pytest.approx([0.008, -0.004, -0.006])
    assert f["interaction"].tolist() == pytest.approx([0.002, 0.001, 0.0])
    t = at.totals(f)
    assert t["rp"] == pytest.approx(0.046) and t["rb"] == pytest.approx(0.040)
    assert t["allocation"] + t["selection"] + t["interaction"] == pytest.approx(t["active"], abs=1e-15)


def test_benchmark_weights_give_zero_allocation():
    f = at.brinson_fachler(WB, WB, RP, RB)
    assert np.allclose(f["allocation"], 0.0) and np.allclose(f["interaction"], 0.0)
    assert f["selection"].sum() == pytest.approx(at.totals(f)["active"])


def test_cash_and_unclassified_segments():
    wp = S(A=0.5, B=0.3, cash=0.1, unclassified=0.1)
    rp = S(A=0.10, B=0.02, cash=0.0, unclassified=0.07)
    f = at.brinson_fachler(wp, S(A=0.5, B=0.5), rp, S(A=0.08, B=0.03, cash=0.0))
    big_rb = 0.5 * 0.08 + 0.5 * 0.03
    # cash, given its own return as benchmark return: the cash drag, all allocation
    assert f.loc["cash", "allocation"] == pytest.approx(0.1 * (0.0 - big_rb))
    assert f.loc["cash", "selection"] == 0.0 and f.loc["cash", "interaction"] == 0.0
    # unclassified: benchmark return := R_b, no benchmark weight, so its excess return is interaction
    assert f.loc["unclassified", "rb"] == pytest.approx(big_rb)
    assert f.loc["unclassified", "interaction"] == pytest.approx(0.1 * (0.07 - big_rb))
    assert f.loc["unclassified", "allocation"] == 0.0 and f.loc["unclassified", "selection"] == 0.0
    t = at.totals(f)
    assert f["total"].sum() == pytest.approx(t["active"], abs=1e-15)


def test_a_segment_the_portfolio_lacks_has_no_selection():
    f = at.brinson_fachler(S(A=1.0), S(A=0.6, B=0.4), S(A=0.05), S(A=0.04, B=0.01))
    assert f.loc["B", "selection"] == 0.0 and f.loc["B", "interaction"] == 0.0
    assert f["total"].sum() == pytest.approx(at.totals(f)["active"], abs=1e-15)


def test_a_held_segment_without_a_return_makes_the_period_missing():
    assert at.brinson_fachler(WP, WB, S(A=0.1, B=0.02), RB) is None                   # C held, no return
    assert at.brinson_fachler(WP, WB, RP, S(A=0.08, B=np.nan, C=0.0)) is None
    with pytest.raises(ValueError, match="sum to"):
        at.brinson_fachler(S(A=0.5), WB, RP, RB)


def test_currency_effect_and_cross_close_the_dkk_identity():
    # portfolio: X (USD) only; benchmark: Y (EUR) and Z (USD), half each; segments are the holdings
    local = at.brinson_fachler(S(X=1.0), S(Y=0.5, Z=0.5), S(X=0.02), S(Y=0.01, Z=0.03))
    fx = S(USD=0.01, EUR=0.005)
    cur = at.currency_effect(S(USD=1.0), S(EUR=0.5, USD=0.5), fx)
    assert cur["effect"].tolist() == pytest.approx([0.00125, 0.00125])                # EUR, USD; F_b = 0.0075
    rp_dkk = 1.02 * 1.01 - 1
    rb_dkk = 0.5 * (1.01 * 1.005 - 1) + 0.5 * (1.03 * 1.01 - 1)
    d = at.day_effects(rp_dkk, rb_dkk, local, cur)
    assert d["currency"] == pytest.approx(0.0025)
    # the cross term is Σ w·r_local·f, portfolio less benchmark
    assert d["cross"] == pytest.approx(0.02 * 0.01 - (0.5 * 0.01 * 0.005 + 0.5 * 0.03 * 0.01), abs=1e-15)
    parts = d["allocation"] + d["selection"] + d["interaction"] + d["currency"] + d["cross"]
    assert parts == pytest.approx(rp_dkk - rb_dkk, abs=1e-15)
    assert at.split_dkk(rp_dkk, 0.01) == pytest.approx(0.02)
    assert at.currency_effect(S(USD=1.0), S(USD=1.0), S(EUR=0.01)) is None            # USD held, no rate


def test_carino_hand_example_and_the_equal_returns_limit():
    rp, rb = pd.Series([0.10, -0.05]), pd.Series([0.05, 0.02])
    w = at.carino_weights(rp, rb)
    linked = at.link(pd.DataFrame({"active": rp - rb}), w)["active"]
    assert linked == pytest.approx(1.10 * 0.95 - 1.05 * 1.02, abs=1e-15)             # -0.026
    big_k = (np.log(1.045) - np.log(1.071)) / (0.045 - 0.071)
    assert w.iloc[0] == pytest.approx((np.log(1.10) - np.log(1.05)) / 0.05 / big_k)
    assert at.carino_k(0.01, 0.01) == pytest.approx(1 / 1.01)
    assert at.carino_k(0.01, 0.01 + 1e-9) == pytest.approx(1 / 1.01, rel=1e-6)        # continuous at the limit
    rev = at.carino_weights(rp[::-1], rb[::-1])
    assert rev.sort_index().tolist() == pytest.approx(w.tolist())                       # order doesn't matter


def test_linked_daily_brinson_matches_the_period_active_return():
    rng = np.random.default_rng(7)
    days, rows, rps, rbs = pd.bdate_range("2026-01-05", periods=60), [], [], []
    for _ in days:
        wp = pd.Series(rng.dirichlet(np.ones(4)), index=list("ABCD"))
        wb = pd.Series(rng.dirichlet(np.ones(4)), index=list("ABCD"))
        f = at.brinson_fachler(wp, wb, pd.Series(rng.normal(0, 0.01, 4), index=list("ABCD")),
                               pd.Series(rng.normal(0, 0.01, 4), index=list("ABCD")))
        t = at.totals(f)
        rows.append({e: t[e] for e in at.EFFECTS})
        rps.append(t["rp"])
        rbs.append(t["rb"])
    eff = pd.DataFrame(rows, index=days)
    rp, rb = pd.Series(rps, index=days), pd.Series(rbs, index=days)
    linked = at.link(eff, at.carino_weights(rp, rb))
    assert at.linking_error(float(linked.sum()), rp, rb) < 1e-12
    with pytest.raises(ValueError, match="without a return"):
        at.carino_weights(rp.where(rp.index != days[3]), rb)

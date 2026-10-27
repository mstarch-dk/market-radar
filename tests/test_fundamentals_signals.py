"""The kvalitetsscore and værdiscore: each metric on numbers that can be checked by hand, the edge cases (net
cash, no interest line, a loss, a bank), the dividend record from prices, and the percentile and scoring rules
(sector peers or the whole set, k of n pillars, never 0 for missing)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from radar.config import settings
from radar.fundamentals import store
from radar.signals import fundamentals as sf

ASOF = pd.Timestamp("2026-10-15")
QUARTERS = [pd.Timestamp(d) for d in ("2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30")]
YEARS = [pd.Timestamp(f"{y}-12-31") for y in (2021, 2022, 2023, 2024, 2025)]


@pytest.fixture(scope="module")
def cfg() -> dict:
    return settings()["fundamentals"]


def yahoo(flows_q: dict, balance: dict, flows_fy: dict | None = None, quarters=QUARTERS) -> pd.DataFrame:
    """Yahoo-style facts: each quarterly flow the same every quarter, balances the same at each quarter end and
    a year earlier, and fiscal-year flows given per year."""
    rows = []

    def add(item, end, fp, v):
        rows.append({"ticker": "X", "source": "yahoo", "item": item, "end": end, "value": v, "fp": fp,
                     "form": "quarterly" if fp == "Q" else "yearly", "currency": "USD",
                     "known": end + pd.Timedelta(days=40), "fetched": ASOF, "tag": item})
    for item, v in flows_q.items():
        for end in quarters:
            add(item, end, "Q", v)
    for item, v in balance.items():
        for end in [*quarters, quarters[-1] - pd.DateOffset(years=1)]:
            add(item, end, "Q", v)
    for item, by_year in (flows_fy or {}).items():
        for end, v in zip(YEARS, by_year):
            add(item, end, "FY", v)
    return store.normalize(pd.DataFrame(rows))


BASE_Q = {"revenue": 250.0, "operating_income": 50.0, "pretax": 50.0, "income_tax": 10.0, "net_income": 40.0,
          "cfo": 50.0, "capex": 12.5, "dna": 12.5, "interest": -5.0, "dividends_paid": 10.0, "buybacks": 5.0}
BASE_B = {"total_assets": 1000.0, "cash": 100.0, "current_liabilities": 200.0, "debt_current": 50.0,
          "debt_noncurrent": 300.0, "equity": 400.0, "shares": 100.0}


def test_quality_and_value_metrics_by_hand(cfg):
    m = sf.metrics(yahoo(BASE_Q, BASE_B), ASOF, cfg, False, mcap=2000.0)
    v = m["values"]
    assert v["fcf_margin"] == pytest.approx((200 - 50) / 1000)
    ic = 1000 - 100 - (200 - 50)                                  # assets - cash - non-debt current liabilities
    assert v["roic"] == pytest.approx(200 * (1 - 0.2) / ic)        # tax rate 40 / 200
    assert v["nd_ebitda"] == pytest.approx((350 - 100) / 250)
    assert v["interest_cover"] == pytest.approx(200 / 20)         # Yahoo's negative interest taken as a cost
    assert v["fcf_yield"] == pytest.approx(150 / 2000)
    ev = 2000 + 350 - 100
    assert v["ebit_ev"] == pytest.approx(200 / ev) and v["ev_ebit"] == pytest.approx(ev / 200)
    assert v["shareholder_yield"] == pytest.approx((40 + 20) / 2000)
    assert m["period_end"] == "2026-06-30" and m["basis"] == "4q"
    assert m["rank"]["nd_ebitda"] == pytest.approx(-1.0)            # lower is better: negated for ranking


def test_net_cash_ranks_best_and_a_loss_has_no_cover(cfg):
    rich = sf.metrics(yahoo(BASE_Q, BASE_B | {"cash": 900.0}), ASOF, cfg, False, mcap=2000.0)
    assert rich["rank"]["nd_ebitda"] == 1.0                       # net cash: -(-1)
    loss = sf.metrics(yahoo(BASE_Q | {"operating_income": -10.0, "pretax": -12.0}, BASE_B), ASOF, cfg, False, 2000.0)
    assert loss["values"]["interest_cover"] == 0.0
    assert loss["values"]["ev_ebit"] is None and loss["values"]["ebit_ev"] < 0   # ranked low, not dropped
    no_debt = sf.metrics(yahoo({k: v for k, v in BASE_Q.items() if k != "interest"},
                               BASE_B | {"debt_current": 0.0, "debt_noncurrent": 0.0}), ASOF, cfg, False, 2000.0)
    assert no_debt["values"]["interest_cover"] == cfg["interest_cover_cap"]


def test_missing_is_missing_never_zero(cfg):
    m = sf.metrics(yahoo({k: v for k, v in BASE_Q.items() if k != "capex"}, BASE_B), ASOF, cfg, False, None)
    v = m["values"]
    assert v["fcf_margin"] is None and v["fcf_yield"] is None and v["ebit_ev"] is None
    assert any("no market value" in n for n in m["notes"])
    old = [q - pd.DateOffset(years=1) for q in QUARTERS]          # the latest report is over a year old
    stale = sf.metrics(yahoo(BASE_Q, BASE_B, quarters=old), ASOF, cfg, False, 2000.0)
    assert stale["values"]["roic"] is None and stale["values"]["fcf_margin"] is None
    assert any("left out" in n for n in stale["notes"])


def test_cash_flow_falls_back_to_the_latest_fiscal_year(cfg):
    # quarterly income statement, cash flow only for the full year (as Yahoo has it for many European companies)
    cash_items = ("cfo", "capex", "dividends_paid", "buybacks")
    q = {k: v for k, v in BASE_Q.items() if k not in cash_items}
    fy = {"revenue": [1000.0] * 5, "cfo": [180.0] * 5, "capex": [60.0] * 5, "dividends_paid": [30.0] * 5,
          "buybacks": [50.0] * 5}
    m = sf.metrics(yahoo(q, BASE_B, fy), ASOF, cfg, False, mcap=2000.0)    # FY 2025 ends 288 days before ASOF
    v = m["values"]
    assert v["shareholder_yield"] == pytest.approx((30 + 50) / 2000)
    assert v["fcf_yield"] == pytest.approx(120 / 2000)
    assert v["fcf_margin"] == pytest.approx(120 / 1000)          # against that year's revenue, not the last 4 quarters
    assert any("fiscal year ending 31 Dec 2025" in n for n in m["notes"])
    later = ASOF + pd.Timedelta(days=200)                          # past annual_max_age_days: missing, not 0
    assert sf.metrics(yahoo(q, BASE_B, fy), later, cfg, False, mcap=2000.0)["values"]["shareholder_yield"] is None
    mixed = sf.metrics(yahoo(q | {"capex": 12.5}, BASE_B, fy), ASOF, cfg, False, mcap=2000.0)
    assert mixed["values"]["fcf_yield"] is None                    # FY operating cash flow, 4-quarter capex: no FCF
    fresh = sf.metrics(yahoo(BASE_Q, BASE_B, fy), ASOF, cfg, False, mcap=2000.0)
    assert fresh["values"]["shareholder_yield"] == pytest.approx((40 + 20) / 2000)
    assert not any("fiscal year ending" in n for n in fresh["notes"])


def test_debt_missing_from_the_latest_balance_is_unknown_not_zero(cfg):
    no_debt_b = {k: v for k, v in BASE_B.items() if not k.startswith("debt")}
    no_interest = {k: v for k, v in BASE_Q.items() if k != "interest"}
    old = [q - pd.DateOffset(years=2) for q in QUARTERS]          # debt reported two years ago, not since
    renamed = store.normalize(pd.concat([yahoo(no_interest, no_debt_b),
                                         yahoo({}, {"debt_noncurrent": 300.0}, quarters=old)]))
    m = sf.metrics(renamed, ASOF, cfg, False, mcap=2000.0)
    v = m["values"]
    assert v["nd_ebitda"] is None and m["rank"]["nd_ebitda"] is None   # not "net cash: best"
    assert v["interest_cover"] is None
    assert v["ebit_ev"] is None and v["ev_ebit"] is None
    assert any("debt" in n and "left out" in n for n in m["notes"])
    never = sf.metrics(yahoo(no_interest, no_debt_b), ASOF, cfg, False, mcap=2000.0)   # no debt line, ever
    assert never["rank"]["nd_ebitda"] == 1.0 and never["values"]["ebit_ev"] == pytest.approx(200 / 1900)
    assert any("no debt" in n for n in never["notes"])


def test_stability_metrics_over_fiscal_years(cfg):
    fy = {"revenue": [800, 880, 968, 1065, 1171], "gross_profit": [400, 440, 484, 532, 585],
          "operating_income": [100, 110, 120, 130, 140]}
    v = sf.metrics(yahoo(BASE_Q, BASE_B, fy), ASOF, cfg, False, 2000.0)["values"]
    assert v["gm_stability"] == pytest.approx(np.std([0.5, 0.5, 0.5, 0.4995, 0.4996], ddof=1) * 100, abs=0.01)
    assert v["rev_stability"] == pytest.approx(1.0, abs=1e-3) and v["rev_cagr"] == pytest.approx(0.10, abs=0.002)
    shaky = sf.metrics(yahoo(BASE_Q, BASE_B, {"revenue": [800, 600, 900, 700, 1000],
                                               "gross_profit": [400, 200, 500, 250, 500]}), ASOF, cfg, False, 2000.0)
    assert shaky["values"]["rev_stability"] < 0.6 and shaky["values"]["gm_stability"] > 5     # ~9.8 pp


def test_a_bank_is_measured_on_the_financial_set(cfg):
    fy = {"net_income": [80, 85, 90, 95, 100]}
    bal = BASE_B | {"total_assets": 10000.0, "equity": 800.0}
    m = sf.metrics(yahoo(BASE_Q, bal, fy | {"equity": [700, 720, 750, 780, 800]}), ASOF, cfg, True, mcap=1600.0)
    v = m["values"]
    assert v["roe"] == pytest.approx(160 / 800) and v["equity_assets"] == pytest.approx(0.08)
    assert v["bp"] == pytest.approx(0.5) and v["pb"] == pytest.approx(2.0) and v["ep"] == pytest.approx(0.1)
    assert v["fcf_margin"] is None and v["ebit_ev"] is None and v["roic"] is None
    assert v["roe_stability"] is not None


def test_dividend_record():
    assert sf.dividend_years({2021: 1.0, 2022: 1.1, 2023: 1.0, 2024: 1.2, 2025: 1.3}, 2025) == 2   # 2023 was a cut
    assert sf.dividend_years({2023: 1.0, 2024: 0.98, 2025: 1.0}, 2025) == 3     # within 5%: not a cut; first year counts
    assert sf.dividend_years({2024: 1.0, 2025: 0.0}, 2025) == 0                 # stopped paying
    assert sf.dividend_years({}, 2025) is None and sf.dividend_years({2024: 1.0}, 2025) is None


def test_dividends_read_from_adjusted_and_traded_closes():
    idx = pd.bdate_range("2023-01-02", "2025-12-31")
    raw = pd.Series(100.0, index=idx)
    divs = {pd.Timestamp("2023-06-01"): 2.0, pd.Timestamp("2024-06-03"): 2.2, pd.Timestamp("2025-06-02"): 2.4,
            pd.Timestamp("2025-12-01"): 0.5}
    factor = pd.Series(1.0, index=idx)
    for day, d in sorted(divs.items(), reverse=True):               # back-adjust, newest first
        factor[factor.index < day] *= 1 - d / 100.0
    got = sf.dps_by_year(raw * factor, raw)
    assert got == pytest.approx({2023: 2.0, 2024: 2.2, 2025: 2.9}, rel=1e-6)


def _table(rows):
    return pd.DataFrame([{"ticker": t, "set": s, "sector": sec, "member": mem, **{f"rank_{k}": v for k, v in r.items()}}
                         for t, s, sec, mem, r in rows])


def test_percentiles_use_sector_peers_when_there_are_enough(cfg):
    cfg = cfg | {"min_sector_peers": 3}
    rows = [(f"T{i}", "standard", "Tech", True, {"roic": i}) for i in range(4)] + \
           [(f"U{i}", "standard", "Util", True, {"roic": 10 + i}) for i in range(2)]
    s = sf.score(_table(rows), cfg)
    assert s.at["T3", "pct_roic"] == 75.0 and s.at["T3", "basis_roic"] == "sector" and s.at["T3", "peers_roic"] == 4
    assert s.at["U1", "basis_roic"] == "universe" and s.at["U1", "pct_roic"] == pytest.approx(500 / 6)


def test_k_of_n_pillars_and_required_profitability(cfg):
    full = {"fcf_margin": 1, "roic": 1, "gm_stability": -1, "rev_stability": 1, "nd_ebitda": -1,
            "interest_cover": 1, "div_years": 1, "fcf_yield": 1, "ebit_ev": 1, "shareholder_yield": 1,
            "ey_vs_history": 1}
    rows = [("A", "standard", "", True, full),
            ("B", "standard", "", True, {k: 0 for k in full}),
            ("NOPROF", "standard", "", True, {k: v for k, v in full.items() if k not in ("fcf_margin", "roic")}),
            ("THIN", "standard", "", True, {"fcf_margin": 1, "roic": 1, "fcf_yield": 1})]
    s = sf.score(_table(rows), cfg)
    assert s.at["A", "quality"] is not None and s.at["A", "q_n"] == 4 and s.at["A", "qv"] is not None
    assert s.at["A", "quality"] > s.at["B", "quality"]
    assert pd.isna(s.at["NOPROF", "quality"]) and s.at["NOPROF", "q_n"] == 3   # three pillars, but no profitability
    assert pd.isna(s.at["THIN", "quality"]) and pd.isna(s.at["THIN", "value"]) and pd.isna(s.at["THIN", "qv"])


def test_a_stock_outside_the_lists_is_ranked_against_them_without_moving_them(cfg):
    rows = [(f"M{i}", "standard", "", True, {"roic": i}) for i in range(4)]
    alone = sf.score(_table(rows), cfg)
    s = sf.score(_table(rows + [("HELD", "standard", "", False, {"roic": 2.5})]), cfg)
    assert s.at["HELD", "pct_roic"] == 60.0 and s.at["HELD", "peers_roic"] == 5   # 3 of 5 below, itself included
    assert (s.loc[[f"M{i}" for i in range(4)], "pct_roic"] == alone["pct_roic"]).all()


def test_banks_are_ranked_among_banks(cfg):
    rows = [(f"B{i}", "financial", "Financial Services", True, {"roe": i / 10}) for i in range(3)] + \
           [(f"S{i}", "standard", "Financial Services", True, {"roic": i}) for i in range(3)]
    s = sf.score(_table(rows), cfg)
    assert s.at["B2", "pct_roe"] == pytest.approx(200 / 3) and s.at["B2", "peers_roe"] == 3
    assert pd.isna(s.at["S2", "pct_roe"])

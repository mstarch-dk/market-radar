import pandas as pd

from radar import external

FACTSET_TEXT = """EARNINGS INSIGHT
Key Metrics
• Earnings Growth: For Q3 2026, the estimated (year-over-year) earnings growth rate for the S&P 500 is 29.5%. If
• Earnings Revisions: On June 30, the estimated (year-over-year) earnings growth rate for the S&P 500 for Q3
2026 was 26.7%. Four sectors are expected to report higher earnings today
• Earnings Guidance: For Q3 2026, 44 S&P 500 companies have issued negative EPS guidance and 72 S&P 500
companies have issued positive EPS guidance.
• Valuation: The forward 12-month P/E ratio for the S&P 500 is 19.0. This P/E ratio is below the 5-year average
(19.8) and below the 10-year average (19.1).
Four sectors have recorded an increase in dollar-level earnings due to upward
revisions to earnings estimates, led by the Energy, Information Technology, and Financials sectors. On the other hand, six
sectors have recorded a decrease in their dollar-level earnings due to downward revisions to earnings estimates, led by
the Materials, Consumer Staples, and Health Care sectors.
For CY 2026, analysts are projecting earnings growth of 32.4% and revenue growth of 12.4%.
For CY 2027, analysts are projecting earnings growth of 15.8% and revenue growth of 9.3%.
"""


def test_parse_factset():
    r = external.parse_factset([FACTSET_TEXT])
    assert r["quarter"] == "Q3 2026"
    assert (r["growth_now"], r["growth_start"]) == (29.5, 26.7)
    assert (r["guidance_neg"], r["guidance_pos"]) == (44, 72)
    assert (r["fwd_pe"], r["fwd_pe_5y"], r["fwd_pe_10y"]) == (19.0, 19.8, 19.1)
    assert r["cy_next_growth"] == 15.8  # the last calendar year mentioned
    assert r["rev_up_sectors"] == "Energy, Information Technology, Financials"
    assert r["rev_down_sectors"] == "Materials, Consumer Staples, Health Care"


def test_parse_factset_missing_fields_are_none():
    r = external.parse_factset(["nothing useful here"])
    assert all(v is None for v in r.values())


def test_cot_rows_handles_both_report_layouts():
    tff = {"report_date_as_yyyy_mm_dd": "2026-10-06T00:00:00.000", "cftc_contract_market_code": "13874A",
           "open_interest_all": "1000", "asset_mgr_positions_long": "600", "asset_mgr_positions_short": "100"}
    disagg = {"report_date_as_yyyy_mm_dd": "2026-10-06T00:00:00.000", "cftc_contract_market_code": "088691",
              "open_interest_all": "400", "m_money_positions_long_all": "120", "m_money_positions_short_all": "20"}
    a = external.cot_rows([tff], {"asset_mgr_positions": "Asset managers"}, {"13874A": "S&P 500"})
    b = external.cot_rows([disagg], {"m_money_positions": "Managed money"}, {"088691": "Gold"})
    assert a.iloc[0]["net_pct_oi"] == 50 and a.iloc[0]["market"] == "S&P 500"
    assert b.iloc[0]["net_pct_oi"] == 25 and b.iloc[0]["group"] == "Managed money"


def test_cot_table_flags_extremes_against_own_history():
    dates = pd.date_range("2023-01-03", periods=160, freq="W-TUE")
    hi = pd.DataFrame({"date": dates, "market": "A", "group": "G", "net": 0, "net_pct_oi": range(160)})
    lo = pd.DataFrame({"date": dates, "market": "B", "group": "G", "net": 0, "net_pct_oi": range(160, 0, -1)})
    mid = pd.DataFrame({"date": dates, "market": "C", "group": "G", "net": 0,
                        "net_pct_oi": [50 + (i % 2) * 10 - 5 for i in range(160)]})
    t = external.cot_table(pd.concat([hi, lo, mid]), lookback_weeks=156, extreme=10).set_index("market")
    assert t.loc["A", "flag"] == "3y high" and t.loc["A", "chg_4w"] == 4
    assert t.loc["B", "flag"] == "3y low"
    assert pd.isna(t.loc["C", "flag"])


def test_parse_oecd_cli_and_phases():
    csv = "REF_AREA,TIME_PERIOD,OBS_VALUE\n" + "\n".join(
        f"{a},2026-{m:02d},{v}" for a, vals in {"USA": [100.5, 100.7, 100.9, 101.0],
                                                "CHN": [98.5, 98.0, 97.6, 97.4],
                                                "G20": [100.3, 100.2, 100.2, 100.1]}.items()
        for m, v in zip(range(6, 10), vals))
    cli = external.parse_oecd_cli(csv)
    assert cli.index[-1] == pd.Timestamp("2026-09-01")
    t = external.cli_table(cli, {"G20": "G20", "USA": "United States", "CHN": "China"})
    assert list(t["area"]) == ["G20", "USA", "CHN"]  # config order, so G20 carries the regime vote
    assert dict(zip(t["area"], t["phase"])) == {"G20": "Slowdown", "USA": "Expansion", "CHN": "Contraction"}

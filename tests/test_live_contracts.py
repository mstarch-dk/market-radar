"""Live contract checks: each source's parser against the real, current answer.

The rest of the suite runs offline against recorded or synthetic payloads, so it can't notice that a source moved,
changed its layout or stopped updating. These can. They are deselected by default (marker `network`); run them by
hand before a release, or when a source looks odd:

    uv run pytest -m network -q

Each asks once, through net.get (paced, and recorded in the operations log like any other request), and checks
the parse and that the data is recent. A failure here means: update the parser and its fixture (scripts/
capture_fixture.py), not the test.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from radar import constituents, external, ingest, net, sentiment, valuation
from radar.discovery import sources
from radar.signals import periods

pytestmark = pytest.mark.network
TODAY = date.today()


def _recent(last, days: int, what: str):
    last = pd.Timestamp(last).date()
    assert (TODAY - last).days <= days, f"{what}: newest value is from {last}, more than {days} days ago"


def _get(url: str, **kw):
    r = net.get(url, timeout=60, **kw)
    r.raise_for_status()
    return r


def test_fred():
    s = ingest.parse_fred_csv(_get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10").text, "DGS10")
    _recent(s.dropna().index[-1], 10, "FRED DGS10")


def test_oecd_cli():
    areas = list(external.cfg().get("oecd_cli", {}))
    start = (TODAY - timedelta(days=400)).strftime("%Y-%m")
    df = external.parse_oecd_cli(_get(external.OECD_CLI_URL.format(areas="+".join(areas), start=start)).text)
    assert set(areas) <= set(df.columns), f"areas missing: {set(areas) - set(df.columns)}"
    _recent(df.index[-1], 120, "OECD CLI")


def test_ecb():
    for key, (sid, _label) in external.cfg().get("ecb", {}).items():
        s = external.parse_ecb(_get(external.ECB_URL.format(key=sid, start=(TODAY - timedelta(days=60)).isoformat())).text)
        _recent(s.index[-1], 10, f"ECB {key}")


def test_cftc():
    dataset, groups = external.COT_DATASETS["tff"]
    names = {str(code): name for name, code in external.cfg().get("cot", {}).get("tff", {}).items()}
    raw = external.cot_fetch(dataset, list(names), TODAY - timedelta(days=30))
    rows = external.cot_parse(raw, groups, names, "tff")
    assert not rows.empty
    _recent(rows["date"].max(), 14, "CFTC")


def test_cboe_put_call():
    for back in range(8):
        d = TODAY - timedelta(days=back)
        r = net.get(sentiment.CBOE_URL.format(d=d), timeout=30, expected=(403, 404))
        if r.status_code == 200:
            assert 0.05 < sentiment.parse_cboe(r.json())["total"] < 10
            return
    pytest.fail("no CBOE daily statistics in the last 8 days: has the address changed?")


def test_aaii():
    df = sentiment.parse_aaii(_get(sentiment.AAII_URL).content)
    _recent(df["date"].iloc[-1], 14, "AAII")


def test_multpl_cape():
    s = valuation.parse_multpl(_get(valuation.MULTPL_URL).text)
    _recent(s.index[-1], 10, "CAPE")


def test_damodaran_erp():
    df = valuation.parse_damodaran(_get(valuation.DAMODARAN_URL).content)
    _recent(df["date"].iloc[-1], 70, "Damodaran ERP")


def test_spy_holdings():
    assert len(constituents.spy_holdings()) >= constituents.SPY_MIN_HOLDINGS


@pytest.mark.parametrize("key", ["stoxx600", "sp500"])
def test_ishares_index_holdings(key):
    assert not sources.fetch_index(key).empty


def test_edgar_company_facts():
    """SEC's company facts still parse to a recent TTM. Sent with the radar's plain User-Agent (no contact: the
    test data folder has none); a 403 here means SEC now wants the contact for this endpoint too."""
    from radar.fundamentals import edgar

    df = edgar.parse_companyfacts(_get(edgar.FACTS_URL.format(cik=320193)).json(), "AAPL", TODAY)
    rev = periods.ttm(df, "revenue")
    assert rev is not None and rev.basis in ("fy", "ytd")
    _recent(rev.end, 200, "EDGAR AAPL revenue")


def test_yahoo_statements():
    from radar.fundamentals import store, yahoo

    raw = yahoo.fetch_statements("AAPL")
    assert {("income", "quarterly"), ("cash", "quarterly"), ("balance", "yearly")} <= set(raw["blocks"]), raw["errors"]
    df = yahoo.merge(store.empty(), yahoo.parse_statements(raw["blocks"], "AAPL", "USD", TODAY), TODAY,
                     {"quarterly": 45, "annual": 75})
    for item in ("revenue", "operating_income", "cfo", "capex"):
        v = periods.ttm(df, item)
        assert v is not None and v.basis == "4q", item
        _recent(v.end, 200, f"Yahoo AAPL {item}")


def test_yahoo_daily_bars_reach_the_latest_session():
    """The failure behind PR #34: every ticker, European listings too, has a recent bar, adjusted close included."""
    df = ingest.norm_dates(ingest.download_bars(["SPY", "RHM.DE", "NOVO-B.CO", "7203.T"], TODAY - timedelta(days=20)))
    assert set(df["ticker"]) == {"SPY", "RHM.DE", "NOVO-B.CO", "7203.T"}
    last = df.groupby("ticker")["date"].max()
    for t, d in last.items():
        _recent(d, 5, f"Yahoo {t}")
    assert df["close"].notna().all() and df["raw_close"].notna().all()

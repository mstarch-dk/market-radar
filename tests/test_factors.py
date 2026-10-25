import io
import zipfile
from datetime import date

import numpy as np
import pandas as pd
import pytest

from radar.config_schema import Factors
from radar.sources import factors

# the layout of a French file: notes, a monthly block, a second monthly block with a title, an annual block
FRENCH = """This file was created using the 202608 CRSP database.
Missing data are indicated by -99.99 or -999.

  Average Value Weighted Returns -- Monthly
,Agric,Food ,Soda
192607,   2.36,   0.09, -99.99
192608,   2.23,   2.71, -999
192609,  -0.57,   1.59,   1.00

  Average Equal Weighted Returns -- Monthly
,Agric,Food ,Soda
192607,   9.00,   9.00,   9.00
192608,   9.00,   9.00,   9.00

  Average Value Weighted Returns -- Annual
,Agric,Food ,Soda
  1927,  10.00,  10.00,  10.00

Copyright 2026 Eugene F. Fama and Kenneth R. French
"""

FACTORS_ONLY = """This file was created using the 202608 Bloomberg database.

,WML
199011    ,0.14
199012   ,-2.64
 Annual Factors: January-December
,WML
  1991,   5.00
"""


def _zip(name: str, text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, text)
    return buf.getvalue()


def test_french_blocks_by_title_missing_codes_become_nan():
    blocks = factors.french_blocks(FRENCH)
    assert list(blocks) == ["Average Value Weighted Returns -- Monthly", "Average Equal Weighted Returns -- Monthly"]
    vw = blocks["Average Value Weighted Returns -- Monthly"]
    assert list(vw.columns) == ["Agric", "Food", "Soda"]                       # header names stripped
    assert vw.index[0] == pd.Timestamp("1926-07-31")                           # month-end
    assert vw.loc["1926-07-31", "Agric"] == pytest.approx(0.0236)              # percent -> decimal
    assert vw["Soda"].isna().sum() == 2 and vw.loc["1926-09-30", "Soda"] == pytest.approx(0.01)   # -99.99, -999


def test_parse_french_first_block_and_named_block():
    assert factors.parse_french(_zip("x.csv", FACTORS_ONLY)).loc["1990-12-31", "WML"] == pytest.approx(-0.0264)
    ew = factors.parse_french(_zip("x.CSV", FRENCH), "equal weighted returns -- monthly")
    assert (ew == 0.09).all().all()


def test_parse_french_fails_loudly():
    with pytest.raises(ValueError, match="no block titled"):
        factors.parse_french(_zip("x.csv", FRENCH), "Number of Firms")
    with pytest.raises(ValueError, match="no monthly returns"):
        factors.parse_french(_zip("x.csv", "Copyright only\n"))
    with pytest.raises(ValueError, match="no CSV"):
        factors.parse_french(_zip("x.txt", FRENCH))


JKP = """location,name,freq,weighting,direction,n_stocks,n_stocks_min,date,ret
dnk,mkt,monthly,vw,na,24,na,1986-01-31,0.05
dnk,mkt,monthly,vw,na,24,na,1986-02-28,
usa,mkt,monthly,vw,na,24,na,1986-01-31,0.01
usa,mkt,monthly,vw,na,24,na,1986-02-28,0.02
"""


def test_parse_jkp_wide_keeps_missing():
    df = factors.parse_jkp(_zip("[x].csv", JKP))
    assert list(df.columns) == ["dnk", "usa"]
    assert df.loc["1986-01-31", "dnk"] == 0.05 and np.isnan(df.loc["1986-02-28", "dnk"])


def test_parse_jkp_rejects_duplicates_and_missing_columns():
    with pytest.raises(ValueError, match="duplicate"):
        factors.parse_jkp(_zip("x.csv", JKP + "usa,mkt,monthly,vw,na,24,na,1986-02-28,0.03\n"))
    with pytest.raises(ValueError, match="lacks"):
        factors.parse_jkp(_zip("x.csv", "location,date\nusa,1986-01-31\n"))


def _settings(monkeypatch, datasets: dict):
    monkeypatch.setattr(factors, "cfg", lambda: Factors(max_age_days=30, french=datasets))


def _wide(n: int, cols=("A", "B")) -> pd.DataFrame:
    idx = pd.period_range("2000-01", periods=n, freq="M").to_timestamp(how="end").normalize()
    return pd.DataFrame({c: np.linspace(0.01, 0.02, n) for c in cols}, index=idx)


def test_update_stores_skips_fresh_and_keeps_a_failing_dataset(monkeypatch):
    _settings(monkeypatch, {"a": "A_CSV", "b": "B_CSV"})
    answers = {"A_CSV": _wide(24), "B_CSV": _wide(12, ("X",))}
    monkeypatch.setattr(factors, "fetch", lambda spec: answers[spec["file"]])
    assert factors.update_factors(date(2026, 10, 1)).startswith("2 downloaded")
    assert factors.panel("french:a").shape == (24, 2)
    assert factors.update_factors(date(2026, 10, 15)) == "0 downloaded, 2 up to date"

    def broken(spec):
        if spec["file"] == "B_CSV":
            raise ValueError("format changed")
        return _wide(25)
    monkeypatch.setattr(factors, "fetch", broken)
    with pytest.raises(RuntimeError, match="french:b .*format changed"):
        factors.update_factors(date(2026, 11, 15))
    assert len(factors.panel("french:a")) == 25           # the good one is written
    assert factors.panel("french:b").shape == (12, 1)      # the failing one keeps its rows


def test_update_refuses_an_answer_with_less_history(monkeypatch):
    _settings(monkeypatch, {"a": "A_CSV"})
    monkeypatch.setattr(factors, "fetch", lambda spec: _wide(24))
    factors.update_factors(date(2026, 10, 1))
    monkeypatch.setattr(factors, "fetch", lambda spec: _wide(24).iloc[6:])   # starts later: a truncated file
    with pytest.raises(RuntimeError, match="kept the stored copy"):
        factors.update_factors(date(2026, 10, 1), force=True)
    assert len(factors.panel("french:a")) == 24


def test_total_adds_rf_and_keeps_missing():
    idx = _wide(3).index
    data = pd.concat([
        factors.long_rows("french:ff3_us", pd.DataFrame({"RF": [0.001, 0.002, np.nan]}, index=idx), date(2026, 1, 1)),
    ])
    ex = pd.DataFrame({"dnk": [0.01, np.nan, 0.03]}, index=idx)
    t = factors.total(ex, data)
    assert t["dnk"].iloc[0] == pytest.approx(0.011)
    assert t["dnk"].isna().tolist() == [False, True, True]     # missing return, missing RF: missing, never 0


# the layout of French's daily developed files (a real file's header and first rows, trimmed)
DAILY = """This file was created using the 202608 Bloomberg database.

Missing data are indicated by -99.99.



,Mkt-RF,SMB,HML,RMW,CMA,RF
19900702    ,0.69   ,-0.08   ,-0.33    ,0.21   ,-0.12    ,0.03
19900703    ,0.21    ,0.12    ,0.05   ,-0.99    ,0.14    ,0.03
19900704    ,0.05   ,-99.99    ,0.11    ,0.02    ,0.01    ,0.03
19900705   ,-0.62    ,0.21    ,0.31    ,0.07    ,0.09    ,0.03
19900706    ,0.33    ,0.03   ,-0.02    ,0.11   ,-0.05    ,0.03
19900709    ,0.10    ,0.01    ,0.02    ,0.03    ,0.04    ,0.03
"""


def test_daily_french_file_parses_days_and_missing():
    df = factors.parse_french(_zip("Developed_5_Factors_Daily.csv", DAILY), daily=True)
    assert list(df.columns) == ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]
    assert df.index[0] == pd.Timestamp("1990-07-02") and len(df) == 6
    assert df.loc["1990-07-02", "Mkt-RF"] == pytest.approx(0.0069)
    assert np.isnan(df.loc["1990-07-04", "SMB"])                          # -99.99: missing, never a return
    with pytest.raises(ValueError, match="no daily returns"):
        factors.parse_french(_zip("x.csv", FACTORS_ONLY), daily=True)      # a monthly file read as daily
    assert factors.french_blocks(DAILY) == {}                              # and daily rows aren't monthly


def test_to_weeks_compounds_and_leaves_gaps_missing():
    df = factors.parse_french(_zip("x.csv", DAILY), daily=True)
    w = factors.to_weeks(df)
    assert list(w.index) == [pd.Timestamp("1990-07-06")]                  # the week of 9 July isn't complete
    mkt = (1.0069 * 1.0021 * 1.0005 * (1 - 0.0062) * 1.0033) - 1
    assert w.loc["1990-07-06", "Mkt-RF"] == pytest.approx(mkt)
    assert np.isnan(w.loc["1990-07-06", "SMB"])                            # a missing day: the week is missing


def test_daily_datasets_go_to_their_own_store(monkeypatch):
    monkeypatch.setattr(factors, "cfg", lambda: Factors(max_age_days=30, french={"a": "A_CSV"},
                                                        french_daily={"d": "D_CSV"}))
    daily = factors.parse_french(_zip("x.csv", DAILY), daily=True)
    answers = {"A_CSV": _wide(24), "D_CSV": daily}
    monkeypatch.setattr(factors, "fetch", lambda spec: answers[spec["file"]])
    assert factors.update_factors(date(2026, 10, 1)).startswith("2 downloaded")
    assert set(factors.load()["key"]) == {"french:a"}
    assert set(factors.load_daily()["key"]) == {"french_daily:d"}
    assert factors.daily_panel("french_daily:d").shape == (6, 6)
    assert factors.update_factors(date(2026, 10, 2)) == "0 downloaded, 2 up to date"
    monkeypatch.setattr(factors, "fetch", lambda spec: answers[spec["file"]].iloc[2:])   # starts later
    with pytest.raises(RuntimeError, match="french_daily:d"):
        factors.update_factors(date(2026, 10, 2), force=True)
    assert len(factors.daily_panel("french_daily:d")) == 6                 # kept the stored rows

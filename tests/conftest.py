from pathlib import Path

import pytest

from radar import coverage, tickers, universe, userstore
from radar.discovery import scan

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_data(tmp_path, monkeypatch):
    """Point every module-level data path at a temporary directory."""
    monkeypatch.setattr(coverage, "DATA", tmp_path)
    monkeypatch.setattr(coverage, "LOG_FILE", tmp_path / "sources.json")
    monkeypatch.setattr(coverage, "TRANSACTIONS_FILE", tmp_path / "transactions.csv")
    monkeypatch.setattr(coverage, "HOLDINGS_FILE", tmp_path / "holdings.csv")
    monkeypatch.setattr(coverage, "POSITIVE_LIST_FILE", tmp_path / "positivliste.xlsx")
    monkeypatch.setattr(universe, "DATA", tmp_path)
    monkeypatch.setattr(universe, "TRANSACTIONS_FILE", tmp_path / "transactions.csv")
    monkeypatch.setattr(universe, "HOLDINGS_FILE", tmp_path / "holdings.csv")
    monkeypatch.setattr(universe, "POSITIVE_LIST_FILE", tmp_path / "positivliste.xlsx")
    monkeypatch.setattr(userstore, "USERDATA", tmp_path / "userdata")
    monkeypatch.setattr(tickers, "DATA", tmp_path)
    monkeypatch.setattr(tickers, "_cache", None)
    d = tmp_path / "discovery"
    for name, path in {"DIR": d, "UNIVERSE_FILE": d / "universe.csv", "ISIN_MAP_FILE": d / "isin_map.csv",
                       "PRICES_FILE": d / "prices.parquet", "SNAPSHOTS": d / "snapshots",
                       "REPORT_FILE": tmp_path / "reports" / "discovery.json"}.items():
        monkeypatch.setattr(scan, name, path)
    return tmp_path

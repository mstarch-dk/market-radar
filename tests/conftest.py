from pathlib import Path

import pytest

from radar import coverage, universe

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
    return tmp_path

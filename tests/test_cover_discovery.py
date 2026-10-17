"""The discovery universe's sources offline: Yahoo screener paging, iShares holdings over HTTP, FX rates and
how one failed market is handled while the universe is rebuilt."""
from datetime import date, timedelta

import pandas as pd
import pytest

from conftest import FIXTURES
from fakes import Resp, fake_yf, serve
from radar import ingest, net, sourcelog, universe
from radar.discovery import scan, sources

# ---------------- Yahoo screener ----------------

class FakeScreener:
    """yfinance's EquityQuery + screen: a query is kept as nested tuples; `screen` answers from `pages(query,
    offset, size)` and records (query, offset, size)."""

    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def EquityQuery(self, op, args):  # noqa: N802 (yfinance's name)
        return (op, tuple(args))

    def screen(self, query, size, offset, sortField, sortAsc):  # noqa: N803
        self.calls.append((query, offset, size))
        return self.pages(query, offset, size)


def _install(monkeypatch, pages) -> FakeScreener:
    fake = FakeScreener(pages)
    monkeypatch.setattr(net, "yf", lambda: fake)
    return fake


def _quotes(n):
    return [{"symbol": f"S{i}"} for i in range(n)]


def _paged(all_quotes, total=True):
    def pages(query, offset, size):
        res = {"quotes": all_quotes[offset:offset + size]}
        return res | ({"total": len(all_quotes)} if total else {})
    return pages


def test_screener_pages_are_followed_until_the_last_short_page(monkeypatch):
    fake = _install(monkeypatch, _paged(_quotes(5)))
    out = sources.screen_exchange("CPH", page=2)
    assert [q["symbol"] for q in out] == ["S0", "S1", "S2", "S3", "S4"]
    assert [c[1] for c in fake.calls] == [0, 2, 4]


def test_screener_stops_when_total_is_reached_without_asking_for_an_empty_page(monkeypatch):
    fake = _install(monkeypatch, _paged(_quotes(4)))
    assert len(sources.screen_exchange("CPH", page=2)) == 4
    assert [c[1] for c in fake.calls] == [0, 2]


def test_screener_without_a_total_still_reads_every_page(monkeypatch):
    _install(monkeypatch, _paged(_quotes(5), total=False))
    assert len(sources.screen_exchange("CPH", page=2)) == 5


def test_screener_stops_at_the_limit_even_when_yahoo_has_more(monkeypatch):
    fake = _install(monkeypatch, _paged(_quotes(10)))
    assert len(sources.screen_exchange("CPH", page=2, limit=4)) == 4     # the cap is a hard stop
    assert len(fake.calls) == 2


def test_screener_query_asks_for_the_exchange_above_min_cap_and_the_sector(monkeypatch):
    fake = _install(monkeypatch, _paged(_quotes(1)))
    sources.screen_exchange("STO", min_cap=3e8, sector="Energy")
    query = fake.calls[0][0]
    assert query == ("and", (("eq", ("exchange", "STO")), ("gt", ("intradaymarketcap", 3e8)),
                             ("eq", ("sector", "Energy"))))


def test_screener_waits_and_retries_when_yahoo_throttles(monkeypatch):
    answers = [RuntimeError("Too Many Requests"), {"quotes": _quotes(1), "total": 1}]

    def pages(query, offset, size):
        a = answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a
    _install(monkeypatch, pages)
    waits = []
    monkeypatch.setattr("time.sleep", waits.append)
    assert len(sources.screen_exchange("CPH")) == 1 and waits == [20.0]


def test_sector_screen_maps_each_symbol_to_the_sector_it_was_found_under(monkeypatch):
    found = {("CPH", "Energy"): ["ORSTED.CO"], ("STO", "Technology"): ["ERIC-B.ST"],
             ("CPH", "Healthcare"): ["NOVO-B.CO"]}

    def pages(query, offset, size):
        parts = dict((a[0], a[1]) for op, a in query[1] if op == "eq")
        syms = found.get((parts["exchange"], parts["sector"]), [])
        return {"quotes": [{"symbol": s} for s in syms], "total": len(syms)}
    fake = _install(monkeypatch, pages)
    out = sources.screen_sectors(["CPH", "STO"], min_cap=1e8)
    assert out == {"ORSTED.CO": "Energy", "ERIC-B.ST": "Technology", "NOVO-B.CO": "Healthcare"}
    assert len(fake.calls) == 2 * len(sources.SECTORS)                 # one call per exchange and sector
    assert all(c[0][1][1] == ("gt", ("intradaymarketcap", 1e8)) for c in fake.calls)


# ---------------- iShares holdings over HTTP ----------------

BOM = b"\xef\xbb\xbf"


@pytest.mark.parametrize("key, file, minimum, symbol", [
    ("stoxx600", "ishares_exsa_holdings.csv", 30, "ASML.AS"),
    ("sp500", "ishares_cspx_holdings.csv", 5, "NVDA"),
])
def test_index_holdings_with_a_byte_order_mark_parse(monkeypatch, key, file, minimum, symbol):
    url, _, what = sources.INDEXES[key]
    monkeypatch.setitem(sources.INDEXES, key, (url, minimum, what))      # the fixtures are trimmed
    calls = serve(monkeypatch, {"ishares": Resp(content=BOM + (FIXTURES / file).read_bytes())})
    df = sources.fetch_index(key)
    assert symbol in set(df["ticker"]) and calls == [url]


def test_index_holdings_file_shorter_than_the_index_raises(monkeypatch):
    serve(monkeypatch, {"ishares": Resp(content=BOM + (FIXTURES / "ishares_exsa_holdings.csv").read_bytes())})
    with pytest.raises(ValueError, match="only .* STOXX 600"):
        sources.fetch_index("stoxx600")                                  # 46 rows < 550


def test_index_holdings_http_error_raises(monkeypatch):
    serve(monkeypatch, {"ishares": Resp(404)})
    with pytest.raises(Exception, match="404"):
        sources.fetch_index("sp500")


# ---------------- FX ----------------

RATES = {"USDDKK=X": 6.5, "EURDKK=X": 7.46, "GBPDKK=X": 8.6, "SEKDKK=X": 0.65, "NOKDKK=X": 0.62,
         "CHFDKK=X": 8.0}


def _store_fx(days_ago: int, rates=RATES):
    d = pd.Timestamp(date.today() - timedelta(days=days_ago))
    df = pd.DataFrame([{"date": d, "ticker": t, "high": v, "low": v, "close": v, "raw_close": v, "volume": 0.0}
                       for t, v in rates.items()], columns=ingest.COLUMNS)
    ingest.PRICES_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(ingest.PRICES_FILE, index=False)


def _yahoo_fx(rates):
    def download(tickers, start):
        idx = pd.date_range(end=pd.Timestamp(date.today()), periods=2)
        cols = pd.MultiIndex.from_tuples([(t, "Close") for t in rates])
        return pd.DataFrame([[rates[t] for t in rates]] * 2, index=idx, columns=cols)
    return download


def test_fx_from_a_recent_price_store_does_not_ask_yahoo(monkeypatch):
    _store_fx(days_ago=2)
    fake = fake_yf(monkeypatch, download=lambda t, s: pytest.fail("asked Yahoo"))
    out = scan.fx_rates()
    assert out["DKK"] == 1.0 and out["EUR"] == 7.46 and out["CHF"] == 8.0 and fake.asked == []


@pytest.mark.parametrize("days_ago, rates", [(30, RATES),                         # stale store
                                              (1, {k: v for k, v in RATES.items() if k != "CHFDKK=X"})])
def test_fx_from_a_stale_or_incomplete_store_falls_back_to_yahoo(monkeypatch, days_ago, rates):
    _store_fx(days_ago, rates)
    fake = fake_yf(monkeypatch, download=_yahoo_fx(RATES | {"CHFDKK=X": 8.1}))
    out = scan.fx_rates()
    assert out["CHF"] == 8.1 and [k for k, _ in fake.asked] == ["download"]


def test_fx_without_a_store_uses_yahoo(monkeypatch):
    fake_yf(monkeypatch, download=_yahoo_fx(RATES))
    assert scan.fx_rates()["SEK"] == pytest.approx(RATES["SEKDKK=X"])


def test_fx_a_rate_yahoo_misses_comes_from_the_store_at_any_age(monkeypatch):
    _store_fx(days_ago=40)                                         # too old to use as a whole
    fake_yf(monkeypatch, download=_yahoo_fx({k: v for k, v in RATES.items() if k != "SEKDKK=X"}))
    assert scan.fx_rates()["SEK"] == pytest.approx(RATES["SEKDKK=X"])


def test_fx_a_needed_rate_missing_everywhere_raises_rather_than_dropping_a_market(monkeypatch):
    fake_yf(monkeypatch, download=_yahoo_fx({"USDDKK=X": 6.5, "EURDKK=X": 7.46, "GBPDKK=X": 8.6}))
    with pytest.raises(RuntimeError, match="no DKK rate for CHF, NOK, SEK"):
        scan.fx_rates()


def test_fx_with_too_few_rates_from_yahoo_raises(monkeypatch):
    fake_yf(monkeypatch, download=_yahoo_fx({"USDDKK=X": 6.5, "EURDKK=X": 7.46}))
    with pytest.raises(RuntimeError, match="no FX rates"):
        scan.fx_rates()


# ---------------- build_universe ----------------

MARKETS = {"nordic": {"label": "Nordic", "kind": "stock", "exchanges": ["CPH"]},
           "europe": {"label": "Europe", "kind": "stock", "exchanges": ["GER"]}}


def _q(sym, name, ccy, cap):
    return {"symbol": sym, "longName": name, "currency": ccy, "financialCurrency": ccy, "marketCap": cap,
            "quoteType": "EQUITY"}


SCREENS = {"CPH": [_q("NOVO-B.CO", "Novo Nordisk A/S", "DKK", 1e12)],
           "GER": [_q("SIE.DE", "Siemens AG", "EUR", 2e11), _q("NOV.DE", "Novo Nordisk A/S", "EUR", 1.3e11)]}


def _setup(monkeypatch, failing=()):
    monkeypatch.setattr(scan, "discovery_config", lambda: {"markets": MARKETS})
    monkeypatch.setattr(scan, "fx_rates", lambda: {"DKK": 1.0, "EUR": 7.46})
    monkeypatch.setattr(scan, "INDEX_KEEP", set())

    def screen(code, min_cap=5e7, **kw):
        if code in failing:
            raise ValueError(f"screener broke for {code}")
        return SCREENS[code]
    monkeypatch.setattr(sources, "screen_exchange", screen)
    monkeypatch.setattr(sources, "screen_sectors", lambda codes: {})
    monkeypatch.setattr(sources, "fetch_index", lambda key: pytest.fail("no index in these markets"))
    monkeypatch.setattr(universe, "currencies", lambda t: pytest.fail(f"currency lookup for {t}"))


def _cached(rows):
    scan.DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).reindex(columns=scan.UNIVERSE_COLS).to_csv(scan.UNIVERSE_FILE, index=False)


def _row(ticker, name, market, exchange, ccy):
    return {"ticker": ticker, "name": name, "market": market, "kind": "stock", "exchange": exchange,
            "currency": ccy, "market_cap_dkk": 1e9, "sector": ""}


def test_a_failed_market_keeps_its_cached_names_and_the_others_are_rebuilt(monkeypatch):
    _setup(monkeypatch, failing={"GER"})
    _cached([_row("OLD.CO", "Old Nordic A/S", "nordic", "CPH", "DKK"),       # rebuilt away
             _row("BAS.DE", "BASF SE", "europe", "GER", "EUR"),               # kept (market failed)
             _row("NOV.DE", "Novo Nordisk A/S", "europe", "GER", "EUR")])     # kept, but already in Nordic
    logs = []
    with pytest.raises(sourcelog.PartialFailure, match=r"Europe \(ValueError: screener broke for GER\)"):
        scan.build_universe(logs.append)
    df = scan.load_universe().set_index("ticker")
    assert dict(df["market"]) == {"NOVO-B.CO": "nordic", "BAS.DE": "europe"}
    assert any("Europe: FAILED" in m and "keeping 2 cached names" in m for m in logs)


def test_a_company_in_two_markets_stays_only_in_the_first(monkeypatch):
    _setup(monkeypatch)
    df = scan.build_universe(lambda m: None).set_index("ticker")
    assert dict(df["market"]) == {"NOVO-B.CO": "nordic", "SIE.DE": "europe"}
    assert df.loc["SIE.DE", "market_cap_dkk"] == pytest.approx(2e11 * 7.46)


def test_all_markets_failing_still_keep_cached_rows_and_with_none_cached_raise(monkeypatch):
    _setup(monkeypatch, failing={"CPH", "GER"})
    _cached([_row("BAS.DE", "BASF SE", "europe", "GER", "EUR")])
    with pytest.raises(sourcelog.PartialFailure):          # the cached Europe rows still make a universe
        scan.build_universe(lambda m: None)
    assert list(scan.load_universe()["ticker"]) == ["BAS.DE"]
    scan.UNIVERSE_FILE.unlink()
    with pytest.raises(RuntimeError, match="no market could be built"):
        scan.build_universe(lambda m: None)
    assert not scan.UNIVERSE_FILE.exists()

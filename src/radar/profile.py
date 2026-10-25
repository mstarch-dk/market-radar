"""Everything the radar knows about one ticker: price development, momentum, technicals, stop levels,
analyst estimates, valuation, ETF look-through and peers. Used by `radar info` and the web app.

Every section carries `status` (ok | stale | missing), `asof` and `source`, so a reader can tell a real
zero from absent data. Numbers come from the same functions the dashboard uses; nothing is invented when
a source has no answer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

import pandas as pd

from . import mine, money, universe
from .config import settings, typed, universe_config
from .jsonsafe import clean
from .market import Market
from .model import inputs
from .portfolios import trades
from .reporting import dashboard
from .signals import gauges as gz
from .signals import levels, momentum, risk, rotation, technicals
from .signals.score import score_vs
from .sources import external, fxrates, ingest, positive_list, tracked
from .universe import region_for

OK, STALE, MISSING = "ok", "stale", "missing"
WINDOWS = {"r1w": 5, "r1m": 21, "r3m": 63, "r6m": 126, "r1y": 252}
# the chart's ranges, counted like the return windows (None = year to date)
CHART_RANGES = {"1W": 5, "1M": 21, "3M": 63, "6M": 126, "YTD": None, "1Y": 252, "3Y": 756, "5Y": 1260}


class TickerNotFound(LookupError):
    pass


# ---------------- market data (the Market reader is in market.py) ----------------

def ensure_prices(ticker: str, market: Market | None = None, refresh: bool = False) -> Market:
    """Make sure `ticker` has a current history. Untracked tickers are downloaded (and kept in the price
    store, so the next lookup is fast) but are not added to the daily update. A tracked ticker waits for the
    update, unless `refresh` (the profile's refresh button) asks for its missing sessions now."""
    market = market or Market.load()
    bench = tracked.benchmark()
    is_tracked = ticker in set(universe.all_price_tickers(offline=True))
    have = ticker in market.closes.columns
    behind = have and market.closes[ticker].dropna().index[-1] < market.closes[bench].dropna().index[-1]
    if not have or (behind and (refresh or not is_tracked)):
        ingest.update_prices([ticker])
        market = Market.load()
    if ticker not in market.closes.columns or market.closes[ticker].dropna().empty:
        raise TickerNotFound(f"No Yahoo price data for {ticker}")
    return market


# ---------------- helpers ----------------

def _ret(s: pd.Series, n: int) -> float | None:
    s = s.dropna()
    return float(s.iloc[-1] / s.iloc[-1 - n] - 1) if len(s) > n else None


def _ret_since(s: pd.Series, start: pd.Timestamp) -> float | None:
    s = s.dropna()
    base = s[:start]
    return float(s.iloc[-1] / base.iloc[-1] - 1) if not base.empty else None


def _range_start(s: pd.Series, n: int | None):
    """The base date of a window on `s` (n rows back, or the last close of the previous year), None if too short."""
    if n is None:
        base = s[:pd.Timestamp(year=s.index[-1].year, month=1, day=1) - pd.Timedelta(days=1)]
        return base.index[-1] if not base.empty else None
    return s.index[-1 - n] if len(s) > n else None


def chart_ranges(close: pd.Series, bench: pd.Series, own_close: pd.Series) -> dict[str, dict]:
    """Return, ACWI's return and the difference for each chart range, on the same calendar as the Returns card
    (forward-filled closes), so 1M/YTD/1Y agree with it. A range longer than the stored history runs from the
    first close and says so (`short`). High/low are the ticker's own closes in the range."""
    end = own_close.index[-1]
    s, b = close.dropna()[:end], bench.dropna()[:end]
    out = {}
    for key, n in CHART_RANGES.items():
        start = _range_start(s, n)
        short = start is None
        start = s.index[0] if short else start
        ret = float(s.iloc[-1] / s[start] - 1)
        bb = b[:start]
        acwi = float(b.iloc[-1] / bb.iloc[-1] - 1) if not bb.empty and not b.empty else None
        own = own_close[start:]
        out[key] = {"start": start.strftime("%Y-%m-%d"), "short": short, "ret": ret, "acwi": acwi,
                    "vs_acwi": ret - acwi if acwi is not None else None,
                    "high": float(own.max()) if not own.empty else None, "low": float(own.min()) if not own.empty else None}
    return out


def _windows(s: pd.Series, end) -> dict[str, float | None]:
    """Returns over each window, ending on `end` (the ticker's last bar), plus year to date."""
    s = s.dropna()[:end]
    out = {k: _ret(s, n) for k, n in WINDOWS.items()}
    out["ytd"] = _ret_since(s, pd.Timestamp(year=pd.Timestamp(end).year, month=1, day=1) - pd.Timedelta(days=1))
    return out


def _diff(a: dict, b: dict) -> dict:
    return {k: (a[k] - b[k]) if a.get(k) is not None and b.get(k) is not None else None for k in a}


def sector_etf(region: str, sector: str | None, industry: str | None) -> str | None:
    cfg = universe_config().get("sector_etfs") or {}
    m = cfg.get("europe" if region in ("europe", "nordic") else region) or {}
    for prefix, etf in (m.get("industries") or {}).items():
        if industry and industry.startswith(prefix):
            return etf
    return m.get(sector) if sector else None


def _valuation_snapshot(ticker: str) -> dict | None:
    """The weekly valuation snapshot for this ticker (valuation.py): P/E against its sector peers and EPS
    revisions for a stock, P/E against ACWI for a fund, plus its P/E over the stored weeks. None when the
    snapshot doesn't have it."""
    from .sources import valuation

    ctx = valuation.context()
    fund = ticker in ctx.etf
    if not fund and ticker not in ctx.now.index:
        return None
    f = ctx.fund(ticker) if fund else ctx.stock(ticker)
    hist = valuation.load_etfs() if fund else valuation.load_stocks()
    col = "pe" if fund else "pe_fy1"
    h = hist[hist["ticker"] == ticker].sort_values("date")
    return {"kind": "fund" if fund else "stock", "asof": ctx.etf_asof if fund else ctx.asof, "weeks": len(h),
            "pe": f.get(col), "pe_vs_sector": f.get("pe_vs_sector"), "pe_vs_acwi": f.get("pe_vs_acwi"),
            "pe_pct": f.get("pe_pct"), "eps_rev_4w": f.get("eps_rev_4w"), "eps_rev_12w": f.get("eps_rev_12w"),
            "sector": None if fund else ctx.sector.get(ticker), "gauges": f["val_gauges"],
            "history": [{"date": pd.Timestamp(d).date().isoformat(), "pe": float(v)}
                        for d, v in zip(h["date"], h[col]) if pd.notna(v)]}


def _section(status: str, source: str, asof=None, **data) -> dict:
    return {"status": status, "source": source, "asof": asof, **data}


def quality_card(ticker: str, market: Market) -> dict | None:
    """The stock's kvalitetsscore and værdiscore card, from the scores of every tracked stock (built once per
    price store and statement update)."""
    from .fundamentals import context as fcontext

    return fcontext.context(market.closes, market.raw_closes(), universe.tracked_stocks(),
                            market.mtime).card(ticker)


# ---------------- the profile ----------------

@dataclass
class ProfileInputs:
    """Everything a profile reads from outside (prices, the Yahoo detail, your holdings, config, the dashboard's
    regime and leaders, stored analyst history, valuation and statements), loaded once by `load_inputs`. The
    sections below are pure functions of it; the properties are views of these fields that several sections share."""
    ticker: str
    market: Market
    bench: str
    cfg: dict                                     # settings.yaml as written
    raw: dict | None                              # the cached Yahoo detail (external.detail); None without one
    raw_status: str
    holdings: pd.DataFrame                        # your holdings and watchlist; empty when built anonymously
    etf: tracked.Instrument | None                # the tracked ETF this ticker is (or is the UCITS share class of)
    etfs: list[tracked.Instrument]
    region: str
    sectors: pd.DataFrame | None                  # universe.sectors, read for a stock only
    name: str | None
    currency: str | None
    is_tracked: bool
    stock_groups: dict[str, list[str]]
    group_labels: dict[str, str]
    leaders: pd.DataFrame                         # momentum and scores of every tracked stock (Market.leaders)
    analyst_history: pd.DataFrame                 # this ticker's stored analyst rows
    regime: dict
    rotation_window: int
    rotation_tail: int
    on_positive_list: str | None = None
    sector_etf: str | None = None
    valuation: dict | None = None                 # the weekly valuation snapshot (_valuation_snapshot)
    quality: dict | None = None                   # the quality card, read for a stock only
    peer_names: dict[str, str] = field(default_factory=dict)

    @property
    def info(self) -> dict:
        return (self.raw or {}).get("info") or {}

    @property
    def detail_asof(self) -> str | None:
        return self.raw["fetched"][:10] if self.raw else None

    @property
    def is_fund(self) -> bool:
        return self.info.get("quoteType") in ("ETF", "MUTUALFUND")

    @cached_property
    def look(self) -> dict | None:
        """The fund's look-through, None for anything but a fund."""
        return external.parse_fund((self.raw or {}).get("fund") or {}, self.info) if self.is_fund else None

    @property
    def sector(self) -> str | None:
        sec, look = self.sectors, self.look
        sector = self.info.get("sector") or (sec.loc[self.ticker, "sector"] if sec is not None else "") or None
        if look and look["sector_weights"] and look["sector_weights"][0]["weight"] >= 0.5:
            sector = look["sector_weights"][0]["sector"]       # a sector fund: compare it with that sector
        return sector

    @property
    def industry(self) -> str | None:
        sec = self.sectors
        return self.info.get("industry") or (sec.loc[self.ticker, "industry"] if sec is not None else "") or None

    @cached_property
    def close(self) -> pd.Series:
        return self.market.closes[self.ticker].dropna()

    @cached_property
    def own(self) -> pd.DataFrame:
        return self.market.bars(self.ticker)

    @cached_property
    def bench_close(self) -> pd.Series:
        return self.market.closes[self.bench].dropna()

    @property
    def last_date(self) -> pd.Timestamp:
        return self.own.index[-1]

    @cached_property
    def fx(self) -> pd.Series | None:
        return fxrates.fx_to_dkk(self.market.closes, self.currency)

    @property
    def mine(self) -> pd.DataFrame:
        return self.holdings[self.holdings["symbol"] == self.ticker]

    @property
    def status(self) -> str | None:
        mine = self.mine
        return mine.iloc[0]["status"] if len(mine) else None


def load_inputs(ticker: str, market: Market | None = None, refresh: bool = False,
                anonymous: bool = False) -> ProfileInputs:
    """Read everything the profile of `ticker` needs, prices first (TickerNotFound without them). `refresh` asks
    Yahoo for a fresh detail; `anonymous` leaves your holdings out (see build)."""
    cfg = settings()
    market = ensure_prices(ticker, market, refresh=refresh)   # refresh: a tracked ticker's missing sessions too
    raw, raw_status = external.detail(ticker, cfg.get("profile", {}).get("max_age_hours", 24), refresh)
    info = (raw or {}).get("info") or {}
    etfs = tracked.etfs()
    etf = next((e for e in etfs if ticker in (e.ticker, e.ucits)), None)
    hist = external.load_analyst()
    rc = typed().rotation
    inp = ProfileInputs(
        ticker=ticker, market=market, bench=tracked.benchmark(), cfg=cfg, raw=raw, raw_status=raw_status,
        holdings=trades.holdings() if not anonymous else pd.DataFrame(columns=trades.HOLDING_COLS),
        etf=etf, etfs=etfs, region=etf.region.lower() if etf else region_for(ticker),
        sectors=universe.sectors([ticker]) if info.get("quoteType", "EQUITY") == "EQUITY" else None,
        name=info.get("longName") or info.get("shortName") or universe.names([ticker])[ticker],
        currency=info.get("currency") or fxrates.currencies([ticker])[ticker],
        is_tracked=ticker in set(universe.all_price_tickers(offline=True)),
        stock_groups=tracked.stock_groups(offline=True), group_labels=tracked.stock_group_labels(),
        leaders=market.leaders(), analyst_history=hist[hist["ticker"] == ticker] if not hist.empty else hist,
        regime=inputs.current_regime(dashboard.load()), rotation_window=rc.window, rotation_tail=rc.tail,
        on_positive_list=positive_list.flag(etf.isin, market.positive_list()) if etf else None,
        valuation=_valuation_snapshot(ticker))
    # what depends on who the ticker is: its sector ETF, its peers' names and (a stock) its quality card
    if not etf:
        # a fund is compared with the US sector ETF of its dominant sector (the deepest, cleanest sector series)
        inp.sector_etf = sector_etf("us" if inp.look else inp.region, inp.sector, inp.industry)
    if inp.industry:
        same = _same_industry(inp)
        inp.peer_names = universe.names(list(same["ticker"].head(12))) if not same.empty else {}
    if not inp.is_fund and not etf:
        inp.quality = quality_card(ticker, market)
    return inp


def _age(inp: ProfileInputs) -> int:
    """Days between the ticker's last bar and the benchmark's last close."""
    return (pd.Timestamp(inp.bench_close.index[-1]) - inp.last_date).days


def _scored(inp: ProfileInputs) -> tuple[dict, Any, int | None, str, pd.DataFrame]:
    """The momentum metrics and the score within the region, as on the dashboard: the rank in its stock group,
    or a percentile against the region's group for a ticker that isn't a member. Also the basis and the pool."""
    m = momentum.metrics(inp.market.closes, inp.market.volumes, [inp.ticker],
                         inp.cfg["momentum"]["min_history_days"]).iloc[0].to_dict()
    lead, region = inp.leaders, inp.region
    in_group = lead[(lead["ticker"] == inp.ticker) & (lead["region"] == region)]
    pool = lead[lead["region"] == region] if region in set(lead["region"]) else lead[lead["region"] == "us"]
    if not in_group.empty:
        r = in_group.iloc[0]
        score, rank, basis = r["score"], int(r["rank"]) if pd.notna(r["rank"]) else None, "rank in its stock group"
    else:
        score, rank = score_vs(pool, pd.Series(m)), None
        basis = f"percentile against the {pool['region'].iloc[0] if len(pool) else region} stock group (not a member)"
    return m, score, rank, basis, pool


def _analyst_history(inp: ProfileInputs) -> pd.DataFrame:
    """The stored analyst history (tracked names) plus today's fetch, in the radar's price units."""
    hist, info, raw = inp.analyst_history, inp.info, inp.raw
    today_row = external.parse_analyst(info) if info else None
    if today_row and raw:
        hist = pd.concat([hist, pd.DataFrame([today_row | {"ticker": inp.ticker,
                                                           "fetched": pd.Timestamp(raw["fetched"][:10])}])],
                         ignore_index=True)
        for col in ("current_price", "target_mean", "target_median", "target_high", "target_low", "n_analysts", "rec_mean"):
            hist[col] = pd.to_numeric(hist[col], errors="coerce")
        hist = hist.drop_duplicates(["ticker", "fetched"], keep="last")
    return hist


def _same_industry(inp: ProfileInputs) -> pd.DataFrame:
    """The tracked stocks in the ticker's industry, strongest score first."""
    lead = inp.leaders
    return lead[(lead["industry"] == inp.industry) & (lead["ticker"] != inp.ticker)].sort_values("score", ascending=False)


def section_identity(inp: ProfileInputs) -> dict:
    info, etf, mine, status = inp.info, inp.etf, inp.mine, inp.status
    return _section(OK, "Yahoo Finance, config", inp.detail_asof,
        symbol=inp.ticker, name=inp.name,
        quote_type=info.get("quoteType") or ("ETF" if etf else None), currency=inp.currency,
        exchange=info.get("fullExchangeName") or info.get("exchange"), country=info.get("country"),
        sector=inp.sector, industry=inp.industry, website=info.get("website"),
        summary=info.get("longBusinessSummary"), employees=info.get("fullTimeEmployees"),
        region=inp.region, tracked=inp.is_tracked,
        stock_group=next((g for g, ts in inp.stock_groups.items() if inp.ticker in ts), None),
        etf_group=etf.group if etf else None, ucits=etf.ucits if etf else None,
        isin=etf.isin if etf else None, positive_list=inp.on_positive_list,
        my_status=status,
        my_position=clean(mine.iloc[0][["quantity", "avg_price", "first_trade"]].to_dict()) if status == "holding" else None)


def section_price(inp: ProfileInputs) -> dict:
    """Price development: returns in the quote currency and DKK, against ACWI and the sector ETF, the 52-week
    range and the last month's sessions."""
    closes, close, own, last_date, fx, setf = (inp.market.closes, inp.close, inp.own, inp.last_date, inp.fx,
                                               inp.sector_etf)
    local = _windows(close, last_date)
    dkk = _windows((close * fx.reindex(close.index).ffill()).dropna(), last_date) if fx is not None else None
    vs_acwi = _diff(local, _windows(inp.bench_close, last_date))
    vs_sector = (_diff(local, _windows(closes[setf], last_date))
                 if setf and setf in closes and closes[setf].notna().any() else None)
    year = close.iloc[-252:]
    recent = own.iloc[-21:]
    return _section(OK if _age(inp) <= inp.cfg["coverage"]["max_age"]["prices"] else STALE,
        "Yahoo Finance (adjusted closes)", last_date,
        last=float(own["close"].iloc[-1]), traded_last=float(own["raw_close"].iloc[-1]),
        change_1d=_ret(own["close"], 1), currency=inp.currency,
        returns=local, returns_dkk=dkk, vs_acwi=vs_acwi, sector_etf=setf, vs_sector=vs_sector,
        high_52w=float(year.max()), low_52w=float(year.min()),
        from_high=float(close.iloc[-1] / year.max() - 1), from_low=float(close.iloc[-1] / year.min() - 1),
        recent=[{"date": d, "close": float(r.close), "change": float(r.close / recent["close"].iloc[i - 1] - 1),
                 "volume": None if pd.isna(r.volume) else float(r.volume)}
                for i, (d, r) in enumerate(recent.iterrows()) if i > 0][::-1])


def section_momentum(inp: ProfileInputs) -> dict:
    """Momentum: score within the region, as on the dashboard."""
    m, score, rank, basis, pool = _scored(inp)
    return _section(OK, "radar (prices)", inp.last_date, **{k: v for k, v in m.items() if k != "ticker"},
                    score=score, rank=rank, group_size=int(len(pool)), score_basis=basis,
                    gauges=gz.gauges({"score": score, "from_high": m.get("from_high"), "vol_surge": m.get("vol_surge")}),
                    region_label=inp.group_labels.get(pool["region"].iloc[0]) if len(pool) else None)


def section_technicals(inp: ProfileInputs) -> dict:
    market, ticker, close = inp.market, inp.ticker, inp.close
    oc = inp.own["close"].dropna()                     # same bars as the chart, so card and chart agree
    ma = technicals.macd(oc).iloc[-1]
    bb = technicals.bollinger(oc).iloc[-1]
    rsi = technicals.rsi(oc).iloc[-1]
    atr = (levels.atr(market.highs[ticker], market.lows[ticker], market.closes[ticker],
                      inp.cfg["stops"]["atr_days"]).dropna()
           if ticker in market.highs else pd.Series(dtype=float))
    beta, corr = technicals.beta_corr(close, inp.bench_close)
    return _section(OK, "radar (prices)", inp.last_date,
        rsi14=rsi, rsi_state=None if pd.isna(rsi) else "overbought" if rsi >= 70 else "oversold" if rsi <= 30 else "neutral",
        macd=ma["macd"], macd_signal=ma["signal"], macd_hist=ma["hist"],
        macd_state=None if pd.isna(ma["hist"]) else "bullish" if ma["hist"] > 0 else "bearish",
        bb_pct_b=bb["pct_b"], bb_upper=bb["upper"], bb_lower=bb["lower"],
        atr=float(atr.iloc[-1]) if not atr.empty else None,
        atr_pct=float(atr.iloc[-1] / close.iloc[-1]) if not atr.empty else None,
        vol_3m=technicals.realised_vol(oc, 63), max_drawdown_1y=technicals.max_drawdown(oc),
        beta_acwi=beta, corr_acwi=corr,
        gauges=gz.gauges({"rsi14": rsi, "bb_pct_b": bb["pct_b"],
                          "macd_atr": ma["hist"] / atr.iloc[-1] if not atr.empty and atr.iloc[-1] else None,
                          "atr_pct": atr.iloc[-1] / close.iloc[-1] if not atr.empty else None, "beta": beta}))


def section_analyst(inp: ProfileInputs) -> dict:
    """Analyst targets, recommendations, EPS estimates and the earnings calendar."""
    raw = inp.raw or {}
    hist = _analyst_history(inp)
    view = (levels.analyst_view(hist, inp.ticker, inp.close, max_age_days=inp.cfg["coverage"]["max_age"]["analyst"])
            if not hist.empty else None)
    recs = external.parse_recommendations(raw.get("recommendations") or [])
    eps = external.parse_eps_trend(*(raw.get(k) or {} for k in ("eps_trend", "eps_revisions", "growth_estimates")))
    cal = external.parse_calendar(raw.get("calendar") or {})
    has_analyst = bool(view and view.get("target_mean")) or bool(recs) or bool(eps)
    return _section(inp.raw_status if has_analyst else MISSING, "Yahoo Finance", inp.detail_asof,
                    **(view or {}), recommendations=recs, eps=eps, calendar=cal,
                    gauges=gz.gauges({"upside": (view or {}).get("upside"),
                                      "target_change": (view or {}).get("target_change")}))


def section_levels(inp: ProfileInputs) -> dict:
    """Stop / take-profit levels: the same rule as for holdings, anchored on your entry when you hold it."""
    m, score, *_ = _scored(inp)
    cfg, market = inp.cfg, inp.market
    row = m | {"score": None if score is None or pd.isna(score) else score}
    lv = levels.for_ticker(inp.ticker, market.closes, market.highs, market.lows, row,
                           inp.mine.iloc[0]["first_trade"] if inp.status == "holding" else None, inp.regime["label"],
                           _analyst_history(inp),
                           cfg["stops"] | {"analyst_max_age_days": cfg["coverage"]["max_age"]["analyst"]})
    if lv:
        lv.pop("analyst", None)
    return _section(OK if lv else MISSING, "radar (prices, analyst targets)", inp.last_date,
                    **(lv or {}), regime=inp.regime["label"],
                    gauges=gz.gauges({"stop_dist": (lv or {}).get("stop_pct"), "tp_dist": (lv or {}).get("tp_pct")}))


def section_risk(inp: ProfileInputs, stop_pct) -> dict:
    """Weekly DKK returns vs ACWI, factor tilts, and the position size the rule stop (`stop_pct`) allows."""
    return risk_section(inp.ticker, inp.market, inp.close, inp.fx, inp.sector_etf, stop_pct, inp.last_date)


def section_fundamentals(inp: ProfileInputs) -> dict:
    fund = external.parse_fundamentals(inp.info)      # all keys, None where Yahoo has nothing
    fx = inp.fx
    if fund.get("market_cap") and not money.is_pence(inp.currency) and fx is not None:
        fund["market_cap_dkk"] = fund["market_cap"] * float(fx.iloc[-1])
    has_fund = any(v is not None for k, v in fund.items() if k not in ("notes", "currency", "financial_currency"))
    beta, _ = technicals.beta_corr(inp.close, inp.bench_close)
    return _section(inp.raw_status if has_fund else MISSING,
                    "Yahoo Finance", inp.detail_asof, **fund, beta_radar=beta, snapshot=inp.valuation)


def section_quality(inp: ProfileInputs) -> dict | None:
    """Kvalitetsscore and værdiscore from the stored statements; None for a fund."""
    if inp.is_fund or inp.etf:
        return None
    card = inp.quality
    return (_section(OK, "SEC EDGAR" if card["fund_source"] == "edgar" else "Yahoo statements",
                     card["period_end"], **card) if card else
            _section(MISSING, "statements", None, notes=[
                "No financial statements stored for this stock: the radar fetches them for the stocks it "
                "tracks (its lists, your holdings and watchlist), a few each update."]))


def section_etf(inp: ProfileInputs) -> dict | None:
    """A fund's look-through, with the top holdings you hold yourself; None for anything but a fund."""
    if inp.look is None:
        return None
    h = inp.holdings
    held = set(h.loc[h["status"] == "holding", "symbol"]) if not h.empty else set()
    f = inp.look | {"overlap": [x["symbol"] for x in inp.look["top_holdings"] if x.get("symbol") in held]}
    return _section(inp.raw_status if f["top_holdings"] or f["expense_ratio"] else MISSING, "Yahoo Finance",
                    inp.detail_asof, **f)


def section_peers(inp: ProfileInputs) -> dict:
    """Peers in the same industry and the sector ETF's (or the ETF's own) place in the rotation."""
    closes, industry = inp.market.closes, inp.industry
    peers = []
    if industry:
        same, names = _same_industry(inp), inp.peer_names
        peers = [{"ticker": r.ticker, "name": names.get(r.ticker, r.ticker), "region": r.region, "score": r.score,
                  "r3m": r.r3m, "r6m": r.r6m, "trend_ok": r.trend_ok, "from_high": r.from_high}
                 for r in same.head(12).itertuples()]
    rot = None
    target = inp.sector_etf or (inp.ticker if inp.etf else None)
    if target and target in closes:
        inst = next((e for e in inp.etfs if e.ticker == target), None) or tracked.Instrument(
            target, target, "sector", inp.region)
        t = rotation.relative_table(closes, inp.bench, [inst], inp.rotation_window, inp.rotation_tail)
        if not t.empty:
            r = t.iloc[0]
            rot = {"ticker": target, "name": inst.name, "quadrant": r["quadrant"], "rs_ratio": r["rs_ratio"],
                   "rs_mom": r["rs_mom"], "rel_r3m": r["rel_r3m"]}
    return _section(OK if peers or rot else MISSING, "radar (prices, Yahoo sectors)", inp.last_date,
                    industry=industry, peers=peers, rotation=rot)


def context_notes(inp: ProfileInputs) -> list[str]:
    """What a reader should know about the data behind the profile: a Yahoo detail that couldn't be refreshed,
    an untracked ticker, a missing DKK rate, a stale last price. The sections' own notes follow these."""
    raw, notes = inp.raw, []
    if inp.raw_status != OK:
        notes.append("Yahoo fundamentals and estimates: " + ("no data" if raw is None else
                     f"couldn't refresh, showing data from {raw['fetched'][:10]}"))
    for block, when in ((raw or {}).get("kept") or {}).items():
        notes.append(f"Yahoo {block.replace('_', ' ')}: couldn't refresh, showing data from {when[:10]}")
    if not inp.is_tracked:
        notes.append("Not tracked by the radar: prices are fetched on lookup, not in the daily update")
    if inp.fx is None:
        notes.append(f"No DKK rate for currency {inp.currency}: DKK returns not shown")
    age = _age(inp)
    if not age <= inp.cfg["coverage"]["max_age"]["prices"]:
        notes.append(f"Last price is from {inp.last_date.date()}, {age} days before the benchmark's last close")
    return notes


def build(ticker: str, market: Market | None = None, refresh: bool = False, anonymous: bool = False) -> dict:
    """The full profile of `ticker` (a Yahoo symbol). Raises TickerNotFound without price data. `anonymous`
    builds it as if you held nothing: no status or position, stops anchored on the recent high instead of
    your entry, and no overlap with your holdings, so nothing personal can be read from it."""
    inp = load_inputs(ticker, market, refresh, anonymous)
    identity, price, mom, tech = section_identity(inp), section_price(inp), section_momentum(inp), section_technicals(inp)
    analyst, lvl = section_analyst(inp), section_levels(inp)
    risk_sec = section_risk(inp, lvl.get("stop_pct"))
    fundamentals, quality, etf, peers = (section_fundamentals(inp), section_quality(inp), section_etf(inp),
                                         section_peers(inp))
    notes = context_notes(inp)
    for s in (fundamentals, etf or {}):
        notes += s.get("notes") or []
    watchouts = gz.watchouts({k: v for sec in (tech, mom, lvl, analyst) for k, v in sec["gauges"].items()},
                             skip=set() if inp.status == "holding" else {"stop_dist", "tp_dist"})
    out = {"symbol": ticker, "generated": pd.Timestamp.now().isoformat(timespec="seconds"),
           "identity": identity, "price": price, "momentum": mom, "technicals": tech, "levels": lvl, "risk": risk_sec,
           "analyst": analyst, "fundamentals": fundamentals, "quality": quality, "etf": etf, "peers": peers,
           "context": {"regime": inp.regime, "notes": notes, "errors": (inp.raw or {}).get("errors") or {},
                       "watchouts": watchouts}}
    if not anonymous:   # your market views are personal, like your positions
        from . import market_views

        out["views"] = market_views.align_profile(identity, inp.market.closes)
    return checked(clean(out))


def checked(p: dict) -> dict:
    """A profile against api_models.Profile (what the ticker page reads; extra fields an error): a shape the app
    can't show fails here, for `radar info` and the API alike, naming the field."""
    from pydantic import ValidationError

    from . import api_models

    try:
        api_models.Profile.model_validate(p)
    except ValidationError as e:
        err = e.errors()[0]
        raise ValueError(f"the profile of {p.get('symbol')} doesn't match api_models.Profile: "
                         f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}") from None
    return p


def risk_section(ticker: str, market: Market, close: pd.Series, fx: pd.Series | None, sector_etf_: str | None,
                 stop_pct, asof) -> dict:
    """Risk statistics in DKK over the configured windows (see signals/risk.py), factor tilts vs ACWI (the factor
    ETFs and the sector ETF) and the risk budget at the rule stop."""
    rc = typed().risk
    closes = market.closes
    bench = tracked.benchmark()
    usd = fxrates.fx_to_dkk(closes, fxrates.currencies([bench])[bench])
    if fx is None or usd is None:
        return _section(MISSING, "radar (prices, FRED 3m T-bill)", asof, currency="DKK", benchmark=bench,
                        windows={}, factors=None, budget=None, notes=["no DKK rate for this currency"])

    def dkk(px: pd.Series, rate: pd.Series) -> pd.Series:
        return risk.weekly((px * rate.reindex(px.index).ffill()).dropna())

    y = dkk(close, fx)
    mkt = dkk(closes[bench].dropna(), usd)
    rf = market.fred()["DGS3MO"] if "DGS3MO" in market.fred() else None
    windows = {k: risk.window_stats(y, mkt, rf, n, rc.min_weeks) for k, n in rc.windows.items()}
    windows = {k: v for k, v in windows.items() if v}
    tilts = {f: dkk(closes[f].dropna(), usd) for f in rc.factors if f in closes and f != ticker}
    if sector_etf_ and sector_etf_ in closes and sector_etf_ != ticker:
        tilts[f"sector {sector_etf_}"] = dkk(closes[sector_etf_].dropna(), usd)
    longest = max(rc.windows.values())
    factors = risk.factor_loadings(y, mkt, tilts, rf, longest, rc.min_weeks) if tilts else None
    notes = []
    if rf is None:
        notes.append("no risk-free rate yet (FRED DGS3MO): Sharpe and Sortino are not computed, alpha uses raw returns")
    return _section(OK if windows else MISSING, "radar (prices, FRED 3m T-bill)", asof, currency="DKK", benchmark=bench,
                    windows=windows, factors=factors, budget=risk.risk_budget(stop_pct, rc.budget),
                    budget_risk=rc.budget, notes=notes)


def legacy_info(p: dict) -> dict:
    """The flat keys `radar info` has always printed (used by /research), followed by the full profile."""
    m = p["momentum"]
    flat = {k: m.get(k) for k in ("last", "r1m", "r3m", "r6m", "r12_1", "from_high", "sma50", "sma200", "vol_surge",
                                   "above50", "above200", "trend_ok")}
    flat |= {"ticker": p["symbol"], "name": p["identity"]["name"], "currency": p["identity"]["currency"]}
    flat |= {f"rel_{k}": p["price"]["vs_acwi"].get(k) for k in ("r1m", "r3m", "r6m")}
    if p["identity"]["stock_group"]:
        flat |= {"region": p["identity"]["stock_group"], "score_in_region": m["score"], "rank_in_region": m["rank"],
                 "region_size": m["group_size"]}
    flat["my_status"] = p["identity"]["my_status"]
    return flat | p


# ---------------- chart series ----------------

def series(ticker: str, market: Market, days: int = 756) -> dict:
    """Daily series for the charts, computed on the full history and then cut to the last `days`."""
    closes = market.closes
    bench = tracked.benchmark()
    own = market.bars(ticker)                     # real sessions only: a missing Yahoo bar is a gap, not a flat day
    c = own["close"].dropna()
    if c.empty:
        raise TickerNotFound(ticker)
    ma = technicals.macd(c)
    bb = technicals.bollinger(c)
    df = pd.DataFrame({
        "close": c, "high": own["high"].reindex(c.index), "low": own["low"].reindex(c.index),
        "volume": own["volume"].reindex(c.index), "sma50": c.rolling(50).mean(), "sma200": c.rolling(200).mean(),
        "rsi": technicals.rsi(c), "macd": ma["macd"], "macd_signal": ma["signal"], "macd_hist": ma["hist"],
        "bb_upper": bb["upper"], "bb_lower": bb["lower"],
        "rel_acwi": c / closes[bench].reindex(c.index).ffill(),
    }).iloc[-days:]
    df["rel_acwi"] = 100 * df["rel_acwi"] / df["rel_acwi"].dropna().iloc[0]   # rebased to 100 at the window start
    df.index = df.index.strftime("%Y-%m-%d")
    ranges = chart_ranges(closes[ticker], closes[bench], c)
    return clean({"symbol": ticker, "dates": list(df.index), **{k: df[k].tolist() for k in df.columns}, "ranges": ranges})


# ---------------- several tickers side by side ----------------

# (label, path into the profile, direction: "higher" / "lower" is better, None = context only)
COMPARE_METRICS = [
    ("Momentum score (region)", "momentum.score", "higher"),
    ("Return 1m", "price.returns.r1m", "higher"),
    ("Return 3m", "price.returns.r3m", "higher"),
    ("Return 6m", "price.returns.r6m", "higher"),
    ("Return 12-1m", "momentum.r12_1", "higher"),
    ("Return 6m in DKK", "price.returns_dkk.r6m", "higher"),
    ("vs ACWI 3m", "price.vs_acwi.r3m", "higher"),
    ("From 52w high", "momentum.from_high", "higher"),
    ("Trend intact", "momentum.trend_ok", None),
    ("RSI 14", "technicals.rsi14", None),
    ("Volatility 1y (DKK)", "risk.windows.1y.vol_ann", "lower"),
    ("Beta 3y", "risk.windows.3y.beta", None),
    ("Downside beta 3y", "risk.windows.3y.downside_beta", "lower"),
    ("Alpha 3y (annual)", "risk.windows.3y.alpha_ann", "higher"),
    ("Alpha 3y t-stat", "risk.windows.3y.alpha_t", None),
    ("Sharpe 3y", "risk.windows.3y.sharpe", "higher"),
    ("Max drawdown 3y", "risk.windows.3y.max_dd", "higher"),
    ("P/E on this year's EPS estimate", "derived.pe_0y", "lower"),
    ("P/E on next year's EPS estimate", "derived.pe_1y", "lower"),
    ("Forward P/E (Yahoo's basis)", "fundamentals.forward_pe", None),
    ("EV/EBITDA", "fundamentals.ev_ebitda", "lower"),
    ("Revenue growth", "fundamentals.revenue_growth", "higher"),
    ("Earnings growth", "fundamentals.earnings_growth", "higher"),
    ("Operating margin", "fundamentals.operating_margin", "higher"),
    ("Return on equity", "fundamentals.return_on_equity", "higher"),
    ("Debt/equity", "fundamentals.debt_to_equity", "lower"),
    ("Dividend yield", "fundamentals.dividend_yield", None),
    ("Kvalitetsscore", "quality.quality", "higher"),
    ("Værdiscore", "quality.value", "higher"),
    ("FCF yield", "derived.fcf_yield", "higher"),
    ("ROIC", "derived.roic", "higher"),
    ("EV/EBIT", "quality.ev_ebit", "lower"),
    ("Shareholder yield", "derived.shareholder_yield", "higher"),
    ("Analyst upside", "analyst.upside", "higher"),
    ("Analyst target change 30d", "analyst.target_change", "higher"),
    ("EPS estimate change 30d (this year)", "analyst.eps.0y.chg_30d", "higher"),
    ("Next earnings", "analyst.calendar.next_earnings", None),
    ("Distance to rule stop", "levels.stop_pct", None),
    ("Position size at 1% risk", "risk.budget", None),
]


def _get(d, path: str):
    """Value at a dotted path; list items are matched on their `period` (e.g. analyst.eps.0y)."""
    for part in path.split("."):
        if isinstance(d, list):
            d = next((x for x in d if isinstance(x, dict) and x.get("period") == part), None)
        elif isinstance(d, dict):
            d = d.get(part)
        else:
            return None
        if d is None:
            return None
    return d


def _derived(p: dict) -> dict:
    """P/E on the consensus EPS for this and next fiscal year, so the basis is explicit (Yahoo's `forwardPE`
    may use either). Only when the EPS is quoted in the price's currency; otherwise null, not a mixed ratio."""
    out = {}
    price, ccy = p["price"]["last"], p["price"]["currency"]
    for key, period in (("pe_0y", "0y"), ("pe_1y", "+1y")):
        e = next((x for x in p["analyst"]["eps"] if x["period"] == period), None)
        ok = e is not None and e.get("eps") and e["eps"] > 0 and (e.get("currency") or ccy) == ccy
        out[key] = price / e["eps"] if e is not None and ok else None
    metrics = {m["key"]: m.get("value") for m in ((p.get("quality") or {}).get("metrics") or [])}
    for key in ("fcf_yield", "roic", "shareholder_yield"):
        out[key] = metrics.get(key)
    return out


def compare(symbols: list[str], personal: bool = False, market: Market | None = None,
            portfolios: list[int] | None = None) -> dict:
    """Several tickers side by side, with ACWI as the always-present alternative: full profiles, the market
    regime, weekly-return correlations (DKK) and a table of key metrics with the best value per row. Without
    `personal` the profiles are built anonymously (see build); with it, "your holdings" are these portfolios
    (ids; default: your real ones). An unknown ticker becomes an error entry."""
    market = market or Market.load()
    bench = tracked.benchmark()
    rc = typed().risk
    tickers: dict[str, dict] = {}
    for sym in dict.fromkeys(s.strip().upper() for s in symbols):
        try:
            market = ensure_prices(sym, market)
            tickers[sym] = build(sym, market, anonymous=not personal)
        except TickerNotFound as e:
            tickers[sym] = {"error": str(e)}
    ok = {s: p for s, p in tickers.items() if "error" not in p}

    # ACWI: the zero-effort alternative every candidate has to beat
    closes = market.closes
    usd = fxrates.fx_to_dkk(closes, fxrates.currencies([bench])[bench])
    b = closes[bench].dropna()
    mkt = risk.weekly((b * usd.reindex(b.index).ffill()).dropna()) if usd is not None else None
    rf = market.fred()["DGS3MO"] if "DGS3MO" in market.fred() else None
    # ACWI against itself: beta 1 and alpha 0 by definition; the regression's error terms are numerical noise
    self_fit = {"beta_se": None, "r2": None, "alpha_t": None, "idio_vol_ann": None, "downside_beta": 1.0}
    bench_block = {"symbol": bench, "name": universe.names([bench]).get(bench), "returns": _windows(b, b.index[-1]),
                   "risk": {k: (w | self_fit | {"alpha_ann": 0.0, "beta": 1.0, "corr": 1.0}) if w else None
                            for k, n in rc.windows.items()
                            for w in [risk.window_stats(mkt, mkt, rf, n, rc.min_weeks) if mkt is not None else None]}}

    # correlations of weekly DKK returns: the candidates, ACWI, and (personal) the current holdings
    series = {}
    for sym in [*ok, bench] + (sorted(set(trades.holdings(portfolios).query("status == 'holding'")["symbol"]) - set(ok))
                               if personal else []):
        if sym not in closes:
            continue
        fx = fxrates.fx_to_dkk(closes, fxrates.currencies([sym])[sym])
        if fx is not None:
            s = closes[sym].dropna()
            series[sym] = risk.weekly((s * fx.reindex(s.index).ffill()).dropna())
    corr = risk.correlation(series, rc.windows["1y"], rc.min_weeks)

    bench_profile = {"price": {"returns": bench_block["returns"]}, "risk": {"windows": bench_block["risk"]}}
    derived = {s: _derived(p) for s, p in ok.items()}
    table = []
    for label, path, direction in COMPARE_METRICS:
        values = {s: clean(_get(p | {"derived": derived[s]}, path)) for s, p in ok.items()}
        acwi = clean(_get(bench_profile, path))
        if acwi is not None:
            values[bench] = acwi
        nums = {s: v for s, v in values.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
        best = (max(nums, key=lambda s: nums[s]) if direction == "higher" else min(nums, key=lambda s: nums[s])) \
            if direction and len(nums) > 1 else None
        table.append({"metric": label, "path": path, "direction": direction, "values": values, "best": best})

    d = dashboard.load()
    regime = None
    if d:
        overall, inds = inputs.regime_now(d)                            # with your current choice of voting groups
        regime = {"asof": d["asof"], "overall": overall,
                  "indicators": [{k: i.get(k) for k in ("name", "value", "status", "gauge")} for i in inds]}
    out = {"generated": pd.Timestamp.now().isoformat(timespec="seconds"),
           "asof": closes[bench].dropna().index[-1].date().isoformat(),
           "personal_included": personal, "regime": regime, "benchmark": bench_block,
           "tickers": tickers, "correlation": corr, "table": table}
    if personal:
        rot = [r for g in (d or {}).get("rotation", {}).get("groups", []) for r in g["rows"]]
        rows = mine.table(closes, market.highs, market.lows, market.volumes, market.raw_closes(), market.leaders(), rot,
                          (regime or {}).get("overall", {}).get("label"), settings(), sessions=lambda s: market.bars(s)["close"],
                          portfolios=portfolios)
        out["mine"] = {r["symbol"]: r for r in rows if r["symbol"] in ok}
    return clean(out)
